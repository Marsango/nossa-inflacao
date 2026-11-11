package webapi

import (
	"fmt"
	"net/url"
	"strings"
	"testing"

	"inflacao-real/core/internal/dailysummary"
)

func TestSearchValidationAndDefaults(test *testing.T) {
	store := &fakeStore{}
	assertStatus(test, store, "/api/v1/products?q=CAF%C3%89", 200)
	if store.products.Query != "CAFÉ" || store.products.Limit != 20 {
		test.Fatalf("search not forwarded: %+v", store.products)
	}
	invalid := []string{"", "a", "  ", "***", "a!", strings.Repeat("a", 101)}
	for _, search := range invalid {
		assertStatus(test, store, "/api/v1/products?q="+url.QueryEscape(search), 400)
	}
}

func TestCuratedFiltersUseIngestionLabels(test *testing.T) {
	fixture := newFixture(test)
	names := []string{"Arroz branco tipo 1", "Banana nanica", "Bala de banana", "Peito de frango", "Sabão em pó", "Produto sem classificação"}
	for position, name := range names {
		seedLabeledProduct(fixture, position+1, name)
	}
	assertGroupProducts(fixture, "cesta-basica", "1", "2")
	assertGroupProducts(fixture, "hortifruti", "2")
	assertGroupProducts(fixture, "doces", "3")
	assertGroupProducts(fixture, "carnes", "4")
	assertGroupHistory(fixture, "cesta-basica", 2, 1500)
	assertGroupHistory(fixture, "hortifruti", 1, 2000)
	assertGroupHistory(fixture, "doces", 1, 3000)
	assertGroupHistory(fixture, "carnes", 1, 4000)
	if history := fixture.history("global", "2026-10-27", "2026-10-28"); history.Counts.Products != 6 {
		test.Fatal("unfiltered overview must include unclassified products")
	}
}

func seedLabeledProduct(fixture fixture, identity int, name string) {
	fixture.submit(identity*2, func(observation map[string]any) {
		labelProductObservation(observation, identity, name)
		setPrice(observation, "2026-10-27T12:00:00Z", "10.00")
	})
	fixture.submit(identity*2+1, func(observation map[string]any) {
		labelProductObservation(observation, identity, name)
		setPrice(observation, "2026-10-28T12:00:00Z", fmt.Sprintf("%d.00", 10+identity))
	})
}

func labelProductObservation(observation map[string]any, identity int, name string) {
	product := observation["product"].(map[string]any)
	product["source_product_id"], product["name"] = fmt.Sprint(identity), name
}

func assertGroupProducts(fixture fixture, group string, identities ...string) {
	fixture.test.Helper()
	var result Products
	fixture.get("/api/v1/products?group="+group, &result)
	if len(result.Items) != len(identities) || result.Items == nil {
		fixture.test.Fatalf("group %s: %+v, expected %v", group, result, identities)
	}
	for position, identity := range identities {
		assertSearchIdentity(fixture.test, result.Items[position], identity)
	}
}

func assertGroupHistory(fixture fixture, group string, count int, change int64) {
	fixture.test.Helper()
	history := fixture.history("global&group="+group, "2026-10-27", "2026-10-28")
	if history.Counts.Products != count || history.Counts.IncludedProducts != count || history.Unit != "percent" {
		fixture.test.Fatalf("incorrect selection: %+v", history)
	}
	assertPrice(fixture.test, history.ChangeBasisPoints, change)
	if !strings.Contains(history.Methodology, "Seleção:") || !strings.Contains(history.Title, "Variação de preços ·") {
		fixture.test.Fatal("missing selection context")
	}
}

