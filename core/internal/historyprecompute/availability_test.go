package historyprecompute

import (
	"errors"
	"testing"
	"time"

	"inflacao-real/core/internal/webapi"
)

func TestOverviewServesSavedResultWhileIngestionChangesRevision(test *testing.T) {
	fixture := newFixture(test)
	request := requestForTest()
	first, err := fixture.store.History(fixture.requestContext, request)
	requireSuccess(test, err)
	fixture.execute(`UPDATE catalog_decisions SET revision=revision+1`)
	fixture.execute(`INSERT INTO ingestion_payloads(scraper_id,submission_id,shop_id,schema_version,created_at,payload)
 VALUES('collector','00000000-0000-4000-8000-000000000001','shop','1.0',now(),'{}')`)
	fixture.source.failure = errors.New("must not calculate on the request path")
	saved, err := fixture.store.History(fixture.requestContext, request)
	requireSuccess(test, err)
	if saved.Title != first.Title || !saved.Processing || fixture.source.calls != 1 {
		test.Fatal("overview did not serve its previous persisted result")
	}
	verifyOverviewRefresh(test, fixture, first.Title)
}

func verifyOverviewRefresh(test *testing.T, fixture fixture, previousTitle string) {
	test.Helper()
	fixture.source.failure = nil
	fixture.execute(`UPDATE ingestion_payloads SET status='processed',processed_at=now()`)
	requireSuccess(test, fixture.store.Refresh(fixture.requestContext, time.Date(2026, 11, 1, 12, 0, 0, 0, time.UTC)))
	updated, err := fixture.store.History(fixture.requestContext, requestForTest())
	requireSuccess(test, err)
	if updated.Processing || updated.Title == previousTitle {
		test.Fatal("background refresh did not replace the saved result")
	}
}

func TestDefaultOverviewFallsBackAcrossDateRollover(test *testing.T) {
	fixture := newFixture(test)
	request := requestForTest()
	first, err := fixture.store.History(fixture.requestContext, request)
	requireSuccess(test, err)
	request.Start, request.End = "2026-10-02", "2026-11-02"
	fixture.source.failure = errors.New("must not calculate during date rollover")
	saved, err := fixture.store.History(fixture.requestContext, request)
	requireSuccess(test, err)
	if saved.Period != first.Period || !saved.Processing || fixture.source.calls != 1 {
		test.Fatal("date rollover lost the previous day's snapshot or its period")
	}
	verifySelectionQueued(test, fixture, request)
}

func verifySelectionQueued(test *testing.T, fixture fixture, request webapi.HistoryRequest) {
	test.Helper()
	var count int
	identity, _ := selectionIdentity(request)
	requireSuccess(test, fixture.database.QueryRowContext(fixture.requestContext,
		`SELECT count(*) FROM history_precomputations WHERE identity=$1 AND result IS NULL`, identity).Scan(&count))
	if count != 1 {
		test.Fatal("new date window was not queued for background refresh")
	}
}

func TestOverviewFallbackDoesNotCrossFilters(test *testing.T) {
	fixture := newFixture(test)
	request := requestForTest()
	_, err := fixture.store.History(fixture.requestContext, request)
	requireSuccess(test, err)
	fixture.source.failure = errors.New("no saved result for selection")
	request.Group = "doces"
	_, err = fixture.store.History(fixture.requestContext, request)
	if err == nil {
		test.Fatal("overview substituted a different product group")
	}
	request.Group, request.Start = "", "2026-10-02"
	_, err = fixture.store.History(fixture.requestContext, request)
	if err == nil {
		test.Fatal("overview substituted a custom period")
	}
}

func TestPreviousDefaultClampsMonthBoundary(test *testing.T) {
	request := requestForTest()
	request.Start, request.End = "2026-02-01", "2026-03-01"
	previous := previousDefault(request)
	if previous.Start != "2026-01-28" || previous.End != "2026-02-28" {
		test.Fatalf("incorrect previous default: %+v", previous)
	}
}
