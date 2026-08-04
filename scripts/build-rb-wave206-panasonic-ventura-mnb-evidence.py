#!/usr/bin/env python3
"""Build fail-closed OEM evidence for Wave206 Panasonic/Ventura/MNB rows."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave205.csv"
CANONICAL = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
SOURCE_INDEX = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/snapshot-index.json"
LIVE_COLLISIONS = ROOT / "docs/audits/generated/wave206-live-identity-collisions.json"
OUTPUT = ROOT / "docs/audits/generated/wave206-panasonic-ventura-mnb-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave206-panasonic-ventura-mnb-evidence-summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave206-panasonic-ventura-mnb-2026-07-29.json"
MANUFACTURERS = {"Panasonic": 34, "Ventura": 28, "MNB": 23}
EXPECTED_ROWS = 85

PANASONIC_EXACT = {
    "bitrix:1145": ("12", "120", "AGM"),
    "bitrix:1152": ("12", "150", "AGM"),
    "bitrix:1163": ("12", "200", "AGM"),
    "bitrix:1164": ("12", "20", "AGM"),
}
VENTURA_EXACT = {
    "bitrix:1415": ("12", "1.3", "AGM"), "bitrix:1416": ("6", "1.3", "AGM"),
    "bitrix:1437": ("12", "100", "AGM"), "bitrix:1438": ("12", "100", "AGM"),
    "bitrix:1457": ("6", "12", "AGM"), "bitrix:1466": ("12", "120", "AGM"),
    "bitrix:1493": ("12", "12", "AGM"), "bitrix:1516": ("12", "150", "AGM"),
    "bitrix:1545": ("12", "18", "AGM"), "bitrix:1563": ("12", "200", "AGM"),
    "bitrix:1575": ("12", "250", "AGM"), "bitrix:1577": ("12", "26", "AGM"),
    "bitrix:1578": ("12", "26", "AGM"), "bitrix:1592": ("12", "33", "AGM"),
}
VENTURA_COMPATIBILITY = {"bitrix:1441", "bitrix:1443", "bitrix:1517", "bitrix:1525", "bitrix:1568"}
VENTURA_CONFLICTS = {
    "bitrix:1436": "official FT series is AGM; legacy title claims GEL",
    "bitrix:1467": "official GPL series is AGM; legacy title claims GEL",
    "bitrix:1471": "official FT 12-125 is AGM and 130 Ah; legacy title claims GEL and 125 Ah",
    "bitrix:1515": "official FT series is AGM; legacy title claims GEL",
    "bitrix:1535": "official FT series is AGM; legacy title claims GEL",
}
MNB_EXACT = {
    "bitrix:1433": ("12", "100", "AGM"), "bitrix:1434": ("12", "100", "GEL"),
    "bitrix:1464": ("12", "120", "AGM"), "bitrix:1470": ("12", "125", "AGM"),
    "bitrix:1513": ("12", "150", "AGM"), "bitrix:1514": ("12", "150", "GEL"),
    "bitrix:1518": ("12", "155", "AGM"), "bitrix:1534": ("12", "180", "AGM"),
    "bitrix:1561": ("12", "200", "AGM"), "bitrix:1562": ("12", "200", "GEL"),
    "bitrix:1574": ("12", "250", "AGM"),
}
SOURCE_BY_MANUFACTURER = {
    "Panasonic": "panasonic_vrla_professional_catalogue",
    "Ventura": "ventura_2023_catalogue",
    "MNB": "mnb_official_catalogue",
}
FIELDS = [
    "batch", "product_external_id", "name", "manufacturer", "model", "partition",
    "source_tier", "source_publisher", "source_url", "source_assertion",
    "verified_voltage_v", "verified_capacity_ah", "verified_technology",
    "snapshot_path", "snapshot_sha256", "required_exact_tokens", "required_token_counts",
    "checked_source_ids", "unsupported_legacy_claims", "conflict_reason",
    "replacement_manufacturer", "replacement_mpn", "duplicate_cluster_ids",
    "duplicate_decision", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value).upper())


def model_identity_key(value: str) -> str:
    # Decimal capacity tokens are identity-significant: MS 1.2-6 is not MS 12-6.
    value = unicodedata.normalize("NFKC", value).upper().replace(",", ".")
    return re.sub(r"[^A-Z0-9.]", "", value)


def normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).upper().replace(",", ".")
    return re.sub(r"[^A-Z0-9А-Я.]", "", value)


def model_from_name(name: str, manufacturer: str) -> str:
    match = re.search(re.escape(manufacturer) + r"\s+(.+?)(?:\s+для ИБП|\s+\()", name, re.I)
    if not match:
        raise SystemExit(f"Cannot extract {manufacturer} model from: {name}")
    return match.group(1).strip()


def pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def main() -> None:
    candidates = [row for row in read_csv(INPUT) if row["manufacturer_cluster"] in MANUFACTURERS]
    counts = Counter(row["manufacturer_cluster"] for row in candidates)
    if len(candidates) != EXPECTED_ROWS or counts != Counter(MANUFACTURERS):
        raise SystemExit(f"Wave206 scope drifted: rows={len(candidates)}, counts={counts}")
    if len({row["product_external_id"] for row in candidates}) != EXPECTED_ROWS:
        raise SystemExit("Wave206 product ids are not unique")

    index = json.loads(SOURCE_INDEX.read_text(encoding="utf-8-sig"))
    sources = {row["source_id"]: row for row in index["sources"]}
    if set(sources) != set(SOURCE_BY_MANUFACTURER.values()):
        raise SystemExit("Wave206 source index drifted")
    source_texts: dict[str, str] = {}
    for source_id, source in sources.items():
        path = ROOT / source["snapshot_path"]
        if not path.is_file() or sha256(path) != source["snapshot_sha256"]:
            raise SystemExit(f"Pinned source missing or hash-mismatched: {source_id}")
        text_path = ROOT / source.get("extracted_text_path", "")
        if not text_path.is_file() or sha256(text_path) != source.get("extracted_text_sha256"):
            raise SystemExit(f"Pinned extracted text missing or hash-mismatched: {source_id}")
        source_texts[source_id] = text_path.read_text(encoding="utf-8-sig")

    canonical = read_csv(CANONICAL)
    title_index: dict[str, list[str]] = defaultdict(list)
    identity_index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in canonical:
        title_index[normalized_title(row["name"])].append(row["registry_id"])
        for manufacturer in MANUFACTURERS:
            if re.search(rf"\b{re.escape(manufacturer)}\b", row["name"], re.I):
                try:
                    model = model_from_name(row["name"], manufacturer)
                except SystemExit:
                    continue
                identity_index[(manufacturer, model_identity_key(model))].append(row["registry_id"])

    output: list[dict[str, str]] = []
    for candidate in candidates:
        external_id = candidate["product_external_id"]
        manufacturer = candidate["manufacturer_cluster"]
        model = model_from_name(candidate["name"], manufacturer)
        source_id = SOURCE_BY_MANUFACTURER[manufacturer]
        source = sources[source_id]
        model_count = normalized(source_texts[source_id]).count(normalized(model))
        specs: tuple[str, str, str] | None = None
        conflict = ""
        unsupported = ""

        if manufacturer == "Panasonic" and external_id in PANASONIC_EXACT:
            partition, specs = "exact_safe", PANASONIC_EXACT[external_id]
        elif manufacturer == "Ventura" and external_id in VENTURA_EXACT:
            partition, specs = "exact_safe", VENTURA_EXACT[external_id]
        elif manufacturer == "Ventura" and external_id in VENTURA_COMPATIBILITY:
            partition = "compatibility"
            unsupported = "legacy Ah claim is not specified in the official watt-rated HR/HRL table"
        elif manufacturer == "Ventura" and external_id in VENTURA_CONFLICTS:
            partition, conflict = "conflict", VENTURA_CONFLICTS[external_id]
        elif manufacturer == "MNB" and external_id in MNB_EXACT:
            partition, specs = "exact_safe", MNB_EXACT[external_id]
        else:
            partition = "no_evidence"
            unsupported = "model and title specifications are absent from the pinned current first-party catalogue"

        if partition != "no_evidence" and model_count < 1:
            raise SystemExit(f"Classified source row lacks exact model token: {external_id} {model}")
        if partition == "no_evidence" and model_count:
            raise SystemExit(f"No-evidence row unexpectedly has an exact model token: {external_id} {model}")

        peers = sorted(set(
            [item for item in title_index[normalized_title(candidate["name"])] if item != external_id]
            + [item for item in identity_index[(manufacturer, model_identity_key(model))] if item != external_id]
        ))
        exact = partition == "exact_safe"
        safe = exact and not peers
        token_counts = {model: model_count} if model_count else {}
        output.append({
            "batch": "wave206_panasonic_ventura_mnb",
            "product_external_id": external_id,
            "name": candidate["name"],
            "manufacturer": manufacturer,
            "model": model,
            "partition": partition,
            "source_tier": "manufacturer_catalogue_primary" if model_count else "none",
            "source_publisher": source["publisher"] if model_count else "",
            "source_url": source["source_url"] if model_count else "",
            "source_assertion": "exact_model_table_row" if exact else ("exact_model_family_only" if model_count else ""),
            "verified_voltage_v": specs[0] if specs else ("12" if partition == "compatibility" else ""),
            "verified_capacity_ah": specs[1] if specs else "",
            "verified_technology": specs[2] if specs else ("AGM" if partition == "compatibility" else ""),
            "snapshot_path": source["snapshot_path"] if model_count else "",
            "snapshot_sha256": source["snapshot_sha256"] if model_count else "",
            "required_exact_tokens": model if model_count else "",
            "required_token_counts": json.dumps(token_counts, ensure_ascii=False, sort_keys=True) if token_counts else "",
            "checked_source_ids": source_id,
            "unsupported_legacy_claims": unsupported,
            "conflict_reason": conflict,
            "replacement_manufacturer": manufacturer if exact else "",
            "replacement_mpn": model if exact else "",
            "duplicate_cluster_ids": "|".join(peers),
            "duplicate_decision": "hold_duplicate_review" if peers else "unique_exact_identity" if exact else "not_applicable",
            "safe_to_apply": "true" if safe else "false",
        })

    live_data = json.loads(LIVE_COLLISIONS.read_text(encoding="utf-8-sig"))
    live_collisions = {row["candidate_external_id"]: row for row in live_data["collisions"]}
    if live_data.get("candidate_rows_checked") != sum(row["safe_to_apply"] == "true" for row in output):
        raise SystemExit("Live collision snapshot does not cover the pre-DB safe set")
    for row in output:
        collision = live_collisions.get(row["product_external_id"])
        if collision is None:
            continue
        if row["partition"] != "exact_safe" or row["safe_to_apply"] != "true":
            raise SystemExit("Live collision refers to a row outside the pre-DB safe set")
        if normalized(row["replacement_mpn"]).lower() != collision["candidate_mpn_normalized"]:
            raise SystemExit("Live collision normalized MPN drifted")
        row["safe_to_apply"] = "false"
        row["duplicate_cluster_ids"] = collision["conflicting_external_id"]
        row["duplicate_decision"] = "hold_live_product_identity_collision"

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
            "source_kind": "official_manufacturer_catalogue",
            "source_publisher": row["source_publisher"],
            "checked_at": "2026-07-29",
            "product_type": "VRLA battery",
            "source_snapshot_path": (Path("../audits/sources") / source_path.relative_to("docs/audits/sources")).as_posix(),
            "source_snapshot_sha256": row["snapshot_sha256"],
        })
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_products}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    partitions = Counter(row["partition"] for row in output)
    safe_ids = sorted(row["product_external_id"] for row in output if row["safe_to_apply"] == "true")
    duplicate_rows = [row for row in output if row["duplicate_cluster_ids"]]
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave206_panasonic_ventura_mnb",
        "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(candidates), "manufacturer_counts": dict(sorted(counts.items()))},
        "canonical_registry": {"path": CANONICAL.relative_to(ROOT).as_posix(), "sha256": sha256(CANONICAL), "rows": len(canonical)},
        "source_index": {"path": SOURCE_INDEX.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE_INDEX), "sources": len(sources)},
        "live_collision_guard": {"path": LIVE_COLLISIONS.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE_COLLISIONS), "candidate_rows_checked": live_data["candidate_rows_checked"], "collision_rows": len(live_collisions)},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)},
        "laravel_manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_products)},
        "partition_counts": dict(sorted(partitions.items())),
        "safe_to_apply": {"rows": len(safe_ids), "external_ids": safe_ids},
        "duplicate_guard": {
            "rows_with_strict_title_or_manufacturer_model_peers": len(duplicate_rows),
            "rows": [{"product_external_id": row["product_external_id"], "peer_ids": row["duplicate_cluster_ids"].split("|")} for row in duplicate_rows],
        },
        "holds": {"rows": len(output) - len(safe_ids)},
        "policy": {"primary_manufacturer_sources_only": True, "price_stock_media_publication_authorized": False, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "partitions": dict(sorted(partitions.items())), "safe_to_apply": len(safe_ids)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