func TestCuratedSearchPaginationAndEmptyHistory(test *testing.T) {
	fixture := newFixture(test)
	seedLabeledProduct(fixture, 1, "Banana nanica")
	seedLabeledProduct(fixture, 2, "Banana prata")
	var first, second Products
	fixture.get("/api/v1/products?group=hortifruti&q=banana&limit=1", &first)
	if len(first.Items) != 1 || first.NextCursor == nil || *first.NextCursor != "1" {
		test.Fatalf("unexpected first page: %+v", first)
	}
	fixture.get("/api/v1/products?group=hortifruti&q=banana&limit=1&after=1", &second)
	if len(second.Items) != 1 || second.Items[0].ID != "2" || second.NextCursor != nil {
		test.Fatalf("unexpected second page: %+v", second)
	}
	assertGroupProducts(fixture, "doces")
	assertEmptyGroupHistory(fixture)
}

func assertEmptyGroupHistory(fixture fixture) {
	history := fixture.history("global&group=doces", "2026-10-27", "2026-10-28")
	if len(history.Points) != 0 || history.ChangeBasisPoints != nil || history.Counts.Products != 0 || history.Title != "Variação de preços · Doces" {
		fixture.test.Fatalf("empty selection fabricated data: %+v", history)
	}
	history = fixture.history("1&group=doces", "2026-10-27", "2026-10-28")
	if len(history.Points) != 0 || history.Unit != "BRL" {
		fixture.test.Fatal("product outside selection must have empty history")
	}
}

func TestCuratedFiltersIncludeEquivalentMembersOnce(test *testing.T) {
	fixture := newFixture(test)
	seedLabeledProduct(fixture, 1, "Banana nanica")
	seedLabeledProduct(fixture, 2, "Banana prata")
	fixture.execute(`INSERT INTO product_equivalence(product_id,representative_id) VALUES (1,1),(2,1)`)
	fixture.execute(`DELETE FROM product_monitoring_targets WHERE product_id=1`)
	fixture.execute(`UPDATE shop_products SET product_id=NULL`)
	assertGroupProducts(fixture, "hortifruti", "1")
	assertGroupHistory(fixture, "hortifruti", 1, 1500)
	history := fixture.history("2&group=hortifruti", "2026-10-27", "2026-10-28")
	if history.Counts.Streams != 2 || history.Counts.Products != 1 {
		test.Fatal("equivalent member lost historical observations")
	}
}

func seedSearchProducts(fixture fixture) {
	fixture.submit(1, nil)
	fixture.submit(2, secondPricedDay)
	fixture.execute(`UPDATE products SET name='Café torrado 500g', brand='União' WHERE id=1`)
	fixture.execute(`INSERT INTO products (name, brand) VALUES
        ('Café moído 500 g', 'União'), ('Café sem observações', 'União')`)
	fixture.execute(`UPDATE price_observations SET product_id=2 WHERE offer_index=1`)
}

func TestIndexedProductSearch(test *testing.T) {
	fixture := newFixture(test)
	seedSearchProducts(fixture)
	assertSearch(test, fixture, "CAFE uni", "1", "2")
	assertSearch(test, fixture, "uniao torr 500 g", "1")
	assertSearch(test, fixture, "uni cafe moid 500g", "2")
	assertSearch(test, fixture, "cafe | ! uniao:*", "1", "2")
	assertSearch(test, fixture, "cafe' OR '1'='1")
	assertSearch(test, fixture, "inexistente")
	assertSearch(test, fixture, "中文")
	fixture.execute(`UPDATE products SET name='Chocolate',brand=NULL WHERE id=1`)
	assertSearch(test, fixture, "choc", "1")
	assertSearch(test, fixture, "cafe", "2")
}

func assertSearch(test *testing.T, fixture fixture, search string, identities ...string) {
	test.Helper()
	var result Products
	fixture.get("/api/v1/products?q="+url.QueryEscape(search), &result)
	if len(result.Items) != len(identities) || result.Items == nil {
		test.Fatalf("search %q: %+v, expected %v", search, result, identities)
	}
	for index, identity := range identities {
		assertSearchIdentity(test, result.Items[index], identity)
	}
}

