package historyprecompute

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"time"

	"inflacao-real/core/internal/insights"
	"inflacao-real/core/internal/webapi"
)

func (store *Store) savedHistory(requestContext context.Context, request webapi.HistoryRequest, revision int64) (insights.History, error) {
	history, err := store.lookup(requestContext, request, revision)
	if err == nil || !errors.Is(err, sql.ErrNoRows) || request.Product != "global" {
		return history, err
	}
	history, err = store.previousOverview(requestContext, request)
	if err != nil {
		return history, err
	}
	if err := store.seed(requestContext, request); err != nil {
		return history, err
	}
	store.notify()
	return history, nil
}

func (store *Store) previousOverview(requestContext context.Context, request webapi.HistoryRequest) (insights.History, error) {
	identity, _ := selectionIdentity(request)
	previousIdentity, _ := selectionIdentity(previousDefault(request))
	var data []byte
	err := store.database.QueryRowContext(requestContext, `UPDATE history_precomputations SET requested_at=now()
 WHERE identity=(SELECT identity FROM history_precomputations WHERE identity IN ($1,$2)
 AND result IS NOT NULL ORDER BY (identity=$1) DESC LIMIT 1)
 RETURNING result`, identity, previousIdentity).Scan(&data)
	if err != nil {
		return insights.History{}, err
	}
	var history insights.History
	err = json.Unmarshal(data, &history)
	history.Processing = true
	return history, err
}

// Only roll the default month window back; custom filters never borrow another period.
func previousDefault(request webapi.HistoryRequest) webapi.HistoryRequest {
	location, _ := time.LoadLocation("America/Sao_Paulo")
	end, err := time.ParseInLocation(time.DateOnly, request.End, location)
	if err != nil || request.Start != previousMonth(end).Format(time.DateOnly) {
		return request
	}
	yesterday := end.AddDate(0, 0, -1)
	request.Start = previousMonth(yesterday).Format(time.DateOnly)
	request.End = yesterday.Format(time.DateOnly)
	return request
}
