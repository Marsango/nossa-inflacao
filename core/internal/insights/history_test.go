package insights

import (
	"strings"
	"testing"
	"time"
)

func TestOverviewDisclosesCitiesWithoutComparingDifferentLocations(test *testing.T) {
	curitiba := testContext("shop", "1000", "")
	curitiba.Location = "Curitiba/PR"
	saoPaulo := testContext("shop", "", "2000")
	saoPaulo.Location = "São Paulo/SP"
	product := ProductSeries{Contexts: []ContextSeries{curitiba, saoPaulo, curitiba}, Streams: 3, Shops: 1}
	history := Build([]ProductSeries{product}, true, 1, time.Now())
	if history.ChangeBasisPoints != nil || history.Counts.IncludedStreams != 0 {
		test.Fatal("different locations must not create a temporal price change")
	}
	if !strings.Contains(history.Coverage, "Localidades observadas: Curitiba/PR; São Paulo/SP.") {
		test.Fatalf("missing or duplicated geography: %s", history.Coverage)
	}
}

func testSeries(name string, values ...string) ProductSeries {
	context := testContext("shop", values...)
	return ProductSeries{Name: name, Streams: 1, Shops: 1, Contexts: []ContextSeries{context}}
}

func testContext(shop string, values ...string) ContextSeries {
	context := ContextSeries{ShopID: shop, ShopName: shop}
	for position, value := range values {
		context.Points = append(context.Points, testPrice(position, value))
	}
	return context
}

func testPrice(position int, value string) PricePoint {
	point := PricePoint{Date: time.Date(2026, 10, 27+position, 0, 0, 0, 0, time.UTC).Format("2006-01-02")}
	if value != "" {
		point.Amount = &value
	}
	return point
}

func assertValue(test *testing.T, actual *int64, expected int64) {
	test.Helper()
	if actual == nil || *actual != expected {
		test.Fatalf("got %v, expected %d", actual, expected)
	}
}

func TestMatchedChangesKeepGapsAndExactMeans(test *testing.T) {
	product := testSeries("Arroz", "2001/2", "", "2201/2")
	history := Build([]ProductSeries{product}, false, 1, time.Now())
	assertValue(test, history.LatestPriceMinor, 1101)
	assertValue(test, history.ChangeBasisPoints, 1000)
	if history.Points[1].Value != nil || history.Counts.PricedDays != 2 {
		test.Fatal("missing day must remain missing")
	}
}

func TestShopsHaveEqualWeightRegardlessOfContextCount(test *testing.T) {
	product := testSeries("Café", "2000", "2200")
	product.Contexts = append(product.Contexts, testContext("shop", "1000", "1100"), testContext("other", "2500", "2500"))
	product.Contexts = append(product.Contexts, testContext("unavailable", "1800", ""))
	product.Streams, product.Shops = 4, 3
	history := Build([]ProductSeries{product}, false, 3, time.Now())
	assertValue(test, history.ChangeBasisPoints, 500)
	assertValue(test, history.Points[0].Value, 2000)
	assertValue(test, history.Points[1].Value, 2075)
	if history.Counts.IncludedStreams != 3 || history.Counts.IncludedShops != 2 || history.ShopPrices[3].Included {
		test.Fatal("incorrect comparison coverage")
	}
}

func TestUnavailableShopDoesNotHidePricesOrChangeVariation(test *testing.T) {
	product := testSeries("Café", "2780", "2780")
	product.Contexts = append(product.Contexts, testContext("unavailable", "", ""))
	product.Streams, product.Shops = 2, 2
	history := Build([]ProductSeries{product}, false, 2, time.Now())
	assertValue(test, history.LatestPriceMinor, 2780)
	assertValue(test, history.ChangeBasisPoints, 0)
	if len(history.ShopPrices) != 2 || history.ShopPrices[1].Points[0].Value != nil {
		test.Fatal("shop prices lost or fabricated")
	}
}

func TestOverviewMatchesEachDayAndWeightsProductsEqually(test *testing.T) {
	products := []ProductSeries{testSeries("Arroz", "1000", "1100", "1200"), testSeries("Café", "10000", "", "9000")}
	products = append(products, testSeries("Unavailable", "100", "100", ""))
	history := Build(products, true, 1, time.Now())
	assertValue(test, history.Points[0].Value, 0)
	assertValue(test, history.ChangeBasisPoints, 333)
	assertValue(test, history.Points[1].Value, 500)
	if history.Counts.IncludedProducts != 3 || history.Counts.Products != 3 {
		test.Fatal("incomplete panel or exclusions incorrect")
	}
}