func assertSearchIdentity(test *testing.T, product Product, expected string) {
	test.Helper()
	if product.ID != expected {
		test.Fatalf("unexpected product: %+v, expected %s", product, expected)
	}
}

func TestSearchRanksBananasAheadOfFlavoredProducts(test *testing.T) {
	fixture := newFixture(test)
	names := []string{"Bala de banana", "Iogurte de banana", "Banana nanica orgânica 1 kg", "Banana prata", "Banana", "Bananada", "Chocolate"}
	expected := []string{"5", "4", "3", "6", "1", "2"}
	for number := 8; number <= 18; number++ {
		names = append(names, fmt.Sprintf("Biscoito de banana marca %d", number))
		expected = append(expected, fmt.Sprint(number))
	}
	for position, name := range names {
		seedLabeledProduct(fixture, position+1, name)
	}
	fixture.execute(`UPDATE products SET brand='Banana' WHERE id=7`)
	expected = append(expected, "7")
	assertSearch(test, fixture, "BANÁNA!", expected...)
	assertSearchPages(fixture, "q=banana", expected...)
}

func TestSearchRanksTomatoesAheadOfSaucesAndPasta(test *testing.T) {
	fixture := newFixture(test)
	names := []string{"Macarrão com molho de tomate", "Molho de tomate", "Tomate italiano selecionado 1 kg", "Tomate cereja", "Tomate"}
	for position, name := range names {
		seedLabeledProduct(fixture, position+1, name)
	}
	assertSearch(test, fixture, "tomate", "5", "4", "3", "2", "1")
	assertSearch(test, fixture, "tom", "5", "4", "3", "2", "1")
	assertSearchPages(fixture, "q=tomate&group=hortifruti", "5", "4", "3")
}

func TestSearchRanksMultiwordNamesAndFewerExtraWords(test *testing.T) {
	fixture := newFixture(test)
	names := []string{"Iogurte com leite em pó", "Leite em pó integral 400g", "Leite em pó", "Leite pó"}
	for position, name := range names {
		seedLabeledProduct(fixture, position+1, name)
	}
	assertSearch(test, fixture, "leite em po", "3", "2", "1")
	assertSearch(test, fixture, "po leite", "4", "3", "1", "2")
	assertSearch(test, fixture, "leite em po integral 400 g", "2")
}

func TestSearchRanksPicanhaAheadOfFlavoredAndPreparedProducts(test *testing.T) {
	fixture := newFixture(test)
	names := []string{"Salgadinho sabor picanha", "Hambúrguer de picanha",
		"Picanha bovina resfriada Friboi peça 1kg", "Picanha bovina kg", "Picanha",
		"Picanha temperada com alho e ervas 1kg"}
	for position, name := range names {
		seedLabeledProduct(fixture, position+1, name)
	}
	expected := []string{"5", "4", "3", "6", "1", "2"}
	assertSearch(test, fixture, "PICANHA", expected...)
	assertSearch(test, fixture, "pican", expected...)
	assertSearchPages(fixture, "q=picanha", expected...)
}

func TestSearchRanksGroundMeatAheadOfPreparedDishes(test *testing.T) {
	fixture := newFixture(test)
	names := []string{"Lasanha com carne moída", "Esfiha de carne moída",
		"Carne Moída Bovino TOP QUALITY Patinho ATM Resfriado 500g", "Carne moída bovina kg",
		"Carne moída", "Carne bovina moída", "Molho com carne moída e tomate"}
	for position, name := range names {
		seedLabeledProduct(fixture, position+1, name)
	}
	expected := []string{"5", "4", "3", "6", "1", "2", "7"}
	assertSearch(test, fixture, "carne moida", expected...)
	assertSearch(test, fixture, "CARNE MOÍDA", expected...)
	assertSearch(test, fixture, "carne moi", expected...)
	assertSearchPages(fixture, "q=carne+moida", expected...)
}

