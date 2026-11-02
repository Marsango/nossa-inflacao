 , bounds AS (
    SELECT min(day) FILTER (WHERE price IS NOT NULL) AS first_day,
        max(day) FILTER (WHERE price IS NOT NULL) AS last_day FROM latest
), baselines AS (
    SELECT DISTINCT ON (product_id,stream) product_id,stream,day AS baseline_day,price AS baseline
    FROM latest WHERE price>0 ORDER BY product_id,stream,day
), observed_pairs AS (
    SELECT latest.*,baseline_day,baseline,
        lead(day,1,last_day+1) OVER (PARTITION BY product_id,stream ORDER BY day) AS next_day
    FROM latest JOIN baselines USING(product_id,stream) CROSS JOIN bounds
    WHERE day>baseline_day AND price IS NOT NULL
), comparable AS (
    SELECT observed_pairs.*,calendar.day::date AS asof_day
    FROM observed_pairs CROSS JOIN LATERAL generate_series(day,next_day-1,interval '1 day') calendar(day)
), shop_weights AS (
    SELECT comparable.*, count(*) OVER (PARTITION BY asof_day,product_id,shop_id) AS contexts,
        dense_rank() OVER (PARTITION BY asof_day,product_id ORDER BY shop_id) AS shop_rank
    FROM comparable
), weighted_points AS (
    SELECT shop_weights.*,baseline*contexts*max(shop_rank) OVER (PARTITION BY asof_day,product_id) AS denominator
    FROM shop_weights
), terms AS (
    SELECT asof_day AS day,denominator,sum(price)*10000 AS numerator,count(*) AS priced_streams
    FROM weighted_points GROUP BY asof_day,denominator
), daily_counts AS (
    SELECT asof_day AS day,count(DISTINCT product_id) AS products,count(DISTINCT shop_id) AS shops,count(*) AS streams,
        min(baseline_day) AS comparison_start,max(day) AS comparison_end,
        count(*) FILTER (WHERE day=asof_day) AS updated_streams
    FROM comparable GROUP BY asof_day
), daily_coverage AS (
    SELECT calendar.day::date AS day,coalesce(products,0) AS products,coalesce(shops,0) AS shops,coalesce(streams,0) AS streams,
        comparison_start,comparison_end,coalesce(updated_streams,0) AS updated_streams
    FROM bounds CROSS JOIN LATERAL generate_series(first_day+1,last_day,interval '1 day') calendar(day)
    LEFT JOIN daily_counts ON daily_counts.day=calendar.day::date
), metadata AS (
    SELECT jsonb_build_object('counts',jsonb_build_object(
        'products',(SELECT count(*) FROM panel),'shops',(SELECT count(DISTINCT shop_id) FROM measurements),
        'streams',(SELECT coalesce(sum(streams),0) FROM panel),
        'includedProducts',(SELECT count(DISTINCT product_id) FROM comparable),
        'includedShops',(SELECT count(DISTINCT shop_id) FROM comparable),
        'includedStreams',(SELECT count(DISTINCT (product_id,stream)) FROM comparable)),
        'dailyComparisons',(SELECT coalesce(jsonb_agg(jsonb_build_object('date',day::text,
            'products',products,'shops',shops,'streams',streams,'comparisonStart',comparison_start::text,
            'comparisonEnd',comparison_end::text,'updatedStreams',updated_streams) ORDER BY day),'[]'::jsonb) FROM daily_coverage),
        'unknownConditions',(SELECT coalesce(bool_or(unknown_conditions),false) FROM panel),
        'collectedAt',(SELECT max(collected_at) FROM panel),
        'availablePeriod',CASE WHEN first_day IS NOT NULL THEN jsonb_build_object('start',first_day::text,'end',last_day::text) END,
        'locations',(SELECT jsonb_agg(DISTINCT coalesce(nullif(concat_ws('/',stream->>4,stream->>5),''),'localidade não informada')) FROM measurements)) AS data
    FROM bounds
)
SELECT 0 AS kind,NULL::text AS day,NULL::text AS denominator,NULL::text AS numerator,0::bigint AS priced_streams,data
FROM metadata
UNION ALL SELECT 1,day::text,denominator::text,numerator::text,priced_streams,NULL::jsonb FROM terms
ORDER BY kind,day,denominator;
