#!/usr/bin/env python3
"""Build fail-closed Wave207 Motorola/Kenwood OEM evidence and manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
CANONICAL = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
SOURCE_INDEX = ROOT / "docs/audits/sources/wave207-motorola-kenwood/snapshot-index.json"
LIVE_COLLISIONS = ROOT / "docs/audits/generated/wave207-live-identity-collisions.json"
OUTPUT = ROOT / "docs/audits/generated/wave207-motorola-kenwood-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave207-motorola-kenwood-evidence-summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave207-motorola-kenwood-2026-07-29.json"
DRY_RUN = ROOT / "docs/audits/generated/wave207-laravel-dry-run.json"
EXPECTED = {"Motorola": 74, "Kenwood": 30}

KENWOOD_EXACT = {
    "bitrix:2597": ("KNB-29N", "NiMH", "1500", "7.2"),
    "bitrix:2602": ("KNB-41NC", "NiMH", "2500", "7.2"),
    "bitrix:2608": ("KNB-53N", "NiMH", "1400", "7.2"),
    "bitrix:2611": ("KNB-56N", "NiMH", "1400", "7.2"),
}
KENWOOD_CONFLICTS = {
    "bitrix:2601": ("KNB-33L", "official capacity 2000mAh; legacy title claims 1700mAh", "portable"),
    "bitrix:2603": ("KNB-45L", "official capacity 2000mAh; legacy title claims 5000mAh", "portable"),
    "bitrix:2605": ("KNB-48L", "official voltage 7.4V; legacy title claims 7.2V", "portable"),
    "bitrix:2606": ("KNB-50NC", "official NiMH 7.2V; legacy title claims NiCd 7.4V", "portable"),
    "bitrix:2609": ("KNB-54N", "official NiMH 2500mAh; legacy title claims NiCd 1700mAh", "portable"),
    "bitrix:2610": ("KNB-55L", "official voltage 7.2V; legacy title claims 7.4V", "portable"),
    "bitrix:2614": ("KNB-63L", "official capacity 1130mAh; legacy title claims 1500mAh", "service"),
}

FIELDS = [
    "batch", "product_external_id", "name", "manufacturer_cluster", "model_candidate",
    "partition", "source_tier", "source_publisher", "source_url", "source_assertion",
    "verified_facts", "snapshot_path", "snapshot_sha256", "required_exact_tokens",
    "required_token_counts", "checked_source_ids", "unsupported_legacy_claims",
    "conflict_reason", "replacement_manufacturer", "replacement_mpn",
    "duplicate_cluster_ids", "duplicate_decision", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).upper()
    return re.sub(r"[^A-Z0-9]", "", value)


def model_from_name(name: str, manufacturer: str) -> str:
    if manufacturer == "Kenwood":
        match = re.search(r"Kenwood\s+(.+?)\s+для радиостанций", name, re.I)
        return match.group(1).strip() if match else ""
    matches = re.findall(r"\b(?:IXNN|JMNN|NNTN|PMNN|HNN|FTN|NTN|RLN)\s*-?\s*\d{4}[A-Z]*\b", name, re.I)
    return re.sub(r"\s+", "", matches[-1].upper()) if matches else ""


def prior_wave206_ids() -> tuple[set[str], list[str]]:
    ids: set[str] = set()
    files: list[str] = []
    for path in sorted((ROOT / "docs/audits/generated").glob("*wave206*evidence*.csv")):
        files.append(path.relative_to(ROOT).as_posix())
        for row in read_csv(path):
            external_id = row.get("product_external_id") or row.get("external_id") or ""
            if external_id:
                ids.add(external_id)
    return ids, files


def source_records() -> tuple[dict[str, dict], dict[str, str], dict]:
    index = json.loads(SOURCE_INDEX.read_text(encoding="utf-8-sig"))
    sources = {row["source_id"]: row for row in index["sources"]}
    texts = {}
    for source_id, source in sources.items():
        snapshot = ROOT / source["snapshot_path"]
        text_path = ROOT / source["extracted_text_path"]
        if not snapshot.is_file() or sha256(snapshot) != source["snapshot_sha256"]:
            raise SystemExit(f"Pinned source missing or hash-mismatched: {source_id}")
        if not text_path.is_file() or sha256(text_path) != source["extracted_text_sha256"]:
            raise SystemExit(f"Extracted source text missing or hash-mismatched: {source_id}")
        texts[source_id] = text_path.read_text(encoding="utf-8-sig")
    required = {"kenwood_portable_radio_accessories_2015", "kenwood_ksc35s_service_manual"}
    if not required.issubset(sources):
        raise SystemExit("Required Kenwood primary snapshots are incomplete")
    return sources, texts, index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provisional", action="store_true", help="Allow manifest generation before Laravel dry-run evidence exists")
    args = parser.parse_args()

    prior_ids, prior_files = prior_wave206_ids()
    raw_scope = [row for row in read_csv(INPUT) if row["manufacturer_cluster"] in EXPECTED]
    overlap = sorted({row["product_external_id"] for row in raw_scope} & prior_ids)
    candidates = [row for row in raw_scope if row["product_external_id"] not in prior_ids]
    counts = Counter(row["manufacturer_cluster"] for row in candidates)
    if counts != Counter(EXPECTED) or len(candidates) != sum(EXPECTED.values()):
        raise SystemExit(f"Wave207 scope drifted after Wave206 exclusion: rows={len(candidates)}, counts={counts}, overlap={overlap}")
    if len({row["product_external_id"] for row in candidates}) != len(candidates):
        raise SystemExit("Wave207 contains duplicate product IDs")

    sources, source_texts, source_index = source_records()
    portable_id = "kenwood_portable_radio_accessories_2015"
    service_id = "kenwood_ksc35s_service_manual"

    target_models: dict[str, str] = {}
    model_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in candidates:
        model = model_from_name(row["name"], row["manufacturer_cluster"])
        target_models[row["product_external_id"]] = model
        if model:
            model_groups[(row["manufacturer_cluster"], normalized(model))].append(row["product_external_id"])

    canonical = read_csv(CANONICAL)
    canonical_model_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in canonical:
        for manufacturer in EXPECTED:
            if re.search(rf"\b{manufacturer}\b", row["name"], re.I):
                model = model_from_name(row["name"], manufacturer)
                if model:
                    canonical_model_groups[(manufacturer, normalized(model))].append(row["registry_id"])

    live = json.loads(LIVE_COLLISIONS.read_text(encoding="utf-8-sig"))
    if live.get("candidate_rows_checked") != len(KENWOOD_EXACT):
        raise SystemExit("Live collision guard does not cover all pre-DB exact rows")
    live_collisions = {row["candidate_external_id"]: row for row in live["collisions"]}

    output: list[dict[str, str]] = []
    for candidate in candidates:
        external_id = candidate["product_external_id"]
        manufacturer = candidate["manufacturer_cluster"]
        model = target_models[external_id]
        partition = "no_evidence"
        source_id = ""
        verified_facts = ""
        conflict = ""
        unsupported = "offered_battery_identity|chemistry|capacity|voltage|device_compatibility"
        exact = False

        if external_id in KENWOOD_EXACT:
            official_model, chemistry, capacity, voltage = KENWOOD_EXACT[external_id]
            source_id = portable_id
            source_text = source_texts[source_id]
            if normalized(source_text).count(normalized(official_model)) < 1:
                raise SystemExit(f"Exact Kenwood model missing from pinned source: {external_id}")
            partition = "exact_safe"
            model = official_model
            verified_facts = f"manufacturer=Kenwood|mpn={official_model}|chemistry={chemistry}|capacity_mah={capacity}|voltage_v={voltage}"
            unsupported = ""
            exact = True
        elif external_id in KENWOOD_CONFLICTS:
            official_model, conflict, source_route = KENWOOD_CONFLICTS[external_id]
            source_id = portable_id if source_route == "portable" else service_id
            if normalized(source_texts[source_id]).count(normalized(official_model)) < 1:
                raise SystemExit(f"Conflict Kenwood model missing from pinned source: {external_id}")
            partition = "conflict"
            model = official_model
            unsupported = "legacy technical claims conflict with first-party source"
        elif manufacturer == "Motorola":
            conflict = "Primary Motorola catalogue snapshots were unavailable during the bounded acquisition; web-index snippets are not accepted as pinned evidence."
        else:
            conflict = "Exact offered battery model is absent from the two pinned first-party Kenwood documents."

        source = sources.get(source_id)
        peers = sorted(set(
            [item for item in model_groups.get((manufacturer, normalized(model)), []) if item != external_id]
            + [item for item in canonical_model_groups.get((manufacturer, normalized(model)), []) if item != external_id]
        )) if model else []
        collision = live_collisions.get(external_id)
        safe = exact and not peers and collision is None
        duplicate_decision = "hold_live_product_identity_collision" if collision else "hold_strict_identity_duplicate" if peers else "unique_exact_identity" if exact else "not_applicable"
        if collision:
            peers = sorted(set(peers + [collision["conflicting_external_id"]]))

        token_count = normalized(source_texts[source_id]).count(normalized(model)) if source_id and model else 0
        checked_source_ids = source_id
        if not checked_source_ids and manufacturer == "Motorola":
            checked_source_ids = "|".join(sorted(item["source_id"] for item in source_index.get("acquisition_failures", [])))
        elif not checked_source_ids:
            checked_source_ids = f"{portable_id}|{service_id}"
        output.append({
            "batch": "wave207_motorola_kenwood",
            "product_external_id": external_id,
            "name": candidate["name"],
            "manufacturer_cluster": manufacturer,
            "model_candidate": model,
            "partition": partition,
            "source_tier": "manufacturer_primary" if source else "none",
            "source_publisher": source["publisher"] if source else "",
            "source_url": source["source_url"] if source else "",
            "source_assertion": "exact_oem_battery_table_row" if exact else "exact_model_conflict" if source else "",
            "verified_facts": verified_facts,
            "snapshot_path": source["snapshot_path"] if source else "",
            "snapshot_sha256": source["snapshot_sha256"] if source else "",
            "required_exact_tokens": model if source else "",
            "required_token_counts": json.dumps({model: token_count}, ensure_ascii=False, sort_keys=True) if source else "",
            "checked_source_ids": checked_source_ids,
            "unsupported_legacy_claims": unsupported,
            "conflict_reason": conflict,
            "replacement_manufacturer": manufacturer if exact else "",
            "replacement_mpn": model if exact else "",
            "duplicate_cluster_ids": "|".join(peers),
            "duplicate_decision": duplicate_decision,
            "safe_to_apply": "true" if safe else "false",
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    manifest_products = []
    for row in output:
        if row["safe_to_apply"] != "true":
            continue
        source_path = Path(row["snapshot_path"])
        manifest_products.append({
            "external_id": row["product_external_id"],
            "current_name": row["name"],
            "manufacturer": row["replacement_manufacturer"],
            "mpn": row["replacement_mpn"],
            "source_url": row["source_url"],
            "source_kind": "official_manufacturer_accessory_catalogue",
            "source_publisher": row["source_publisher"],
            "checked_at": "2026-07-29",
            "product_type": "radio battery pack",
            "source_snapshot_path": (Path("../audits/sources") / source_path.relative_to("docs/audits/sources")).as_posix(),
            "source_snapshot_sha256": row["snapshot_sha256"],
        })
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_products}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    dry_run_verified = False
    if DRY_RUN.is_file():
        dry_run = json.loads(DRY_RUN.read_text(encoding="utf-8-sig"))
        dry_run_verified = (
            dry_run.get("exit_code") == 0
            and dry_run.get("manifest_sha256") == sha256(MANIFEST)
            and dry_run.get("records") == len(manifest_products)
            and dry_run.get("mode") == "dry_run"
            and dry_run.get("commercial_fields_changed") == 0
            and dry_run.get("publication_fields_changed") == 0
        )
    if not args.provisional and not dry_run_verified:
        raise SystemExit("Wave207 manifest lacks a matching successful Laravel dry-run record")

    partitions = Counter(row["partition"] for row in output)
    duplicate_groups = {
        f"{manufacturer}:{model}": sorted(ids)
        for (manufacturer, model), ids in model_groups.items() if len(ids) > 1
    }
    safe_ids = sorted(row["product_external_id"] for row in output if row["safe_to_apply"] == "true")
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave207_motorola_kenwood",
        "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(candidates), "manufacturer_counts": dict(sorted(counts.items()))},
        "wave206_exclusion": {"files": prior_files, "overlap_rows": len(overlap), "overlap_ids": overlap},
        "source_index": {"path": SOURCE_INDEX.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE_INDEX), "pinned_sources": len(sources), "acquisition_failures": len(source_index.get("acquisition_failures", []))},
        "canonical_registry": {"path": CANONICAL.relative_to(ROOT).as_posix(), "sha256": sha256(CANONICAL), "rows": len(canonical)},
        "live_collision_guard": {"path": LIVE_COLLISIONS.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE_COLLISIONS), "candidate_rows_checked": live["candidate_rows_checked"], "collision_rows": len(live_collisions)},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)},
        "partition_counts": dict(sorted(partitions.items())),
        "safe_to_apply": {"rows": len(safe_ids), "external_ids": safe_ids},
        "duplicate_guard": {"strict_identity_groups": len(duplicate_groups), "groups": duplicate_groups},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_products), "laravel_dry_run_verified": dry_run_verified},
        "policy": {"primary_battery_sources_only": True, "compatibility_does_not_prove_pack_identity": True, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "partitions": dict(sorted(partitions.items())), "safe_to_apply": len(safe_ids), "dry_run_verified": dry_run_verified}, ensure_ascii=False))


if __name__ == "__main__":
    main()
