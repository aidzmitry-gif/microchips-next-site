#!/usr/bin/env python3
"""Read-only audit of deterministic local media for the Wave249 B2B gap.

The audit deliberately does not promote a legacy element attachment merely
because it belongs to that element.  A candidate passes only when local bytes,
rights, and exact model identity can all be proven without a visual guess.
Previously processed or held products/assets are excluded at product, media,
and content-hash level.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.util
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "audits" / "generated"
OUTPUT_JSON = GENERATED / "rb-wave250a-deterministic-media-audit-2026-07-30.json"
OUTPUT_CSV = GENERATED / "rb-wave250a-deterministic-media-candidates-2026-07-30.csv"
SOURCE_249 = ROOT / "scripts" / "build-rb-wave249a-indexable-b2b-cohort.py"
SOURCE_249_SHA256 = "272daa2febd9a69e880afa3a030f86f5469fcd793e1aff234d4f3aa318a3f0b1"
SITE_KEY = "microchips-by"

LEDGER_NAME = re.compile(
    r"(?:reviewed.*media|media.*review|media.*hold|media.*skip|media.*decision|"
    r"image.*review|image.*hold|image.*decision|media.*receipt|verified.*images|"
    r"blocked.*image|no-repeat)", re.IGNORECASE,
)
EXCLUDED_LEDGER_NAMES = {
    OUTPUT_JSON.name,
    OUTPUT_CSV.name,
    "bitrix-full-catalog-media-index.csv",
}

CSV_FIELDS = [
    "product_external_id", "product_id", "site_product_id", "name", "manufacturer", "mpn",
    "category_external_id", "canonical_path", "media_id", "storage_path", "content_sha256",
    "source_kind", "source_page_url", "source_asset_url", "rights_basis", "verification_status",
    "local_bytes_match", "hash_distinct_product_count", "verified_same_identity_hash_count",
    "no_repeat_status", "identity_evidence", "rights_evidence", "decision", "blocker",
]


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_wave249_module():
    if not SOURCE_249.is_file() or sha256(SOURCE_249) != SOURCE_249_SHA256:
        raise AuditError("Pinned Wave249 cohort builder drifted")
    spec = importlib.util.spec_from_file_location("wave249a", SOURCE_249)
    if spec is None or spec.loader is None:
        raise AuditError("Cannot load pinned Wave249 cohort builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integer(value: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise AuditError(f"Invalid integer field: {value!r}") from error


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def wave249_media_gap(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Reproduce the sequential Wave249 gates through the missing-media gate."""
    module = load_wave249_module()
    rows = module.choose_primary_categories(snapshot["rows"])
    gap: list[dict[str, Any]] = []
    for row in rows:
        manufacturer = str(row.get("manufacturer") or "").strip()
        mpn = str(row.get("mpn") or "").strip()
        description = str(row.get("short_description") or "").strip()
        if not truth(row.get("is_published")):
            continue
        if not manufacturer or not mpn or not str(row.get("manufacturer_normalized") or "").strip() or not str(row.get("mpn_normalized") or "").strip():
            continue
        if integer(row.get("identity_pair_catalogue_count")) != 1 or len(description) < 200:
            continue
        if integer(row.get("matching_applied_description_count")) < 1:
            continue
        provenance_ok, _, _ = module.provenance(row)
        if not provenance_ok or integer(row.get("verified_media_count")) != 0:
            continue
        # Wave249 checked these after media. Wave250 explicitly excludes cards
        # that have since become indexable or lost canonical cardinality.
        if integer(row.get("product_url_count")) != 1 or integer(row.get("seo_record_count")) != 1:
            continue
        if truth(row.get("url_is_indexable")) or truth(row.get("seo_is_indexable")):
            continue
        if str(row.get("product_path") or "") != str(row.get("seo_canonical_path") or ""):
            continue
        gap.append(dict(row))
    return gap


def walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def prior_no_repeat() -> tuple[set[str], set[tuple[str, int]], set[str], list[dict[str, Any]]]:
    external_ids: set[str] = set()
    pairs: set[tuple[str, int]] = set()
    hashes: set[str] = set()
    evidence: list[dict[str, Any]] = []
    roots = [GENERATED, ROOT / "docs" / "imports"]
    for root in roots:
        for path in sorted(root.glob("*")):
            if not path.is_file() or path.name in EXCLUDED_LEDGER_NAMES or not LEDGER_NAME.search(path.name):
                continue
            if path.suffix.lower() not in {".csv", ".json"}:
                continue
            rows: list[dict[str, Any]] = []
            try:
                if path.suffix.lower() == ".csv":
                    with path.open(encoding="utf-8-sig", newline="") as handle:
                        rows = [dict(row) for row in csv.DictReader(handle)]
                else:
                    rows = list(walk_json(json.loads(path.read_text(encoding="utf-8-sig"))))
            except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as error:
                raise AuditError(f"Cannot parse prior ledger {path.relative_to(ROOT)}: {error}") from error
            before = (len(external_ids), len(pairs), len(hashes))
            for row in rows:
                external = str(row.get("external_id") or row.get("product_external_id") or "").strip()
                media = str(row.get("media_id") or "").strip()
                digest = str(row.get("content_sha256") or row.get("candidate_sha256") or "").strip().lower()
                if external:
                    external_ids.add(external)
                if external and media.isdigit() and int(media) > 0:
                    pairs.add((external, int(media)))
                if re.fullmatch(r"[a-f0-9]{64}", digest):
                    hashes.add(digest)
            after = (len(external_ids), len(pairs), len(hashes))
            evidence.append({
                "path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path),
                "parsed_objects": len(rows), "new_external_ids": after[0] - before[0],
                "new_pairs": after[1] - before[1], "new_hashes": after[2] - before[2],
            })
    return external_ids, pairs, hashes, evidence


