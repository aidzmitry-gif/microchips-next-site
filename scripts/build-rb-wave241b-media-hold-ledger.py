#!/usr/bin/env python3
"""Build the Wave241B no-repeat media acquisition/HOLD ledger."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
QUEUE = GENERATED / "rb-enrichment-queue-wave240.csv"
STAGING = GENERATED / "rb-bitrix-staging-media-wave141.csv"
OUTPUT = GENERATED / "rb-wave241b-media-acquisition-hold-ledger.csv"
SUMMARY = GENERATED / "rb-wave241b-media-acquisition-hold-ledger.summary.json"

DECISION_MARKERS = (
    "review",
    "hold",
    "audit",
    "mismatch",
    "verified",
    "skip",
    "receipt",
    "promotion",
)
NON_DECISION_MARKERS = ("candidate", "queue", "metadata", "gaps")
HASH_RE = re.compile(r"[0-9a-fA-F]{64}")
WAVE_RE = re.compile(r"wave(22[5-9]|23[0-9]|240)")

FIELDNAMES = [
    "priority",
    "product_external_id",
    "name",
    "sku",
    "mpn",
    "manufacturer",
    "category_external_id",
    "status",
    "no_repeat_source_count",
    "no_repeat_sources",
    "local_candidate_count",
    "acquisition_group",
    "hold_reason",
    "next_action",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def prior_media_union() -> tuple[set[str], set[str], dict[str, set[str]]]:
    ids: set[str] = set()
    hashes: set[str] = set()
    sources: dict[str, set[str]] = defaultdict(set)

    for path in sorted(IMPORTS.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        images = payload.get("images", []) if isinstance(payload, dict) else []
        for image in images:
            external_id = str(image.get("external_id", "")).strip()
            content_hash = str(image.get("content_sha256", "")).strip().lower()
            if external_id:
                ids.add(external_id)
                sources[external_id].add(path.name)
            if HASH_RE.fullmatch(content_hash):
                hashes.add(content_hash)

    for path in sorted(GENERATED.glob("*.csv")):
        name = path.name.lower()
        if name.startswith("rb-wave241b-"):
            continue
        if not WAVE_RE.search(name):
            continue
        if not any(token in name for token in ("media", "ocr", "image", "preview")):
            continue
        if not any(token in name for token in DECISION_MARKERS):
            continue
        if any(token in name for token in NON_DECISION_MARKERS):
            continue
        for row in read_csv(path):
            external_id = (row.get("external_id") or row.get("product_external_id") or "").strip()
            if external_id:
                ids.add(external_id)
                sources[external_id].add(path.name)
            for key, value in row.items():
                value = (value or "").strip()
                if ("sha256" in key.lower() or key.lower() == "hash") and HASH_RE.fullmatch(value):
                    hashes.add(value.lower())

    return ids, hashes, sources


def acquisition_fields(external_id: str) -> tuple[str, str, str, str]:
    if external_id.startswith("manufacturer:"):
        return (
            "HOLD_OFFICIAL_ASSET_ACQUISITION",
            "manufacturer_synthetic_no_downloaded_rights_documented_exact_asset",
            "no local company-owned legacy asset and no downloaded official raster with reusable rights",
            "acquire exact manufacturer raster and document reusable rights",
        )
    if external_id.startswith("bitrix:"):
        return (
            "HOLD_LEGACY_MEDIA_ABSENT",
            "bitrix_no_local_legacy_asset",
            "no local Bitrix staging asset remains after no-repeat union",
            "acquire company-owned exact asset or rights-documented official raster",
        )
    return (
        "HOLD_1C_MEDIA_ABSENT",
        "non_bitrix_no_local_asset",
        "no local company-owned asset and no rights-documented official raster",
        "acquire company-owned exact asset or rights-documented official raster",
    )


def main() -> None:
    queue = [
        row
        for row in read_csv(QUEUE)
        if row["has_applied_description"].lower() == "true"
        and row["has_verified_published_image"].lower() == "false"
    ]
    if len(queue) != 745:
        raise SystemExit(f"Wave240 scope drift: expected 745, got {len(queue)}")

    prior_ids, prior_hashes, prior_sources = prior_media_union()
    staging = {
        f"bitrix:{row['legacy_element_id']}": row
        for row in read_csv(STAGING)
    }
    source_rasters = [
        path
        for path in (ROOT / "docs/audits/sources").rglob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}
    ]

    rows: list[dict[str, str | int]] = []
    for item in queue:
        external_id = item["product_external_id"]
        sources = sorted(prior_sources.get(external_id, set()))
        local = staging.get(external_id)

        if external_id in prior_ids:
            status = "EXCLUDED_PRIOR_MEDIA_LEDGER"
            group = "prior_media_decision_no_repeat"
            reason = "prior Wave225-240 media decision exists; do not rescan"
            action = "reuse prior ledger outcome; open a new review only if the asset bytes or authoritative model identity changes"
        elif local and local["sha256"].lower() in prior_hashes:
            status = "EXCLUDED_PRIOR_MEDIA_HASH"
            group = "prior_media_hash_no_repeat"
            reason = "local asset SHA-256 was already reviewed under another media record"
            action = "reuse prior hash-level outcome; do not rescan"
        elif local:
            status = "HOLD_UNREVIEWED_LOCAL_ASSET"
            group = "local_asset_requires_exact_visual_review"
            reason = "new local candidate exists but has no exact visual decision"
            action = "perform original-resolution exact-model review before promotion"
        else:
            status, group, reason, action = acquisition_fields(external_id)

        rows.append(
            {
                "priority": item["priority"],
                "product_external_id": external_id,
                "name": item["name"],
                "sku": item["sku"],
                "mpn": item["mpn"],
                "manufacturer": item["manufacturer"],
                "category_external_id": item["category_external_id"],
                "status": status,
                "no_repeat_source_count": len(sources),
                "no_repeat_sources": "|".join(sources),
                "local_candidate_count": int(local is not None),
                "acquisition_group": group,
                "hold_reason": reason,
                "next_action": action,
            }
        )

    status_counts = Counter(str(row["status"]) for row in rows)
    group_counts = Counter(str(row["acquisition_group"]) for row in rows)
    if status_counts.get("HOLD_UNREVIEWED_LOCAL_ASSET", 0):
        raise SystemExit("Unexpected new local candidates require manual review before ledger finalization")
    if status_counts != Counter(
        {
            "EXCLUDED_PRIOR_MEDIA_LEDGER": 116,
            "HOLD_OFFICIAL_ASSET_ACQUISITION": 407,
            "HOLD_LEGACY_MEDIA_ABSENT": 68,
            "HOLD_1C_MEDIA_ABSENT": 154,
        }
    ):
        raise SystemExit(f"Wave241B status drift: {dict(status_counts)}")

    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "schema_version": 1,
        "wave": "wave241b-media-profile",
        "checked_at": "2026-07-29",
        "scope": {
            "queue": "docs/audits/generated/rb-enrichment-queue-wave240.csv",
            "predicate": "has_applied_description=true and has_verified_published_image=false",
            "count": len(rows),
        },
        "result": {
            "pass_count": 0,
            "promotion_manifest": None,
            "excluded_no_repeat_count": status_counts["EXCLUDED_PRIOR_MEDIA_LEDGER"],
            "hold_count": len(rows) - status_counts["EXCLUDED_PRIOR_MEDIA_LEDGER"],
            "status_counts": dict(sorted(status_counts.items())),
            "acquisition_group_counts": dict(sorted(group_counts.items())),
        },
        "no_repeat_union": {
            "prior_external_ids": len(prior_ids),
            "prior_asset_hashes": len(prior_hashes),
            "waves": "225-240",
        },
        "local_sources": {
            "new_bitrix_staging_candidates": 0,
            "prior_reviewed_with_current_local_staging_asset": sum(
                row["status"] == "EXCLUDED_PRIOR_MEDIA_LEDGER"
                and int(row["local_candidate_count"]) == 1
                for row in rows
            ),
            "prior_reviewed_without_current_local_staging_asset": sum(
                row["status"] == "EXCLUDED_PRIOR_MEDIA_LEDGER"
                and int(row["local_candidate_count"]) == 0
                for row in rows
            ),
            "downloaded_official_rasters_under_docs_audits_sources": len(source_rasters),
            "rights_documented_reusable_official_candidates": 0,
        },
        "safety": {
            "network_calls": 0,
            "database_calls": 0,
            "database_applied": False,
            "backend_files_changed": 0,
        },
        "ledger": "docs/audits/generated/rb-wave241b-media-acquisition-hold-ledger.csv",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["result"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
