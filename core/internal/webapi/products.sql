WITH eligible AS (
    SELECT coalesce(membership.representative_id, observation.product_id) AS product_id
    FROM price_observations observation
    LEFT JOIN product_equivalence membership ON membership.product_id = observation.product_id
    WHERE availability = 'in_stock' AND price_amount IS NOT NULL
    GROUP BY coalesce(membership.representative_id, observation.product_id),
        shop_product_id, seller_id, store_id, postal_code, city, state, channel
    HAVING count(DISTINCT (observed_at AT TIME ZONE 'America/Sao_Paulo')::date) >= 2
), search AS (
    SELECT btrim(product_search_text($3)) AS text,
        to_tsquery('simple', nullif(array_to_string(tsvector_to_array(
            to_tsvector('simple', product_search_text($3))), ':* & '), '') || ':*') AS query
), candidates AS (
    SELECT coalesce(membership.representative_id, member.id) AS product_id,
        btrim(product_search_text(member.name)) AS name
    FROM products member
    LEFT JOIN product_equivalence membership ON membership.product_id = member.id
    CROSS JOIN search
    WHERE $3::text = '' OR member.search_document @@ search.query
), ranked AS (
    SELECT product_id,
        CASE
            WHEN $3::text = '' OR name = search.text THEN 0
            WHEN starts_with(name, search.text || ' ') THEN 1
            WHEN starts_with(name, search.text) THEN 2
            WHEN to_tsvector('simple', name) @@ search.query THEN 3
            ELSE 4
        END AS match_priority,
        CASE WHEN $3::text = '' THEN 0
            ELSE cardinality(regexp_split_to_array(name, ' +')) END AS word_count
    FROM candidates CROSS JOIN search
), matching AS (
    -- An equivalence group inherits its best matching member's relevance.
    SELECT DISTINCT ON (product_id) product_id, match_priority, word_count
    FROM ranked
    ORDER BY product_id, match_priority, word_count
)
SELECT products.id::text, coalesce((SELECT comparison_name FROM product_equivalence WHERE product_id=products.id),
    products.name || coalesce(' · ' || products.brand, ''))
FROM products JOIN matching ON matching.product_id = products.id
WHERE ($1::bigint = 0 OR ($3::text = '' AND id > $1) OR ($3::text <> '' AND
        (match_priority, word_count, id) > (
            SELECT match_priority, word_count, product_id FROM matching WHERE product_id = $1)))
    AND id IN (SELECT product_id FROM eligible)
    AND (cardinality($4::text[]) = 0 OR id IN (
        SELECT equivalent_product_id(product_id) FROM product_monitoring_targets
        WHERE target_id = ANY($4::text[])))
ORDER BY match_priority, word_count, products.id
LIMIT $2
