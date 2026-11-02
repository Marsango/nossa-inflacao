package insights

import (
	"fmt"
	"math/big"
	"time"
)

func comparable(context ContextSeries) bool {
	if len(context.Points) == 0 {
		return false
	}
	baseline := amount(context.Points[0].Amount)
	last := amount(context.Points[len(context.Points)-1].Amount)
	return baseline != nil && baseline.Sign() > 0 && last != nil
}

func prepare(product ProductSeries) ProductSeries {
	shops := map[string][]ContextSeries{}
	for _, context := range product.Contexts {
		includeContext(&product, shops, context)
	}
	product.Points, product.Changes = matchedPoints(product.Contexts, shops)
	return product
}

func matchedPoints(contexts []ContextSeries, shops map[string][]ContextSeries) ([]PricePoint, []PricePoint) {
	prices, changes := []PricePoint{}, []PricePoint{}
	if len(contexts) == 0 {
		return prices, changes
	}
	for position, point := range contexts[0].Points {
		prices = append(prices, PricePoint{point.Date, rationalText(shopAverage(shops, position, false))})
		changes = append(changes, PricePoint{point.Date, rationalText(shopAverage(shops, position, true))})
	}
	return prices, changes
}

func rationalText(value *big.Rat) *string {
	if value == nil {
		return nil
	}
	text := value.RatString()
	return &text
}

func shopAverage(shops map[string][]ContextSeries, position int, changes bool) *big.Rat {
	if len(shops) == 0 {
		return nil
	}
	total := new(big.Rat)
	for _, contexts := range shops {
		total = addAmount(total, contextAverage(contexts, position, changes))
	}
	return divide(total, len(shops))
}

func contextAverage(contexts []ContextSeries, position int, changes bool) *big.Rat {
	total := new(big.Rat)
	for _, context := range contexts {
		total = addAmount(total, contextValue(context, position, changes))
	}
	return divide(total, len(contexts))
}

func contextValue(context ContextSeries, position int, changes bool) *big.Rat {
	value := amount(context.Points[position].Amount)
	if changes {
		return relative(value, amount(context.Points[0].Amount))
	}
	return value
}

func includeContext(product *ProductSeries, shops map[string][]ContextSeries, context ContextSeries) {
	if !comparable(context) {
		return
	}
	shops[context.ShopID] = append(shops[context.ShopID], context)
	product.IncludedStreams++
}

func prepareSeries(series []ProductSeries) []ProductSeries {
	result := make([]ProductSeries, 0, len(series))
	for _, product := range series {
		result = append(result, prepare(product))
	}
	return result
}

func addAmount(total, value *big.Rat) *big.Rat {
	if total == nil || value == nil {
		return nil
	}
	return total.Add(total, value)
}

func divide(total *big.Rat, count int) *big.Rat {
	if total == nil || count == 0 {
		return nil
	}
	return total.Quo(total, big.NewRat(int64(count), 1))
}

// Raw histories build the same observed pairs before the SQL summaries are initialized.
type overviewParticipants struct {
	products map[int]bool
	shops    map[string]bool
	streams  map[string]bool
	pairs    map[string]*observedPair
}

func rawOverview(series []ProductSeries, shopCount int, now time.Time) History {
	calculator := rawCalculator(series, shopCount)
	if len(series) == 0 {
		return calculator.Build("", "", now)
	}
	metadata := calculator.metadata
	series = trimSeries(series, metadata.AvailablePeriod)
	addRawComparisons(calculator, series)
	points := overviewCalendar(series)
	return calculator.Build(points[0].Date, points[len(points)-1].Date, now)
}

func rawCalculator(series []ProductSeries, shopCount int) *OverviewCalculator {
	history := emptyHistory()
	history.Counts = Coverage{Products: len(series), Shops: shopCount}
	collectMetadata(&history, series)
	return NewOverview(OverviewMetadata{Counts: history.Counts, AvailablePeriod: availablePeriod(series),
		UnknownConditions: history.UnknownConditions, CollectedAt: history.CollectedAt, Locations: overviewLocations(series)})
}

func overviewLocations(series []ProductSeries) []string {
	locations := map[string]bool{}
	for _, product := range series {
		collectLocations(locations, product.Contexts)
	}
	names := []string{}
	for location := range locations {
		names = append(names, location)
	}
	return names
}