func TestNoShopSwitchOrMovingBaseline(test *testing.T) {
	product := testSeries("Café", "1000", "")
	product.Contexts = append(product.Contexts, testContext("other", "", "2000"))
	history := Build([]ProductSeries{product}, false, 2, time.Now())
	assertValue(test, history.LatestPriceMinor, 2000)
	if history.ChangeBasisPoints != nil || history.ComparisonStart != nil || history.Counts.IncludedProducts != 0 {
		test.Fatal("availability switch invented a price change")
	}
	zero := Build([]ProductSeries{testSeries("Zero", "0", "100")}, true, 1, time.Now())
	if zero.ChangeBasisPoints != nil || zero.Counts.IncludedProducts != 0 {
		test.Fatal("zero baseline was included")
	}
}

func TestSingleDayAndEmptyHistory(test *testing.T) {
	single := Build([]ProductSeries{testSeries("Leite", "100")}, false, 1, time.Now())
	assertValue(test, single.LatestPriceMinor, 100)
	if single.ChangeBasisPoints != nil || single.ComparisonStart != nil {
		test.Fatal("single day invented variation")
	}
	empty := Build(nil, true, 0, time.Now())
	if empty.Points == nil || empty.ShopPrices == nil || empty.CollectedAt != nil {
		test.Fatal("empty history must preserve unknowns and arrays")
	}
}

func TestFreshnessUsesObservationTime(test *testing.T) {
	collected := time.Date(2026, 10, 27, 12, 0, 0, 0, time.UTC)
	product := testSeries("Arroz", "100")
	product.CollectedAt = &collected
	fresh := Build([]ProductSeries{product}, false, 1, collected.Add(48*time.Hour))
	stale := Build([]ProductSeries{product}, false, 1, collected.Add(48*time.Hour+time.Second))
	if fresh.Stale || !stale.Stale {
		test.Fatal("freshness boundary must be 48 hours")
	}
}

func TestRoundingAndSafeJSONIntegers(test *testing.T) {
	negative := "-1/2"
	assertValue(test, rounded(amount(&negative)), -1)
	huge := "10000000000000000"
	if rounded(amount(&huge)) != nil {
		test.Fatal("unsafe JSON integer must remain unavailable")
	}
}

func TestAveragesContextRelativesRatherThanPriceLevels(test *testing.T) {
	product := testSeries("Café", "1000", "2000")
	product.Contexts = append(product.Contexts, testContext("shop", "10000", "10000"))
	history := Build([]ProductSeries{product}, false, 1, time.Now())
	assertValue(test, history.ChangeBasisPoints, 5000)
	assertValue(test, history.Points[0].Value, 5500)
	assertValue(test, history.Points[1].Value, 6000)
}

func TestZeroEndpointRemainsARealPrice(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Café", "1000", "0")}, false, 1, time.Now())
	assertValue(test, history.LatestPriceMinor, 0)
	assertValue(test, history.ChangeBasisPoints, -10000)
}

func TestAvailableIntervalIgnoresEmptySelectedEndpoints(test *testing.T) {
	series := []ProductSeries{testSeries("Café", "", "1000", "", "1100", "")}
	history := Build(series, false, 1, time.Now())
	assertAvailableInterval(test, history)
}

func assertAvailableInterval(test *testing.T, history History) {
	test.Helper()
	expected := Period{Start: "2026-10-28", End: "2026-10-30"}
	if history.AvailablePeriod == nil || *history.AvailablePeriod != expected {
		test.Fatalf("incorrect available dates: %+v", history.AvailablePeriod)
	}
	if *history.ComparisonStart != expected.Start || *history.ComparisonEnd != expected.End {
		test.Fatal("comparison must disclose the actual dates used")
	}
	assertValue(test, history.ChangeBasisPoints, 1000)
	if len(history.Points) != 3 || history.Points[1].Value != nil || history.Counts.PricedDays != 2 {
		test.Fatal("trimmed chart must preserve internal gaps")
	}
}

