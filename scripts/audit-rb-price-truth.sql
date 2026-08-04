\set ON_ERROR_STOP on
\pset format unaligned
\pset tuples_only on

WITH rb AS (
    SELECT id, currency_code
    FROM sites
    WHERE key = 'microchips-by'
),
one_c AS (
    SELECT *
    FROM one_c_nomenclature_items
    WHERE is_group = false
),
eligible_one_c AS (
    SELECT one_c.*
    FROM one_c, rb
    WHERE one_c.price > 0
      AND one_c.currency = rb.currency_code
      AND nullif(btrim(one_c.price_type), '') IS NOT NULL
      AND one_c.updated_at IS NOT NULL
),
rb_products AS (
    SELECT
        site_products.id AS site_product_id,
        site_products.is_published,
        site_products.price AS visible_price,
        products.id AS product_id,
        products.external_id,
        products.sku,
        products.mpn,
        products.manufacturer
    FROM rb
    JOIN site_products ON site_products.site_id = rb.id
    JOIN products ON products.id = site_products.product_id
),
direct_all AS (
    SELECT rb_products.*, one_c.price AS source_price,
           one_c.currency AS source_currency, one_c.price_type,
           one_c.updated_at AS observed_at
    FROM rb_products
    JOIN one_c ON one_c.external_id = rb_products.external_id
),
direct_eligible AS (
    SELECT rb_products.*, eligible_one_c.price AS source_price,
           eligible_one_c.price_type, eligible_one_c.updated_at AS observed_at
    FROM rb_products
    JOIN eligible_one_c ON eligible_one_c.external_id = rb_products.external_id
),
current_evidence AS (
    SELECT evidences.*
    FROM rb
    JOIN site_product_price_evidences AS evidences ON evidences.site_id = rb.id
    WHERE evidences.is_current = true
),
approved AS (
    SELECT candidates.*, one_c.external_id AS one_c_external_id,
           one_c.price AS one_c_price, one_c.currency AS one_c_currency,
           one_c.price_type AS one_c_price_type
    FROM catalog_identity_candidates AS candidates
    JOIN one_c ON one_c.id = candidates.one_c_nomenclature_item_id
    WHERE candidates.review_status = 'approved_for_staging'
)
SELECT jsonb_pretty(jsonb_build_object(
    'generated_at', now(),
    'site', 'microchips-by',
    'one_c_inventory', jsonb_build_object(
        'nongroup_rows', (SELECT count(*) FROM one_c),
        'positive_price_rows', (SELECT count(*) FROM one_c WHERE price > 0),
        'currency_present_rows', (SELECT count(*) FROM one_c WHERE nullif(btrim(currency), '') IS NOT NULL),
        'price_type_present_rows', (SELECT count(*) FROM one_c WHERE nullif(btrim(price_type), '') IS NOT NULL),
        'fully_eligible_byn_rows', (SELECT count(*) FROM eligible_one_c),
        'source_payload_positive_price_rows', (
            SELECT count(*)
            FROM one_c
            WHERE CASE
                WHEN replace(replace(btrim(source_payload ->> 'price'), ' ', ''), ',', '.') ~ '^[0-9]+([.][0-9]+)?$'
                    THEN replace(replace(btrim(source_payload ->> 'price'), ' ', ''), ',', '.')::numeric > 0
                ELSE false
            END
        ),
        'source_payload_currency_rows', (SELECT count(*) FROM one_c WHERE nullif(btrim(source_payload ->> 'currency'), '') IS NOT NULL),
        'source_payload_price_type_rows', (SELECT count(*) FROM one_c WHERE nullif(btrim(source_payload ->> 'price_type'), '') IS NOT NULL),
        'latest_updated_at', (SELECT max(updated_at) FROM one_c),
        'import_run_ids', (SELECT jsonb_agg(DISTINCT import_run_id ORDER BY import_run_id) FROM one_c),
        'import_runs', (
            SELECT coalesce(jsonb_agg(to_jsonb(run) ORDER BY run.id), '[]'::jsonb)
            FROM (
                SELECT id, source, source_file, status, total_records,
                       processed_records, failed_records, started_at, finished_at
                FROM import_runs
                WHERE id IN (SELECT DISTINCT import_run_id FROM one_c)
            ) AS run
        )
    ),
    'rb_site', jsonb_build_object(
        'site_products', (SELECT count(*) FROM rb_products),
        'published_site_products', (SELECT count(*) FROM rb_products WHERE is_published),
        'visible_numeric_prices', (SELECT count(*) FROM rb_products WHERE visible_price > 0),
        'published_visible_numeric_prices', (SELECT count(*) FROM rb_products WHERE is_published AND visible_price > 0),
        'current_price_evidence_rows', (SELECT count(*) FROM current_evidence),
        'current_one_c_x2_evidence_rows', (SELECT count(*) FROM current_evidence WHERE source = 'one_c_x2'),
        'current_legacy_site_evidence_rows', (SELECT count(*) FROM current_evidence WHERE source = 'legacy_site')
        , 'current_evidence_oldest_observed_at', (SELECT min(observed_at) FROM current_evidence)
        , 'current_evidence_newest_observed_at', (SELECT max(observed_at) FROM current_evidence)
    ),
    'stable_identity_links', jsonb_build_object(
        'direct_external_id_to_one_c_total', (SELECT count(*) FROM direct_all),
        'direct_external_id_with_sku_or_mpn', (SELECT count(*) FROM direct_all WHERE nullif(btrim(sku), '') IS NOT NULL OR nullif(btrim(mpn), '') IS NOT NULL),
        'direct_external_id_to_eligible_one_c', (SELECT count(*) FROM direct_eligible),
        'direct_with_sku_or_mpn', (SELECT count(*) FROM direct_eligible WHERE nullif(btrim(sku), '') IS NOT NULL OR nullif(btrim(mpn), '') IS NOT NULL),
        'approved_candidates_total', (SELECT count(*) FROM approved),
        'approved_candidates_with_positive_price', (SELECT count(*) FROM approved WHERE one_c_price > 0),
        'approved_candidates_fully_eligible_byn', (SELECT count(*) FROM approved WHERE one_c_price > 0 AND one_c_currency = (SELECT currency_code FROM rb) AND nullif(btrim(one_c_price_type), '') IS NOT NULL)
    ),
    'integrity', jsonb_build_object(
        'visible_price_without_current_evidence', (
            SELECT count(*) FROM rb_products
            LEFT JOIN current_evidence ON current_evidence.site_product_id = rb_products.site_product_id
            WHERE rb_products.visible_price > 0 AND current_evidence.id IS NULL
        ),
        'current_evidence_visible_price_mismatch', (
            SELECT count(*) FROM current_evidence
            JOIN rb_products ON rb_products.site_product_id = current_evidence.site_product_id
            WHERE rb_products.visible_price IS DISTINCT FROM current_evidence.calculated_price
        ),
        'duplicate_current_evidence_products', (
            SELECT count(*) FROM (
                SELECT site_product_id FROM current_evidence GROUP BY site_product_id HAVING count(*) > 1
            ) duplicates
        )
    ),
    'safe_next_one_c_x2_batch', (
        SELECT coalesce(jsonb_agg(to_jsonb(sample) ORDER BY sample.external_id), '[]'::jsonb)
        FROM (
            SELECT external_id, manufacturer, sku, mpn, source_price,
                   round(source_price * 2, 2) AS calculated_price_byn,
                   price_type, observed_at, is_published, visible_price
            FROM direct_eligible
            ORDER BY external_id
            LIMIT 100
        ) AS sample
    )
));