func TestSearchRanksEquivalentProductsByTheirBestMember(test *testing.T) {
	fixture := newFixture(test)
	names := []string{"Fruta fresca", "Bala de banana", "Banana prata", "Banana"}
	for position, name := range names {
		seedLabeledProduct(fixture, position+1, name)
	}
	fixture.execute(`INSERT INTO product_equivalence(product_id,representative_id) VALUES (1,1),(3,1),(4,1)`)
	assertSearch(test, fixture, "banana", "1", "2")
	assertSearchPages(fixture, "q=banana", "1", "2")
}

func assertSearchPages(fixture fixture, query string, identities ...string) {
	fixture.test.Helper()
	cursor := ""
	for position, identity := range identities {
		var page Products
		fixture.get("/api/v1/products?"+query+"&limit=1"+cursor, &page)
		assertSearchPage(fixture.test, page, identity, position < len(identities)-1)
		cursor = "&after=" + identity
	}
}

func assertSearchPage(test *testing.T, page Products, identity string, hasNext bool) {
	test.Helper()
	if len(page.Items) != 1 || (page.NextCursor != nil) != hasNext {
		test.Fatalf("unexpected search page: %+v", page)
	}
	assertSearchIdentity(test, page.Items[0], identity)
	if hasNext && *page.NextCursor != identity {
		test.Fatalf("cursor must identify the last returned product: %+v", page)
	}
}

func TestSearchPaginationPreservesHistoricalAssignments(test *testing.T) {
	fixture := newFixture(test)
	seedSearchProducts(fixture)
	var first, second Products
	fixture.get("/api/v1/products?q=cafe&limit=1", &first)
	if len(first.Items) != 1 || first.Items[0].ID != "1" || first.NextCursor == nil {
		test.Fatalf("unexpected first search page: %+v", first)
	}
	fixture.get("/api/v1/products?q=cafe&limit=1&after="+*first.NextCursor, &second)
	if len(second.Items) != 1 || second.Items[0].ID != "2" || second.NextCursor != nil {
		test.Fatalf("unexpected second search page: %+v", second)
	}
}

func TestProductPaginationAcceptsBigintCursors(test *testing.T) {
	fixture := newFixture(test)
	seedSearchProducts(fixture)
	for _, query := range []string{"", "q=cafe&"} {
		var page Products
		fixture.get("/api/v1/products?"+query+"after=9223372036854775807", &page)
		assertEmptyProductPage(test, page)
	}
}

func assertEmptyProductPage(test *testing.T, page Products) {
	test.Helper()
	if len(page.Items) != 0 || page.Items == nil || page.NextCursor != nil {
		test.Fatalf("expected an empty product page: %+v", page)
	}
}

func TestCatalogRequiresTwoDaysOfHistoricalInStockPrices(test *testing.T) {
	fixture := newFixture(test)
	seedSearchProducts(fixture)
	fixture.execute(`UPDATE price_observations SET availability='out_of_stock' WHERE product_id=2`)
	assertSearch(test, fixture, "cafe", "1")
	assertCatalogIdentities(test, fixture, "1")
	fixture.execute(`UPDATE price_observations SET availability='unknown' WHERE product_id=1`)
	assertSearch(test, fixture, "cafe")
	assertCatalogIdentities(test, fixture)
	fixture.execute(`UPDATE price_observations SET availability='in_stock' WHERE product_id=2`)
	assertSearch(test, fixture, "cafe", "2")
	assertCatalogIdentities(test, fixture, "2")
}

func assertCatalogIdentities(test *testing.T, fixture fixture, identities ...string) {
	test.Helper()
	var result Products
	fixture.get("/api/v1/products?limit=1", &result)
	if len(result.Items) != len(identities) || result.NextCursor != nil {
		test.Fatalf("unexpected catalog: %+v", result)
	}
	for index, identity := range identities {
		assertSearchIdentity(test, result.Items[index], identity)
	}
}

