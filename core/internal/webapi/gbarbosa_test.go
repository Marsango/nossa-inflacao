package webapi

import (
	"strings"
	"testing"

	"inflacao-real/core/internal/ingestion"
)

func newGBarbosaFixture(test *testing.T) fixture {
	fixture := newFixture(test)
	fixture.execute(`INSERT INTO shops VALUES ('gbarbosa','GBarbosa','https://www.gbarbosa.com.br')`)
	router, err := ingestion.NewRouter(ingestion.PostgresStore{DB: fixture.pool}, ingestion.Auth{
		Token: "test", ScraperID: "collector-sp-01", ShopIDs: []string{"gbarbosa"}})
	requireSuccess(test, err)
	RegisterRoutes(router, PostgresStore{DB: fixture.pool})
	fixture.router = router
	return fixture
}

func TestCapturedGBarbosaRegionsSurviveIngestionAndWebHistory(test *testing.T) {
	fixture := newGBarbosaFixture(test)
	fixture.submitStoreSource(1, "2026-11-10T12:00:00Z", "gbarbosa-submission")
	var products Products
	fixture.get("/api/v1/products", &products)
	if len(products.Items) != 0 {
		test.Fatal("one local date must not qualify GBarbosa for search")
	}
	fixture.submitStoreSource(2, "2026-11-11T12:00:00Z", "gbarbosa-submission")
	fixture.get("/api/v1/products", &products)
	if len(products.Items) != 3 {
		test.Fatalf("expected rice, banana and beef after two dates; got %+v", products)
	}
	assertGBarbosaRegionalHistory(fixture, products)
	assertGBarbosaPersistedPrices(fixture)
}

func assertGBarbosaRegionalHistory(fixture fixture, products Products) {
	for _, product := range products.Items {
		assertGBarbosaProductHistory(fixture, product)
	}
}

func assertGBarbosaProductHistory(fixture fixture, product Product) {
	history := fixture.history(product.ID, "2026-11-10", "2026-11-11")
	if !history.UnknownConditions || len(history.ShopPrices) != 3 {
		fixture.test.Fatalf("regional prices or unknown conditions lost: %+v", history)
	}
	for _, city := range []string{"Aracaju/SE", "Salvador/BA", "Maceió/AL"} {
		assertGBarbosaCityCoverage(fixture, history.Coverage, city)
	}
}

func assertGBarbosaCityCoverage(fixture fixture, coverage, city string) {
	if !strings.Contains(coverage, city) {
		fixture.test.Fatalf("GBarbosa coverage lost %s: %s", city, coverage)
	}
}

func assertGBarbosaPersistedPrices(fixture fixture) {
	pool := fixture.pool
	row := pool.QueryRowContext(fixture.ctx, `SELECT count(DISTINCT store_id)=3 AND bool_and(
		channel='delivery' AND seller_id='1' AND membership_required IS NULL AND coupon_required IS NULL
		AND ((city='Aracaju' AND state='SE' AND postal_code='49026010' AND price_amount=5.99)
		OR (city='Salvador' AND state='BA' AND postal_code='41820020' AND price_amount=6.59)
		OR (city='Maceió' AND state='AL' AND postal_code='57035000' AND price_amount=6.69)))
		FROM price_observations JOIN shop_products listing ON listing.id=shop_product_id
		WHERE listing.source_product_id='13504'`)
	var preserved bool
	requireSuccess(fixture.test, row.Scan(&preserved))
	if !preserved {
		fixture.test.Fatal("GBarbosa exact regional prices or provenance lost during ingestion")
	}
	assertGBarbosaKilogramBasis(fixture)
}

func assertGBarbosaKilogramBasis(fixture fixture) {
	pool := fixture.pool
	row := pool.QueryRowContext(fixture.ctx, `SELECT count(*)=12 AND bool_and(
		price_basis='kg' AND package_quantity IS NULL AND package_unit IS NULL
		AND ((listing.source_product_id='6294' AND price_amount IN (3.59,4.99))
		OR (listing.source_product_id='12973' AND price_amount IN (45.79,39.99))))
		FROM price_observations JOIN shop_products listing ON listing.id=shop_product_id
		WHERE listing.source_product_id IN ('6294','12973')`)
	var preserved bool
	requireSuccess(fixture.test, row.Scan(&preserved))
	if !preserved {
		fixture.test.Fatal("GBarbosa kilogram prices became portion totals or fixed packages")
	}
}
