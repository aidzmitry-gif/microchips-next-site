#!/usr/bin/env python3
"""Build fail-closed official-source identity evidence for Wave208-S."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
SNAPSHOT_INDEX = ROOT / "docs/audits/sources/wave208s-stationary/snapshot-index.json"
FULL_REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
LIVE_GUARD = ROOT / "docs/audits/generated/wave208s-stationary-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave208s-stationary-laravel-dry-run.json"
OUTPUT = ROOT / "docs/audits/generated/rb-wave208s-stationary-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave208s-stationary-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave208s-stationary-2026-07-29.json"

EXPECTED_GROUPS = {"Casil": 11, "Robiton": 7, "Minamoto": 1}
NO_EVIDENCE = {
    "bitrix:1191": ("Robiton", "VRLA4-3", "No exact current ROBITON manufacturer page or catalogue entry was found."),
    "bitrix:1409": ("Casil", "CA1213", "The official current Casil catalogue has CA1212, not the legacy CA1213 identity."),
    "bitrix:1543": ("Minamoto", "MB12180", "The current official Minamoto domain provides no exact MB12180 product evidence."),
}
DRY_RUN_MATCHER_CONFLICTS = {
    "bitrix:1399": "Laravel bounded-name matcher drops the standalone zero token in VRLA12-0.8; fail-closed until matcher coverage is corrected.",
}
OFFICIAL_HOSTS = {"en.casilbattery.com", "robiton.ru"}
FIELDS = [
    "batch", "group", "product_external_id", "name", "partition", "evidence_scope",
    "source_publisher", "source_url", "source_assertion", "verified_facts",
    "snapshot_path", "snapshot_sha256", "unsupported_legacy_claims", "conflict_reason",
    "replacement_manufacturer", "replacement_mpn", "manufacturer_mpn_inference",
    "duplicate_review", "live_collision_review", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", value.casefold().replace("ё", "е"))


def official_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(host == item or host.endswith("." + item) for item in OFFICIAL_HOSTS)


def main() -> None:
    source_rows = read_csv(INPUT)
    selected = [row for row in source_rows if row["manufacturer_cluster"] in EXPECTED_GROUPS]
    counts = Counter(row["manufacturer_cluster"] for row in selected)
    if dict(counts) != EXPECTED_GROUPS or len(selected) != 19:
        raise SystemExit(f"Wave208-S input drift: expected {EXPECTED_GROUPS}, got {dict(counts)}")
    selected_ids = {row["product_external_id"] for row in selected}
    if len(selected_ids) != 19:
        raise SystemExit("Wave208-S input repeats external IDs")

    index = json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8-sig"))
    sources: dict[str, dict] = {}
    for source in index["sources"]:
        external_id = source["external_id"]
        if external_id in sources or external_id not in selected_ids:
            raise SystemExit(f"Unexpected or duplicate snapshot source: {external_id}")
        if not official_url(source["source_url"]):
            raise SystemExit(f"Non-official source rejected: {external_id}")
        if source["source_kind"] != "official_manufacturer_product_page":
            raise SystemExit(f"Non-product source rejected: {external_id}")
        snapshot = ROOT / source["snapshot_path"]
        if not snapshot.is_file() or sha256(snapshot) != source["snapshot_sha256"]:
            raise SystemExit(f"Snapshot pin mismatch: {external_id}")
        if not all(source["token_counts"].get(token, 0) > 0 for token in source["required_tokens"]):
            raise SystemExit(f"Required exact token absent: {external_id}")
        sources[external_id] = source
    if len(sources) != 16 or set(NO_EVIDENCE) | set(sources) != selected_ids:
        raise SystemExit("Wave208-S evidence partition drift")

    live_guard = json.loads(LIVE_GUARD.read_text(encoding="utf-8-sig"))
    if live_guard["query_exit_code"] != 0 or live_guard["candidate_rows_checked"] != 16:
        raise SystemExit("Live collision guard is incomplete")
    live_collisions = {row["candidate_external_id"] for row in live_guard["collisions"]}

    full_rows = read_csv(FULL_REGISTRY)
    full_names: dict[str, list[str]] = defaultdict(list)
    for row in full_rows:
        full_names[normalize(row["name"])].append(row["registry_id"])

    output_rows: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []
    strict_duplicate_clusters: dict[str, list[str]] = {}
    for candidate in selected:
        external_id = candidate["product_external_id"]
        group = candidate["manufacturer_cluster"]
        duplicate_ids = sorted(
            item for item in full_names.get(normalize(candidate["name"]), []) if item != external_id
        )
        if duplicate_ids:
            strict_duplicate_clusters[external_id] = duplicate_ids

        source = sources.get(external_id)
        if source is None:
            manufacturer, model, reason = NO_EVIDENCE[external_id]
            output_rows.append({
                "batch": "wave208s_stationary", "group": group,
                "product_external_id": external_id, "name": candidate["name"],
                "partition": "no_evidence", "evidence_scope": "no_current_exact_official_model_evidence",
                "source_publisher": "", "source_url": "", "source_assertion": "",
                "verified_facts": "", "snapshot_path": "", "snapshot_sha256": "",
                "unsupported_legacy_claims": f"manufacturer:{manufacturer}|mpn:{model}|chemistry|capacity|voltage",
                "conflict_reason": reason, "replacement_manufacturer": "", "replacement_mpn": "",
                "manufacturer_mpn_inference": "none",
                "duplicate_review": "strict_full_name_duplicate_hold" if duplicate_ids else "no_strict_full_name_duplicate",
                "live_collision_review": "not_applicable_no_exact_identity", "safe_to_apply": "false",
            })
            continue

        collision = external_id in live_collisions
        matcher_conflict = external_id in DRY_RUN_MATCHER_CONFLICTS
        exact_safe = not duplicate_ids and not collision and not matcher_conflict
        manufacturer = source["manufacturer"]
        model = source["model"]
        output_rows.append({
            "batch": "wave208s_stationary", "group": group,
            "product_external_id": external_id, "name": candidate["name"],
            "partition": "exact_safe" if exact_safe else "conflict",
            "evidence_scope": "exact_official_brand_model_identity",
            "source_publisher": source["publisher"], "source_url": source["source_url"],
            "source_assertion": f"The official product page identifies exact model {model}.",
            "verified_facts": f"manufacturer={manufacturer}|mpn={model}",
            "snapshot_path": source["snapshot_path"], "snapshot_sha256": source["snapshot_sha256"],
            "unsupported_legacy_claims": "chemistry|capacity|voltage" if manufacturer == "Casil" else "none_for_identity_only",
            "conflict_reason": "Strict full-name duplicate requires canonical review." if duplicate_ids else (
                "Live MPN/SKU collision blocks apply." if collision else DRY_RUN_MATCHER_CONFLICTS.get(external_id, "")
            ),
            "replacement_manufacturer": manufacturer if exact_safe else "",
            "replacement_mpn": model if exact_safe else "",
            "manufacturer_mpn_inference": "explicit_official_product_identity" if exact_safe else "none",
            "duplicate_review": "strict_full_name_duplicate_hold" if duplicate_ids else "no_strict_full_name_duplicate",
            "live_collision_review": "collision_hold" if collision else "no_live_mpn_or_sku_collision",
            "safe_to_apply": "true" if exact_safe else "false",
        })
        if exact_safe:
            manifest_rows.append({
                "external_id": external_id,
                "current_name": candidate["name"],
                "manufacturer": manufacturer,
                "mpn": model,
                "source_url": source["source_url"],
                "source_kind": source["source_kind"],
                "source_publisher": source["publisher"],
                "checked_at": source["checked_at"],
                "product_type": "stationary sealed rechargeable battery",
                "source_snapshot_path": "../audits/sources/wave208s-stationary/" + Path(source["snapshot_path"]).name,
                "source_snapshot_sha256": source["snapshot_sha256"],
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    MANIFEST.write_text(
        json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    dry_run_verified = False
    if DRY_RUN.is_file():
        dry_run = json.loads(DRY_RUN.read_text(encoding="utf-8-sig"))
        dry_run_verified = (
            dry_run.get("mode") == "dry_run"
            and dry_run.get("exit_code") == 0
            and dry_run.get("records") == len(manifest_rows)
            and dry_run.get("manifest_sha256") == sha256(MANIFEST)
            and dry_run.get("database_mutations") == 0
        )
    partitions = Counter(row["partition"] for row in output_rows)
    summary = {
        "schema_version": 1, "site": "microchips-by", "batch": "wave208s_stationary",
        "checked_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": 19},
        "group_counts": dict(counts), "partition_counts": dict(sorted(partitions.items())),
        "source_index": {"path": SNAPSHOT_INDEX.relative_to(ROOT).as_posix(), "sha256": sha256(SNAPSHOT_INDEX), "pinned_sources": len(sources)},
        "canonical_registry": {"path": FULL_REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(FULL_REGISTRY), "rows": len(full_rows)},
        "duplicate_guard": {"strict_full_name_groups": strict_duplicate_clusters},
        "live_collision_guard": {"path": LIVE_GUARD.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE_GUARD), "collisions": len(live_collisions)},
        "safe_to_apply": {"rows": len(manifest_rows), "external_ids": [row["external_id"] for row in manifest_rows]},
        "no_evidence": {"rows": len(NO_EVIDENCE), "external_ids": sorted(NO_EVIDENCE)},
        "laravel_matcher_conflicts": {"rows": len(DRY_RUN_MATCHER_CONFLICTS), "external_ids": sorted(DRY_RUN_MATCHER_CONFLICTS)},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output_rows)},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_rows), "laravel_dry_run_verified": dry_run_verified},
        "laravel_dry_run": {"path": DRY_RUN.relative_to(ROOT).as_posix(), "sha256": sha256(DRY_RUN) if DRY_RUN.is_file() else "", "verified": dry_run_verified},
        "policy": {"official_exact_product_sources_only": True, "retailer_and_compatibility_snippets_rejected": True, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output_rows), "partitions": dict(partitions), "manifest": len(manifest_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