func TestPreviouslyAvailableProductsRemainSearchable(test *testing.T) {
	fixture := newFixture(test)
	fixture.submit(1, nil)
	fixture.submit(2, secondPricedDay)
	fixture.submit(3, func(observation map[string]any) {
		observation["observed_at"] = "2026-10-29T12:00:00Z"
		observation["availability"], observation["offers"] = "out_of_stock", []any{}
	})
	fixture.execute(`UPDATE shop_products SET product_id=NULL`)
	assertSearch(test, fixture, "arroz", "1")
	assertCatalogIdentities(test, fixture, "1")
}

func secondPricedDay(observation map[string]any) {
	setPrice(observation, "2026-10-28T12:00:00Z", "26.90")
}

func TestInStockWithoutAnyPriceIsNotSearchable(test *testing.T) {
	fixture := newFixture(test)
	fixture.submit(1, func(observation map[string]any) { observation["offers"] = []any{} })
	assertSearch(test, fixture, "arroz")
	assertCatalogIdentities(test, fixture)
}

func TestSearchDoesNotCountOffersOrSameDayCollectionsAsComparison(test *testing.T) {
	fixture := newFixture(test)
	fixture.submit(1, nil)
	fixture.submit(2, func(observation map[string]any) {
		setPrice(observation, "2026-10-27T22:00:00Z", "26.90")
	})
	assertSearch(test, fixture, "arroz")
	assertCatalogIdentities(test, fixture)
	fixture.submit(3, secondPricedDay)
	assertSearch(test, fixture, "arroz", "1")
	assertCatalogIdentities(test, fixture, "1")
}

func TestSearchRequiresTwoDatesInTheSameContext(test *testing.T) {
	fixture := newFixture(test)
	fixture.submit(1, nil)
	fixture.submit(2, func(observation map[string]any) {
		secondPricedDay(observation)
		observation["context"].(map[string]any)["store_id"] = "another-branch"
	})
	assertSearch(test, fixture, "arroz")
	assertCatalogIdentities(test, fixture)
}

type massListing struct {
	name, brand, quantity, unit, basis, first, last string
	count                                           int
}

func TestAutomaticProduceGroupingAndMassConversion(test *testing.T) {
	fixture := newFixture(test)
	seedBananaMassListings(fixture)
	assertBananaGroups(fixture)
	assertBananaMassHistory(fixture)
	requireSuccess(test, dailysummary.Refresh(fixture.ctx, fixture.pool))
	assertBananaMassHistory(fixture)
	assertDailyOverview(fixture, "2026-10-27", "2026-10-28", "")
	assertDeclaredMassSafety(fixture)
}

func seedBananaMassListings(fixture fixture) {
	listings := []massListing{
		{"Banana Prata 750g", "GERAL", "750", "g", "package", "7.50", "8.25", 1},
		{"Banana prata 1,1kg", "", "", "", "package", "11.00", "12.10", 0},
		{"Banana Prata 500g", "Direto do Produtor", "500", "g", "package", "10.00", "11.00", 2},
		{"Banana Prata Aproximadamente 150g/un", "HORTIFRUTI", "", "", "kg", "10.00", "11.00", 0},
		{"Banana Prata Orgânica Santome 800g", "SANTOME", "800", "g", "package", "8.00", "8.80", 1},
		{"Banana Prata Turma da Mônica 750g", "Direto do Produtor", "750", "g", "package", "7.50", "8.25", 1},
		{"Banana Prata Baby 600g Bdj", "", "600", "g", "package", "6.00", "6.60", 1},
	}
	for position, listing := range listings {
		submitMassListing(fixture, position+1, listing)
	}
}

func submitMassListing(fixture fixture, identity int, listing massListing) {
	fixture.submit(identity*2, func(observation map[string]any) {
		setMassListing(observation, identity, listing)
		setPrice(observation, "2026-10-27T12:00:00Z", listing.first)
	})
	fixture.submit(identity*2+1, func(observation map[string]any) {
		setMassListing(observation, identity, listing)
		setPrice(observation, "2026-10-28T12:00:00Z", listing.last)
	})
}