func TestSingleAvailableDayHasPricesWithoutChange(test *testing.T) {
	series := []ProductSeries{testSeries("Leite", "", "100", "")}
	for _, global := range []bool{false, true} {
		history := Build(series, global, 1, time.Now())
		assertSingleAvailableDay(test, history, global)
	}
}

func assertSingleAvailableDay(test *testing.T, history History, global bool) {
	test.Helper()
	if len(history.Points) != 1 || history.Counts.PricedDays != 1 {
		test.Fatal("one available day must remain visible")
	}
	if history.ChangeBasisPoints != nil || history.ComparisonStart != nil || history.ComparisonEnd != nil {
		test.Fatal("one day cannot provide a change")
	}
	if global {
		assertValue(test, history.Points[0].Value, 0)
		return
	}
	assertValue(test, history.Points[0].Value, 100)
}

func TestAvailablePricesDoNotInventComparableVariation(test *testing.T) {
	product := testSeries("Café", "", "1000", "", "", "")
	product.Contexts = append(product.Contexts, testContext("other", "", "", "", "2000", ""))
	history := Build([]ProductSeries{product}, false, 2, time.Now())
	assertValue(test, history.Points[0].Value, 1000)
	assertValue(test, history.Points[2].Value, 2000)
	if history.ChangeBasisPoints != nil || history.Counts.IncludedStreams != 0 || history.Points[1].Value != nil {
		test.Fatal("switching shops cannot produce comparable variation or fill gaps")
	}
}

func TestZeroBaselinePricesRemainVisibleWithoutVariation(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Café", "", "0", "100", "")}, false, 1, time.Now())
	assertValue(test, history.Points[0].Value, 0)
	assertValue(test, history.Points[1].Value, 100)
	if history.ChangeBasisPoints != nil || history.ComparisonStart != nil {
		test.Fatal("zero baseline cannot produce a relative change")
	}
}

func TestNoEligiblePricesHasNoAvailableInterval(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Café", "", "", "")}, false, 1, time.Now())
	if history.AvailablePeriod != nil || history.ChangeBasisPoints != nil || history.Counts.PricedDays != 0 {
		test.Fatal("no eligible prices must not invent dates or values")
	}
}

func TestSparseCalendarUsesSharedBoundsAndKeepsInternalGaps(test *testing.T) {
	amount := "1200"
	series := []ProductSeries{{Contexts: []ContextSeries{
		{Points: []PricePoint{{Date: "2026-10-27", Amount: &amount}, {Date: "2026-10-29", Amount: &amount}}},
		{Points: []PricePoint{{Date: "2026-10-28", Amount: &amount}}},
	}}}
	expanded := ExpandSparse(series, "2026-10-01", "2026-11-01")
	first, second := expanded[0].Contexts[0].Points, expanded[0].Contexts[1].Points
	if len(first) != 3 || first[1].Amount != nil || first[0].Date != "2026-10-27" {
		test.Fatal("outer dates were kept or internal gap was filled")
	}
	if second[0].Amount != nil || second[2].Amount != nil || second[1].Amount == nil {
		test.Fatal("contexts do not share the same calendar")
	}
}

func TestSparseAllNullSelectionRetainsRequestedCalendar(test *testing.T) {
	series := []ProductSeries{{Contexts: []ContextSeries{{Points: []PricePoint{{Date: "2026-10-28"}}}}}}
	expanded := ExpandSparse(series, "2026-10-27", "2026-10-29")
	points := expanded[0].Contexts[0].Points
	if len(points) != 3 || points[0].Date != "2026-10-27" || points[2].Date != "2026-10-29" {
		test.Fatal("all-null selection lost its requested calendar")
	}
}

func TestOverviewIncludesLaterProductsWithoutLosingDays(test *testing.T) {
	series := []ProductSeries{testSeries("Continuous", "1000", "1100", "1210"),
		testSeries("Missing", "1000", "", "2000"), testSeries("New", "", "1000", "1200")}
	history := Build(series, true, 1, time.Now())
	assertValue(test, history.Points[1].Value, 1000)
	assertValue(test, history.ChangeBasisPoints, 4700)
	assertValue(test, history.DailyComparisons[1].ChangeBasisPoints, 4700)
	if history.Counts.IncludedProducts != 3 || history.Counts.PricedDays != 3 {
		test.Fatalf("incorrect union coverage: %+v", history.Counts)
	}
	if history.DailyComparisons[0].Products != 1 || history.DailyComparisons[1].Products != 3 {
		test.Fatalf("daily coverage must show the changing sample: %+v", history.DailyComparisons)
	}
}

