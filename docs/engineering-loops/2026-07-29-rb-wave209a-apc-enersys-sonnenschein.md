# RB Wave209-A — APC, EnerSys and Sonnenschein official identity gate

Date: 2026-07-29  
Scope: 163 rows from `rb-b2b-next-source-batch-wave208.csv` — APC 77, EnerSys 42 and Sonnenschein 44.

## Outcome

The final evidence CSV keeps every source-batch row and fails closed outside the exact-safe subset:

| Partition | Rows |
|---|---:|
| `exact_safe` | 70 |
| `conflict` | 57 |
| `no_evidence` | 35 |
| `compatibility` | 1 |

Only the 70 `safe_to_apply=true` rows are present in the OEM identity manifest. No price, stock, media, technical-claim or publication change is authorized.

## Evidence and guards

- EnerSys and Sonnenschein use only SHA-256-pinned PDFs from `www.enersys.com` and `www.exidegroup.com`; retailer, compatibility and family-only evidence remains outside the manifest.
- The APC set is exactly the pinned Wave199 candidate set: 77 external IDs, names and model tokens all match.
- The complete 17,207-row canonical registry supplied the first collision guard; six candidates have canonical identity peers and are held.
- A current Docker PostgreSQL scan checked 76 pre-live-safe normalized MPNs against every other product's `sku_normalized` and `mpn_normalized`; six live collisions are retained in `wave209a-live-identity-collisions.json` and excluded.
- Twenty-eight legacy APC titles differ from the current pinned product name and are held. Three APCRBC rows are additionally held because Laravel's bounded matcher rejects the preceding attached `APC` prefix before it reaches the standalone manufacturer token.

## Laravel dry-run

`catalog:apply-verified-oem-identities` ran without `--apply` against the final 70-row manifest:

- exit code: 0;
- mode: `dry_run`;
- identities filled / unchanged: 0 / 0;
- commercial and publication fields changed: 0 / 0;
- database mutations: 0.

After an independent dry-run against the same SHA-256 manifest, import run
**933** applied all 70 identities. The idempotence rerun returned **0 filled /
70 unchanged**. Price, availability, media, technical data and publication
fields changed: **0**.

## Verification

```text
python scripts/build-rb-wave209a-official-evidence.py ...
python -m pytest scripts/tests/test_build_rb_wave209a_official_evidence.py -q -p no:cacheprovider
# 4 passed
```

Final SEO audit after application: **16,853 URLs, 97 redirects, 0 blockers**.

Artifacts:

- `docs/audits/generated/rb-wave209a-official-evidence.csv`
- `docs/audits/generated/rb-wave209a-official-evidence.summary.json`
- `docs/audits/generated/wave209a-live-identity-collisions.json`
- `docs/audits/generated/wave209a-laravel-dry-run.json`
- `docs/imports/rb-verified-oem-identities-wave209a-2026-07-29.json`