func addRawComparisons(calculator *OverviewCalculator, series []ProductSeries) {
	participants := overviewParticipants{products: map[int]bool{}, shops: map[string]bool{},
		streams: map[string]bool{}, pairs: map[string]*observedPair{}}
	points := overviewCalendar(series)
	for position := 0; position < len(points); position++ {
		comparison, total := rawComparison(series, position, &participants)
		calculator.comparisons[comparison.Date] = comparison
		calculator.totals[comparison.Date] = total
	}
	calculator.includeParticipants(participants)
}

func rawComparison(series []ProductSeries, position int, participants *overviewParticipants) (DailyComparison, *big.Rat) {
	points := overviewCalendar(series)
	comparison := DailyComparison{Date: points[position].Date}
	total, shops := new(big.Rat), map[string]bool{}
	for productPosition, product := range series {
		daily := observedProduct(product, position, productPosition, participants.pairs)
		total.Add(total, includeObservedProduct(&comparison, daily, productPosition, participants))
		registerObservedContexts(daily.Contexts, productPosition, participants, shops, &comparison)
	}
	comparison.Shops = len(shops)
	return comparison, total
}

func observedProduct(product ProductSeries, position, productPosition int, pairs map[string]*observedPair) ProductSeries {
	contexts := make([]ContextSeries, len(product.Contexts))
	for index, context := range product.Contexts {
		identity := fmt.Sprintf("%d:%d", productPosition, index)
		contexts[index] = observedContext(context, position, contextPair(pairs, identity))
	}
	return prepare(ProductSeries{Contexts: contexts})
}

func contextPair(pairs map[string]*observedPair, identity string) *observedPair {
	if pairs[identity] == nil {
		pairs[identity] = &observedPair{}
	}
	return pairs[identity]
}

func observedContext(context ContextSeries, position int, pair *observedPair) ContextSeries {
	pair.observe(context.Points[position])
	context.Points = []PricePoint{{}, {}}
	if pair.first != nil {
		context.Points[0] = *pair.first
	}
	if pair.last != nil {
		context.Points[1] = *pair.last
	}
	return context
}

type observedPair struct{ first, last *PricePoint }

func (pair *observedPair) observe(point PricePoint) {
	if point.Amount == nil {
		return
	}
	if pair.first != nil {
		pair.last = &point
		return
	}
	value := amount(point.Amount)
	if value == nil || value.Sign() <= 0 {
		return
	}
	pair.first = &point
}

func includeObservedProduct(comparison *DailyComparison, product ProductSeries, position int, participants *overviewParticipants) *big.Rat {
	if product.IncludedStreams == 0 {
		return new(big.Rat)
	}
	participants.products[position] = true
	comparison.Products++
	comparison.Streams += product.IncludedStreams
	changes := product.Changes
	change := amount(changes[1].Amount)
	return new(big.Rat).Add(change, big.NewRat(10000, 1))
}

func registerObservedContexts(contexts []ContextSeries, productPosition int, participants *overviewParticipants, shops map[string]bool, comparison *DailyComparison) {
	for position, context := range contexts {
		registerObservedContext(context, fmt.Sprintf("%d:%d", productPosition, position), participants, shops, comparison)
	}
}

func registerObservedContext(context ContextSeries, identity string, participants *overviewParticipants, shops map[string]bool, comparison *DailyComparison) {
	if !comparable(context) {
		return
	}
	participants.streams[identity], participants.shops[context.ShopID], shops[context.ShopID] = true, true, true
	points := context.Points
	includePairDates(comparison, points[0].Date, points[1].Date)
	if points[1].Date == comparison.Date {
		comparison.UpdatedStreams++
	}
}

func overviewCalendar(series []ProductSeries) []PricePoint {
	product := series[0]
	contexts := product.Contexts
	return contexts[0].Points
}

func (calculator *OverviewCalculator) includeParticipants(participants overviewParticipants) {
	metadata := calculator.metadata
	counts := metadata.Counts
	counts.IncludedProducts = len(participants.products)
	counts.IncludedShops = len(participants.shops)
	counts.IncludedStreams = len(participants.streams)
	metadata.Counts = counts
	calculator.metadata = metadata
}

func includePairDates(comparison *DailyComparison, start, end string) {
	if comparison.ComparisonStart == nil || start < *comparison.ComparisonStart {
		comparison.ComparisonStart = &start
	}
	if comparison.ComparisonEnd == nil || end > *comparison.ComparisonEnd {
		comparison.ComparisonEnd = &end
	}
}