func setMassListing(observation map[string]any, identity int, listing massListing) {
	product := observation["product"].(map[string]any)
	product["source_product_id"], product["name"], product["brand"], product["gtin"] = fmt.Sprint(identity), listing.name, listing.brand, nil
	if listing.brand == "" {
		product["brand"] = nil
	}
	product["package"] = massPackage(listing)
	observation["offers"] = observation["offers"].([]any)[:1]
	offer := observation["offers"].([]any)[0].(map[string]any)
	offer["basis"] = listing.basis
}

func massPackage(listing massListing) any {
	if listing.quantity == "" {
		return nil
	}
	return map[string]any{"quantity": listing.quantity, "unit": listing.unit, "count": listing.count}
}

func assertBananaGroups(fixture fixture) {
	fixture.test.Helper()
	var products Products
	fixture.get("/api/v1/products?q=Banana%20prata", &products)
	if len(products.Items) != 4 {
		fixture.test.Fatalf("expected conventional, organic, licensed and baby groups: %+v", products)
	}
	if products.Items[0].Label != "Banana prata" {
		fixture.test.Fatalf("retailer brand or sale weight leaked into generic label: %+v", products.Items[0])
	}
}

func assertBananaMassHistory(fixture fixture) {
	fixture.test.Helper()
	history := fixture.history("1", "2026-10-27", "2026-10-28")
	if history.Title != "Banana prata" || history.PriceBasis == nil || *history.PriceBasis != "kg" || len(history.ShopPrices) != 4 {
		fixture.test.Fatalf("bad mass group history: %+v", history)
	}
	assertPrice(fixture.test, history.Points[0].Value, 1000)
	assertPrice(fixture.test, history.LatestPriceMinor, 1100)
	assertPrice(fixture.test, history.ChangeBasisPoints, 1000)
	for _, shop := range history.ShopPrices {
		assertPrice(fixture.test, shop.Points[0].Value, 1000)
		assertPrice(fixture.test, shop.Points[1].Value, 1100)
	}
	assertDailyOverview(fixture, "2026-10-27", "2026-10-28", "")
}

func assertDeclaredMassSafety(fixture fixture) {
	fixture.test.Helper()
	var valid bool
	requireSuccess(fixture.test, fixture.pool.QueryRowContext(fixture.ctx, `SELECT
 declared_mass_grams('Banana prata 1,1kg')=1100 AND declared_mass_grams('Banana prata 1k')=1000
 AND declared_mass_grams('Banana prata 750g')=750
 AND declared_mass_grams('Banana prata aproximadamente 150g') IS NULL
 AND declared_mass_grams('Banana prata 150g/un') IS NULL
 AND declared_mass_grams('Banana prata 2x750g') IS NULL
 AND package_mass_grams(500,'g',2)=1000
 AND package_mass_grams(1,'unit',1) IS NULL`).Scan(&valid))
	if !valid {
		fixture.test.Fatal("unknown or approximate package mass inferred")
	}
}

func TestMassGroupingNormalizesPackageChangesAndConditions(test *testing.T) {
	fixture := newFixture(test)
	listing := massListing{"Banana Prata 1kg", "GERAL", "1", "kg", "package", "10.00", "10.00", 1}
	fixture.submit(1, func(observation map[string]any) {
		setMassListing(observation, 1, listing)
		setPrice(observation, "2026-10-27T12:00:00Z", "10.00")
	})
	fixture.submit(2, changedBananaPackage)
	assertChangedBananaPackage(fixture)
	requireSuccess(test, dailysummary.Refresh(fixture.ctx, fixture.pool))
	assertChangedBananaPackage(fixture)
	assertDailyOverview(fixture, "2026-10-27", "2026-10-28", "")
}

