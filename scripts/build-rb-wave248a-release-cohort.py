#!/usr/bin/env python3
"""Build a read-only, no-repeat Wave248A B2B release cohort from live RB data.

The cohort is deliberately a research queue, not a publication manifest.  It
does not change product, media, price, SEO, or availability records.  It
selects cards where the useful text and a stable manufacturer/MPN identity
already exist, while published verified media is still missing.  That makes a
large external-image verification pass both commercially relevant and safe to
review without inventing product facts.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "audits" / "generated"
OUTPUT_JSON = GENERATED / "rb-wave248a-release-cohort-2026-07-30.json"
OUTPUT_CSV = GENERATED / "rb-wave248a-release-cohort-2026-07-30.csv"
SITE_KEY = "microchips-by"
LIMIT = 300

# These are the commercial groups requested for the next release-ready B2B
# queue.  Consumer electronics and the generic electronic-components group
# are intentionally absent.
CATEGORY_RANK = {
    "seo:ups-systems": 1,
    "seo:batteries-traction": 2,
    "seo:batteries-industrial": 3,
    "seo:replacement-batteries": 4,
    "seo:power-systems": 5,
    "seo:power-converters": 6,
    "seo:power-supplies": 7,
    "seo:batteries-ups": 8,
}

QUEUE_FILES = tuple(
    GENERATED / f"rb-enrichment-queue-wave{wave}.csv" for wave in (242, 243, 244, 245, 246)
)
DIRECT_RESEARCH_PATTERNS = (
    "rb-wave24[2-7]*-evidence-ledger.csv",
    "rb-wave24[2-7]*-decision-ledger.csv",
    "rb-wave24[2-7]*-scope.csv",
    "rb-wave24[2-7]*-exact-media-review.csv",
    "rb-reviewed-legacy-preview-media-wave246.csv",
)

CSV_FIELDS = [
    "cohort_order", "priority_band", "product_external_id", "product_id", "site_product_id",
    "name", "manufacturer", "mpn", "category_external_id", "category_name", "is_published",
    "is_indexable", "identity_ready", "description_ready", "description_characters",
    "verified_published_media_count", "current_price_evidence_count", "visible_price_byn",
    "availability", "completion_gap_count", "recommended_next_action", "no_repeat_basis",
]


class CohortError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def first_present(row: dict[str, str], *fields: str) -> str:
    for field in fields:
        value = (row.get(field) or "").strip()
        if value:
            return value
    return ""


def read_queues() -> tuple[set[str], dict[str, Any]]:
    """Return terminal research IDs from the latest known queue state.

    A historic queue is an inventory of candidates, not proof that every row
    was researched.  We therefore exclude only terminal statuses from the
    latest queue containing an ID.  This prevents both repeat work and the
    mistake of silently discarding still-pending cards.
    """
    latest: dict[str, str] = {}
    details: list[dict[str, Any]] = []
    for path in QUEUE_FILES:
        if not path.is_file():
            raise CohortError(f"required Wave242-246 queue missing: {path.name}")
        rows = read_csv(path)
        ids = [first_present(row, "product_external_id", "external_id") for row in rows]
        if not rows or any(not value for value in ids) or len(ids) != len(set(ids)):
            raise CohortError(f"invalid unique product IDs in {path.name}")
        for row, external_id in zip(rows, ids):
            latest[external_id] = (row.get("research_status") or "").strip()
        details.append({"path": path.relative_to(ROOT).as_posix(), "rows": len(rows), "sha256": sha256(path)})

    allowed_pending = {
        "pending_official_source_research",
        "new_after_verified_duplicate_retirement",
    }
    terminal = {external_id for external_id, status in latest.items() if status not in allowed_pending}
    return terminal, {
        "files": details,
        "latest_status_rows": len(latest),
        "latest_terminal_status_rows": len(terminal),
        "allowed_not_yet_researched_statuses": sorted(allowed_pending),
    }


def read_direct_research_ids() -> tuple[set[str], list[dict[str, str]]]:
    """Collect actual ledger/scope decisions, never broad exclusion ledgers."""
    paths = sorted({path for pattern in DIRECT_RESEARCH_PATTERNS for path in GENERATED.glob(pattern) if path.is_file()})
    if not paths:
        raise CohortError("no direct Wave242-247 research artifacts found")
    ids: set[str] = set()
    pins: list[dict[str, str]] = []
    identifier_fields = ("product_external_id", "external_id", "source_external_id", "duplicate_external_id")
    for path in paths:
        rows = read_csv(path)
        found = 0
        for row in rows:
            external_id = first_present(row, *identifier_fields)
            # Manufacturer identifiers and prices are not product identities.
            if external_id and (external_id.startswith("bitrix:") or external_id.startswith("manufacturer:") or "-" in external_id):
                ids.add(external_id)
                found += 1
        pins.append({
            "path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path),
            "rows": str(len(rows)), "recognized_product_ids": str(found),
        })
    return ids, pins


def query_live_snapshot() -> dict[str, Any]:
    """Read the exact card-quality fields from the running database only."""
    categories = ",".join(repr(value) for value in CATEGORY_RANK)
    php = f'''
$site=app('db')->table('sites')->where('key','{SITE_KEY}')->first(['id','key','currency_code']);
if (!$site) {{ throw new RuntimeException('microchips-by site missing'); }}
$rows=app('db')->table('site_products as sp')
 ->join('products as p','p.id','=','sp.product_id')
 ->join('site_category_product as scp','scp.site_product_id','=','sp.id')
 ->join('site_categories as sc','sc.id','=','scp.site_category_id')
 ->join('site_seos as seo',function($join) use($site) {{$join->on('seo.resource_id','=','sp.id')->where('seo.site_id',$site->id)->where('seo.resource_type','product');}})
 ->where('sp.site_id',$site->id)->where('sp.is_published',true)->where('seo.is_indexable',false)
 ->whereIn('sc.external_id',[{categories}])
 ->orderBy('p.external_id')->get([
   'p.id as product_id','p.external_id','p.name','p.manufacturer','p.mpn',
   'p.short_description','sp.id as site_product_id','sp.is_published','sp.price',
   'sp.availability','sc.external_id as category_external_id','sc.name as category_name',
   app('db')->raw("(select count(*) from product_media pm where pm.product_id=p.id and pm.is_published=true and pm.verification_status='verified') as verified_published_media_count"),
   app('db')->raw("(select count(*) from site_product_price_evidences pe where pe.site_product_id=sp.id and pe.site_id={{$site->id}} and pe.is_current=true) as current_price_evidence_count")
 ]);
echo json_encode(['site_key'=>$site->key,'currency'=>$site->currency_code,'rows'=>$rows],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
'''
    encoded = base64.b64encode(php.encode("utf-8")).decode("ascii")
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}')); "],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0 or not result.stdout.strip().startswith("{"):
        raise CohortError(f"live read-only cohort query failed: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def integer(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise CohortError(f"invalid integer quality field: {value!r}") from error


def normalise_rows(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if snapshot.get("site_key") != SITE_KEY or snapshot.get("currency") != "BYN":
        raise CohortError("expected live RB site with BYN currency")
    raw_rows = snapshot.get("rows")
    if not isinstance(raw_rows, list):
        raise CohortError("live snapshot rows must be a list")

    # A product can have legacy secondary category bindings.  Preserve just the
    # highest business-priority B2B category deterministically.
    chosen: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        if not isinstance(row, dict):
            raise CohortError("live snapshot contains a non-object row")
        external_id = str(row.get("external_id") or "").strip()
        category = str(row.get("category_external_id") or "").strip()
        if not external_id or category not in CATEGORY_RANK:
            raise CohortError("live snapshot has blank external ID or unsupported category")
        prior = chosen.get(external_id)
        if prior is None or CATEGORY_RANK[category] < CATEGORY_RANK[str(prior["category_external_id"])]:
            chosen[external_id] = row
    return list(chosen.values())


def build(snapshot: dict[str, Any]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    terminal_queue_ids, queue_info = read_queues()
    direct_research_ids, direct_pins = read_direct_research_ids()
    rows = normalise_rows(snapshot)
    candidates: list[dict[str, Any]] = []
    excluded = Counter()
    for row in rows:
        external_id = str(row["external_id"]).strip()
        manufacturer = str(row.get("manufacturer") or "").strip()
        mpn = str(row.get("mpn") or "").strip()
        description = str(row.get("short_description") or "").strip()
        media = integer(row.get("verified_published_media_count"))
        price_evidence = integer(row.get("current_price_evidence_count"))
        identity_ready = bool(manufacturer and mpn)
        description_ready = len(description) >= 120
        if external_id in direct_research_ids:
            excluded["direct_wave242_247_research_evidence"] += 1
            continue
        if external_id in terminal_queue_ids:
            excluded["terminal_wave242_246_queue_status"] += 1
            continue
        if not identity_ready:
            excluded["identity_not_ready"] += 1
            continue
        if not description_ready:
            excluded["description_not_ready"] += 1
            continue
        if media > 0:
            excluded["verified_media_already_present"] += 1
            continue
        row = dict(row)
        row["identity_ready"] = identity_ready
        row["description_ready"] = description_ready
        row["description_characters"] = len(description)
        row["media"] = media
        row["price_evidence"] = price_evidence
        candidates.append(row)

    # Exact identity + text exists; media is the single critical gap.  Current
    # price evidence raises business utility but never changes publication
    # eligibility or allows an Offer schema by itself.
    candidates.sort(key=lambda row: (
        CATEGORY_RANK[str(row["category_external_id"])],
        -integer(row["price_evidence"]),
        -int(row["description_characters"]),
        str(row["manufacturer"]).casefold(),
        str(row["mpn"]).casefold(),
        str(row["external_id"]),
    ))
    selected = candidates[:LIMIT]
    if not (200 <= len(selected) <= 500):
        raise CohortError(f"Wave248A must contain 200-500 rows; selected {len(selected)}")
    ids = [str(row["external_id"]) for row in selected]
    if len(ids) != len(set(ids)):
        raise CohortError("selected product external IDs are not unique")

    output: list[dict[str, str]] = []
    for index, row in enumerate(selected, start=1):
        price_evidence = integer(row["price_evidence"])
        output.append({
            "cohort_order": str(index),
            "priority_band": f"b2b_category_{CATEGORY_RANK[str(row['category_external_id'])]}",
            "product_external_id": str(row["external_id"]),
            "product_id": str(row["product_id"]),
            "site_product_id": str(row["site_product_id"]),
            "name": str(row["name"]),
            "manufacturer": str(row["manufacturer"]),
            "mpn": str(row["mpn"]),
            "category_external_id": str(row["category_external_id"]),
            "category_name": str(row["category_name"]),
            "is_published": "true" if truth(row["is_published"]) else "false",
            "is_indexable": "false",
            "identity_ready": "true",
            "description_ready": "true",
            "description_characters": str(row["description_characters"]),
            "verified_published_media_count": str(row["media"]),
            "current_price_evidence_count": str(price_evidence),
            "visible_price_byn": str(row.get("price") or ""),
            "availability": str(row.get("availability") or ""),
            "completion_gap_count": "1",
            "recommended_next_action": "FIND_AND_VISUALLY_VERIFY_EXACT_RIGHTS_CLEARED_MEDIA",
            "no_repeat_basis": "not_in_direct_wave242_247_research_evidence_and_not_terminal_wave242_246_status",
        })

    summary: dict[str, Any] = {
        "schema_version": 1,
        "wave": "wave248a_b2b_release_cohort",
        "as_of": "2026-07-30",
        "mode": "live_database_read_only",
        "site_key": SITE_KEY,
        "selection_policy": {
            "target_rows": LIMIT,
            "allowed_range": [200, 500],
            "categories_in_priority_order": list(CATEGORY_RANK),
            "excluded_categories": ["seo:electronic-components"],
            "required": ["published", "noindex", "manufacturer+mpn identity", "description >= 120 chars", "no verified published media"],
            "next_action": "exact official or rights-cleared product media only; visual verification required before any publication",
        },
        "quality": {
            "identity_ready": len(output),
            "description_ready": len(output),
            "verified_published_media_missing": len(output),
            "with_current_price_evidence": sum(integer(row["current_price_evidence_count"]) > 0 for row in output),
            "visible_numeric_price": sum(bool(row["visible_price_byn"]) for row in output),
            "offer_schema_enabled": 0,
            "database_mutations": 0,
            "network_requests": 0,
        },
        "category_distribution": dict(sorted(Counter(row["category_external_id"] for row in output).items())),
        "manufacturer_distribution": dict(sorted(Counter(row["manufacturer"] for row in output).items())),
        "candidate_pool_after_quality_and_no_repeat": len(candidates),
        "excluded": dict(sorted(excluded.items())),
        "no_repeat": {
            "queue_state": queue_info,
            "direct_research_artifacts": direct_pins,
            "direct_research_ids": len(direct_research_ids),
            "terminal_queue_ids": len(terminal_queue_ids),
            "selected_overlap_direct_research": len(set(ids) & direct_research_ids),
            "selected_overlap_terminal_queue": len(set(ids) & terminal_queue_ids),
        },
        "records": output,
    }
    if summary["no_repeat"]["selected_overlap_direct_research"] or summary["no_repeat"]["selected_overlap_terminal_queue"]:
        raise CohortError("no-repeat guard failed")
    return output, summary


def write_outputs(rows: list[dict[str, str]], summary: dict[str, Any], output_dir: Path = GENERATED) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / OUTPUT_CSV.name
    json_path = output_dir / OUTPUT_JSON.name
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary["outputs"] = {
        "csv": {"path": csv_path.relative_to(ROOT).as_posix(), "sha256": sha256(csv_path), "rows": len(rows)},
        "json": {"path": json_path.relative_to(ROOT).as_posix()},
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, help="JSON snapshot used instead of the live read-only Docker query")
    parser.add_argument("--output-dir", type=Path, default=GENERATED)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else query_live_snapshot()
    rows, summary = build(snapshot)
    write_outputs(rows, summary, args.output_dir)
    print(json.dumps({"rows": len(rows), "categories": summary["category_distribution"], "database_mutations": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