func TestOverviewUsesExactFirstAndLatestRatios(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Round trip", "300", "400", "300")}, true, 1, time.Now())
	assertValue(test, history.DailyComparisons[0].ChangeBasisPoints, 3333)
	assertValue(test, history.ChangeBasisPoints, 0)
	history = Build([]ProductSeries{testSeries("Up then down", "1000", "1100", "990")}, true, 1, time.Now())
	assertValue(test, history.ChangeBasisPoints, -100)
}

func TestOverviewRetainsKnownComparisonWithoutInventingMissingPrices(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Gap", "1000", "1100", "", "1000", "1200")}, true, 1, time.Now())
	assertValue(test, history.Points[2].Value, 1000)
	assertValue(test, history.ChangeBasisPoints, 2000)
	comparison := history.DailyComparisons[1]
	if comparison.Products != 1 || comparison.UpdatedStreams != 0 || *comparison.ComparisonEnd != "2026-10-28" {
		test.Fatalf("missing price became a fresh observation: %+v", comparison)
	}
}

func TestOverviewAcceptsNonconsecutiveDatesWithoutUsingFuturePrices(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Gap", "", "1000", "", "1100", "")}, true, 1, time.Now())
	if history.AvailablePeriod.Start != "2026-10-28" || len(history.Points) != 3 {
		test.Fatal("available bounds must still trim empty outer dates")
	}
	if history.Points[1].Value != nil || history.DailyComparisons[0].Products != 0 {
		test.Fatal("a future price must not qualify a context earlier")
	}
	assertValue(test, history.ChangeBasisPoints, 1000)
}

func TestOverviewWeightsContextsShopsAndProductsPerDay(test *testing.T) {
	product := testSeries("First", "1000", "2000")
	product.Contexts = append(product.Contexts, testContext("shop", "10000", "10000"), testContext("other", "1000", "3000"))
	history := Build([]ProductSeries{product, testSeries("Second", "2000", "1000")}, true, 2, time.Now())
	assertValue(test, history.ChangeBasisPoints, 3750)
	if history.DailyComparisons[0].Products != 2 || history.DailyComparisons[0].Shops != 2 || history.DailyComparisons[0].Streams != 4 {
		test.Fatal("daily weights or coverage changed with context count")
	}
}

func TestOverviewZeroStartingPriceExcludesOnlyThatPair(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Zero", "0", "100", "110"), testSeries("Stable", "100", "100", "100")}, true, 1, time.Now())
	assertValue(test, history.ChangeBasisPoints, 500)
	if history.DailyComparisons[0].Products != 1 || history.DailyComparisons[1].Products != 2 {
		test.Fatal("a zero baseline must be excluded only on its own day")
	}
}

func TestOverviewMonthCountsSparsePairOnlyFromSecondObservation(test *testing.T) {
	values := make([]string, 31)
	values[0], values[29] = "3000", "5000"
	later := make([]string, 31)
	later[30] = "9000"
	history := Build([]ProductSeries{testSeries("Sparse", values...), testSeries("Single later price", later...)}, true, 1, time.Now())
	if history.Points[28].Value != nil || history.DailyComparisons[27].Products != 0 {
		test.Fatal("day 29 must not use the observation from day 30")
	}
	assertValue(test, history.Points[29].Value, 6667)
	assertValue(test, history.Points[30].Value, 6667)
	comparison := history.DailyComparisons[29]
	if comparison.Products != 1 || comparison.UpdatedStreams != 0 || *comparison.ComparisonEnd != history.Points[29].Date {
		test.Fatal("day 31 must retain the historical pair with its actual last observation date")
	}
}

func TestOverviewCountsEachContextOnceRegardlessOfObservationCount(test *testing.T) {
	history := Build([]ProductSeries{testSeries("Frequent", "1000", "1200", "1500"), testSeries("Sparse", "1000", "", "1000")}, true, 1, time.Now())
	assertValue(test, history.ChangeBasisPoints, 2500)
	if history.Counts.IncludedStreams != 2 || history.DailyComparisons[1].Streams != 2 {
		test.Fatal("all possible observation pairs must not overweight frequent collections")
	}
}