def query_media_snapshot(external_ids: list[str]) -> list[dict[str, Any]]:
    encoded_ids = base64.b64encode(json.dumps(external_ids).encode()).decode()
    php = f'''\
$ids=json_decode(base64_decode('{encoded_ids}'),true,512,JSON_THROW_ON_ERROR);
$rows=app('db')->table('product_media as pm')->join('products as p','p.id','=','pm.product_id')
 ->join('site_products as sp',function($join){{$join->on('sp.product_id','=','p.id')->where('sp.site_id',4);}})
 ->whereIn('p.external_id',$ids)->orderBy('p.external_id')->orderBy('pm.id')->get([
 'p.external_id','p.id as product_id','sp.id as site_product_id','pm.id as media_id','pm.kind','pm.role',
 'pm.source_page_url','pm.source_asset_url','pm.source_kind','pm.rights_basis','pm.storage_path',
 'pm.content_sha256','pm.verification_status','pm.verification_note','pm.verified_at','pm.is_published','pm.sort_order',
 app('db')->raw("(select count(distinct pm2.product_id) from product_media pm2 where pm2.content_sha256=pm.content_sha256) as hash_distinct_product_count"),
 app('db')->raw("(select count(*) from product_media pm2 join products p2 on p2.id=pm2.product_id where pm2.content_sha256=pm.content_sha256 and pm2.verification_status='verified' and pm2.is_published=true and lower(coalesce(p2.manufacturer,''))=lower(coalesce(p.manufacturer,'')) and lower(coalesce(p2.mpn,''))=lower(coalesce(p.mpn,''))) as verified_same_identity_hash_count")
 ]);
$disk=Storage::disk('public');
foreach($rows as $row){{
 $row->local_exists=false;$row->actual_sha256=null;
 if($row->storage_path && $disk->exists($row->storage_path)){{
  $absolute=$disk->path($row->storage_path);
  $row->local_exists=is_file($absolute);
  if($row->local_exists){{$row->actual_sha256=hash_file('sha256',$absolute);}}
 }}
}}
echo base64_encode(json_encode($rows,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR));
'''
    encoded = base64.b64encode(php.encode()).decode()
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker",
         f"--execute=eval(base64_decode('{encoded}')); "],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise AuditError(f"Media read-only query failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(base64.b64decode(result.stdout.strip(), validate=True).decode())
    except (ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise AuditError("Media query returned invalid base64 JSON") from error


def normalized_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def reusable_rights(value: str) -> bool:
    text = value.casefold()
    if not text or "no explicit" in text or "not established" in text or "hold" in text:
        return False
    return any(token in text for token in ("company-owned", "company owned", "licensed", "licence", "license", "permission"))


def classify_media(
    target: dict[str, Any], media: dict[str, Any], prior_external: set[str],
    prior_pairs: set[tuple[str, int]], prior_hashes: set[str],
) -> dict[str, str]:
    external = str(target["external_id"])
    media_id = integer(media["media_id"])
    digest = str(media.get("content_sha256") or "").lower()
    no_repeat = "new"
    if external in prior_external:
        no_repeat = "prior_product_ledger"
    elif (external, media_id) in prior_pairs:
        no_repeat = "prior_product_media_pair"
    elif digest in prior_hashes:
        no_repeat = "prior_content_hash"

    local_match = bool(
        truth(media.get("local_exists")) and re.fullmatch(r"[a-f0-9]{64}", digest)
        and digest == str(media.get("actual_sha256") or "").lower()
    )
    rights_ok = reusable_rights(str(media.get("rights_basis") or ""))
    mpn_token = normalized_token(str(target.get("mpn") or ""))
    source_tokens = normalized_token(" ".join([
        str(media.get("source_page_url") or ""), str(media.get("source_asset_url") or ""),
    ]))
    same_identity_verified = integer(media.get("verified_same_identity_hash_count", 0)) > 0
    exact_official_reference = bool(
        mpn_token and mpn_token in source_tokens
        and str(media.get("source_kind") or "") in {"manufacturer_primary", "official_manufacturer_product_page"}
    )
    identity_ok = same_identity_verified or exact_official_reference
    shared = integer(media.get("hash_distinct_product_count", 0)) != 1

    blocker = ""
    if no_repeat != "new":
        blocker = no_repeat
    elif not local_match:
        blocker = "local_bytes_missing_or_hash_mismatch"
    elif shared and not same_identity_verified:
        blocker = "content_hash_shared_across_distinct_products"
    elif not rights_ok:
        blocker = "reusable_rights_not_proven"
    elif not identity_ok:
        blocker = "exact_identity_not_machine_proven_without_visual_guess"

    return {
        "product_external_id": external, "product_id": str(target["product_id"]),
        "site_product_id": str(target["site_product_id"]), "name": str(target["name"]),
        "manufacturer": str(target["manufacturer"]), "mpn": str(target["mpn"]),
        "category_external_id": str(target["category_external_id"]),
        "canonical_path": str(target["product_path"]), "media_id": str(media_id),
        "storage_path": str(media.get("storage_path") or ""), "content_sha256": digest,
        "source_kind": str(media.get("source_kind") or ""),
        "source_page_url": str(media.get("source_page_url") or ""),
        "source_asset_url": str(media.get("source_asset_url") or ""),
        "rights_basis": str(media.get("rights_basis") or ""),
        "verification_status": str(media.get("verification_status") or ""),
        "local_bytes_match": str(local_match).lower(),
        "hash_distinct_product_count": str(integer(media.get("hash_distinct_product_count", 0))),
        "verified_same_identity_hash_count": str(integer(media.get("verified_same_identity_hash_count", 0))),
        "no_repeat_status": no_repeat,
        "identity_evidence": "verified_same_identity_hash" if same_identity_verified else ("exact_mpn_in_official_source_url" if exact_official_reference else "none"),
        "rights_evidence": "reusable" if rights_ok else "not_proven",
        "decision": "DETERMINISTIC_PROMOTION_CANDIDATE" if not blocker else "HOLD",
        "blocker": blocker,
    }


def build(
    snapshot: dict[str, Any], media_rows: list[dict[str, Any]],
    no_repeat: tuple[set[str], set[tuple[str, int]], set[str], list[dict[str, Any]]],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    targets = wave249_media_gap(snapshot)
    target_by_external = {str(row["external_id"]): row for row in targets}
    prior_external, prior_pairs, prior_hashes, ledger_evidence = no_repeat
    classified = [
        classify_media(target_by_external[str(media["external_id"])], media, prior_external, prior_pairs, prior_hashes)
        for media in media_rows if str(media.get("external_id")) in target_by_external
    ]
    candidates = [row for row in classified if row["decision"] == "DETERMINISTIC_PROMOTION_CANDIDATE"]
    blockers = Counter(row["blocker"] for row in classified if row["blocker"])
    target_with_media = {row["product_external_id"] for row in classified}
    target_ids = {str(row["external_id"]) for row in targets}
    prior_target_ids = target_ids & prior_external
    no_media_ids = target_ids - target_with_media
    blockers["no_product_media_row"] += len(no_media_ids)
    summary = {
        "schema_version": 1, "wave": "wave250a_deterministic_media_audit", "as_of": "2026-07-30",
        "mode": "live_database_read_only", "site_key": SITE_KEY,
        "scope": {
            "wave249_missing_media_cards": len(targets),
            "already_indexable_excluded": True,
            "cards_with_any_product_media_row": len(target_with_media),
            "cards_without_any_product_media_row": len(targets) - len(target_with_media),
            "product_media_rows_audited": len(classified),
            "cards_in_prior_processed_or_hold_ledgers": len(prior_target_ids),
            "cards_not_in_prior_processed_or_hold_ledgers": len(target_ids - prior_target_ids),
            "unprocessed_cards_with_media": len(target_with_media - prior_target_ids),
            "unprocessed_cards_without_media": len(no_media_ids - prior_target_ids),
        },
        "policy": {
            "no_visual_guess": True, "local_bytes_and_sha256_required": True,
            "reusable_rights_required": True, "exact_machine_identity_required": True,
            "shared_hash_rejected_unless_same_identity_already_verified": True,
            "prior_product_or_asset_ledger_excluded": True,
        },
        "no_repeat": {
            "prior_external_ids": len(prior_external), "prior_product_media_pairs": len(prior_pairs),
            "prior_content_hashes": len(prior_hashes), "source_ledgers": ledger_evidence,
            "source_ledger_count": len(ledger_evidence),
        },
        "blocker_distribution": dict(sorted(blockers.items())),
        "deterministic_candidates": len(candidates),
        "conclusion": "NO_DETERMINISTIC_UNREVIEWED_LOCAL_MEDIA_CANDIDATES" if not candidates else "DETERMINISTIC_CANDIDATES_FOUND",
        "candidate_records": candidates,
        "all_audited_media": classified,
        "quality": {"database_mutations": 0, "network_requests": 0, "manual_visual_guesses": 0},
    }
    return candidates, summary


def write_outputs(candidates: list[dict[str, str]], summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / OUTPUT_CSV.name
    json_path = output_dir / OUTPUT_JSON.name
    audit_rows = summary["all_audited_media"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)
    summary["outputs"] = {
        "csv": {
            "path": csv_path.relative_to(ROOT).as_posix(), "rows": len(audit_rows),
            "candidate_rows": len(candidates), "sha256": sha256(csv_path),
        },
        "json": {"path": json_path.relative_to(ROOT).as_posix()},
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--media-snapshot", type=Path)
    parser.add_argument("--output-dir", type=Path, default=GENERATED)
    args = parser.parse_args()
    module = load_wave249_module()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8")) if args.snapshot else module.query_live_snapshot()
    targets = wave249_media_gap(snapshot)
    media = json.loads(args.media_snapshot.read_text(encoding="utf-8")) if args.media_snapshot else query_media_snapshot([str(row["external_id"]) for row in targets])
    candidates, summary = build(snapshot, media, prior_no_repeat())
    write_outputs(candidates, summary, args.output_dir)
    print(json.dumps({
        "scope": summary["scope"], "deterministic_candidates": len(candidates),
        "conclusion": summary["conclusion"], "database_mutations": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