func changedBananaPackage(observation map[string]any) {
	listing := massListing{"Banana Prata 750g", "GERAL", "750", "g", "package", "", "", 1}
	setMassListing(observation, 1, listing)
	setPrice(observation, "2026-10-28T12:00:00Z", "7.50")
	offer := observation["offers"].([]any)[0].(map[string]any)
	conditions := offer["conditions"].(map[string]any)
	conditions["payment_method"] = "unknown"
	conditions["coupon_required"], conditions["membership_required"], conditions["minimum_quantity"] = nil, nil, nil
}

func assertChangedBananaPackage(fixture fixture) {
	fixture.test.Helper()
	history := fixture.history("1", "2026-10-28", "2026-10-28")
	assertPrice(fixture.test, history.LatestPriceMinor, 1000)
	if !history.UnknownConditions {
		fixture.test.Fatal("converted package hid unknown restrictions")
	}
	history = fixture.history("1", "2026-10-27", "2026-10-28")
	if len(history.Points) != 1 || history.Counts.PricedDays != 1 || history.ChangeBasisPoints != nil {
		fixture.test.Fatal("unknown conditions bypassed the interval's unrestricted-offer policy")
	}
	assertDailyOverview(fixture, "2026-10-28", "2026-10-28", "")
}

func TestAutomaticMeatGroupingAndMassConversion(test *testing.T) {
	fixture := newFixture(test)
	seedMeatMassListings(fixture)
	assertMeatMassHistory(fixture, "1", "Acém moído resfriado", 2, 1100)
	assertMeatMassHistory(fixture, "4", "Picanha resfriada", 2, 2200)
	requireSuccess(test, dailysummary.Refresh(fixture.ctx, fixture.pool))
	assertMeatMassHistory(fixture, "1", "Acém moído resfriado", 2, 1100)
	assertDailyOverview(fixture, "2026-10-27", "2026-10-28", "")
	var products Products
	fixture.get("/api/v1/products", &products)
	if len(products.Items) != 6 {
		test.Fatalf("meat cut, species or bone status lost: %+v", products)
	}
}

func seedMeatMassListings(fixture fixture) {
	listings := []massListing{
		{"Carne Moída De Acém Bovina Resfriada 500g", "Bovino in Natura", "500", "g", "package", "5.00", "5.50", 1},
		{"Carne Bovina Moída Acém Resfriada Kg", "Açougue", "", "", "kg", "10.00", "11.00", 0},
		{"Carne Moída De Patinho Bovina Resfriada 500g", "Açougue", "500", "g", "package", "5.00", "5.50", 1},
		{"Picanha Resfriada 1kg", "GERAL", "1", "kg", "package", "20.00", "22.00", 1},
		{"Picanha Bovina Resfriada 750g", "Bandeiras", "750", "g", "package", "15.00", "16.50", 1},
		{"Picanha Suína Resfriada Kg", "Açougue", "", "", "kg", "10.00", "11.00", 0},
		{"Acém com Osso 1kg", "Açougue", "1", "kg", "package", "8.00", "8.80", 1},
		{"Acém sem Osso Kg", "Açougue", "", "", "kg", "8.00", "8.80", 0},
	}
	for position, listing := range listings {
		submitMassListing(fixture, position+1, listing)
	}
}

func assertMeatMassHistory(fixture fixture, identity, name string, contexts int, latest int64) {
	fixture.test.Helper()
	history := fixture.history(identity, "2026-10-27", "2026-10-28")
	if history.PriceBasis == nil || *history.PriceBasis != "kg" || history.Title != name || len(history.ShopPrices) != contexts {
		fixture.test.Fatalf("incorrect meat grouping: %+v", history)
	}
	assertPrice(fixture.test, history.LatestPriceMinor, latest)
	assertPrice(fixture.test, history.ChangeBasisPoints, 1000)
}
