-- +goose Up
ALTER TABLE product_equivalence ADD COLUMN comparison_basis text CHECK (comparison_basis = 'kg');
ALTER TABLE product_equivalence ADD COLUMN comparison_name text;

-- A title fallback requires one explicit, trailing mass. Approximate portions,
-- multiple quantities and per-item estimates do not establish a package mass.
-- +goose StatementBegin
CREATE FUNCTION declared_mass_grams(value text) RETURNS numeric
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT CASE WHEN value !~* '(aprox|cerca|estimad|por unidade)' THEN
        replace(parts[1], ',', '.')::numeric * CASE lower(parts[2]) WHEN 'g' THEN 1 ELSE 1000 END END
    FROM regexp_match(value, '(?i)^[^0-9]*\m([0-9]+(?:[.,][0-9]{1,6})?)\s*(kg|g|k)\s*$') AS parts
$$;
-- +goose StatementEnd

-- +goose StatementBegin
CREATE FUNCTION package_mass_grams(quantity numeric, unit text, count integer) RETURNS numeric
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT CASE WHEN unit IN ('g','kg') AND quantity > 0 AND count > 0
        THEN quantity * count * CASE unit WHEN 'kg' THEN 1000 ELSE 1 END END
$$;
-- +goose StatementEnd

-- Enable the requested automatic rules on upgrade and for fresh installations.
-- Startup reconciliation backfills existing products; exclusions remain in force.
ALTER TABLE catalog_decisions ALTER COLUMN generic_enabled SET DEFAULT true;
UPDATE catalog_decisions SET generic_enabled=true, revision=revision+1;

-- +goose Down
ALTER TABLE catalog_decisions ALTER COLUMN generic_enabled SET DEFAULT false;
DROP FUNCTION package_mass_grams(numeric, text, integer), declared_mass_grams(text);
ALTER TABLE product_equivalence DROP COLUMN comparison_basis;
ALTER TABLE product_equivalence DROP COLUMN comparison_name;
