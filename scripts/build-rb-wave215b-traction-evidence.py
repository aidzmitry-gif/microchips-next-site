#!/usr/bin/env python3
"""Build the fail-closed Wave215-B traction identity evidence bundle.

Only a literal model occurrence in an SHA-pinned manufacturer-primary snapshot
can enter the OEM manifest.  This is intentionally an identity-only workflow:
it never promotes legacy chemistry, capacity, price, availability, or device
compatibility wording to the catalog.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave214.csv"
REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
SOURCE_DIR = ROOT / "docs/audits/sources/wave215b-traction"
SOURCE_REGISTRY = SOURCE_DIR / "source-registry.json"
YUASA_PDF = SOURCE_DIR / "yuasa-vehicle-battery-range-oct-2025.pdf"
OUTPUT = ROOT / "docs/audits/generated/rb-wave215b-traction-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave215b-traction-evidence.summary.json"
LIVE = ROOT / "docs/audits/generated/wave215b-traction-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave215b-traction-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave215b-traction-2026-07-29.json"
CHECKED_AT = "2026-07-29"

TARGETS = {"Minamoto": 5, "Sonnenschein": 15, "Yuasa": 2, "unresolved_other": 78, "unresolved_replacement": 15}
YUASA_EXACT = {
    "bitrix:24373": "DCB145-6",
    "bitrix:24374": "DCB105-6",
}
FIELDS = [
    "batch", "product_external_id", "name", "manufacturer_cluster", "family_or_model", "product_class",
    "compatibility_context", "partition", "source_tier", "source_publisher", "source_url", "source_snapshot_path",
    "source_snapshot_sha256", "source_assertion", "conflict_reason", "canonical_registry_collision_ids",
    "live_db_collision_ids", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    return re.sub(r"[^A-Z0-9]", "", value)


def model_pattern(model: str) -> re.Pattern[str]:
    pieces = [re.escape(ch) for ch in unicodedata.normalize("NFKC", model).upper() if ch.isalnum()]
    return re.compile(r"(?<![A-Z0-9])" + r"[\s,._/-]*".join(pieces) + r"(?![A-Z0-9])", re.I)


def source_record() -> tuple[dict[str, str], str]:
    if not YUASA_PDF.is_file() or not YUASA_PDF.read_bytes().startswith(b"%PDF-"):
        raise SystemExit("Wave215-B requires the pinned official GS Yuasa PDF snapshot")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(YUASA_PDF).pages)
    for model in YUASA_EXACT.values():
        if not model_pattern(model).search(text.upper()):
            raise SystemExit(f"official Yuasa snapshot lacks exact model {model}")
    source = {
        "source_id": "yuasa_vehicle_range_oct_2025",
        "publisher": "GS Yuasa Battery Sales UK Limited",
        "source_url": "https://www.yuasa.com/media/akeneo_connector/asset_files/L/I/LIT059_GS_Vehicle_Battery_Range_Oct_25_WEB_6b06.pdf",
        "source_kind": "official_manufacturer_catalogue",
        "checked_at": CHECKED_AT,
        "snapshot_path": YUASA_PDF.relative_to(ROOT).as_posix(),
        "snapshot_sha256": sha256(YUASA_PDF),
        "exact_models": sorted(YUASA_EXACT.values()),
    }
    SOURCE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_REGISTRY.write_text(json.dumps({
        "schema_version": 1, "checked_at": CHECKED_AT,
        "policy": "SHA-pinned official manufacturer-primary sources only",
        "sources": [source],
        "unavailable_exact_source_holds": {
            "Minamoto": "no SHA-pinned official exact-model snapshot",
            "Sonnenschein": "official GF/Y page was not retrievable as a pin; no source-derived identity emitted",
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return source, text


def live_products() -> list[dict[str, str]]:
    php = "$r=app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized','status')->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only PostgreSQL query failed: {run.stderr.strip() or run.stdout.strip()}")
    products = json.loads(run.stdout.strip())
    if len({row["external_id"] for row in products}) != len(products):
        raise SystemExit("live PostgreSQL contains duplicate external IDs")
    return products


def candidate_class(row: dict[str, str]) -> tuple[str, str]:
    # All 115 titles name an accumulator.  Boat wording denotes a use context,
    # not proof of a replacement-pack manufacturer/model identity.
    if row["manufacturer_cluster"] == "unresolved_replacement":
        return "actual_battery", "boat_or_marine_device_compatibility_context"
    return "actual_battery", ""


def title_model(row: dict[str, str]) -> str:
    if row["product_external_id"] in YUASA_EXACT:
        return YUASA_EXACT[row["product_external_id"]]
    if row["manufacturer_cluster"] == "Sonnenschein":
        hit = re.search(r"\bGF\s*\d{2}\s*\d{3}(?:\s*[A-Z0-9]+)*\b", row["name"], re.I)
        return re.sub(r"\s+", " ", hit.group(0)).strip() if hit else ""
    if row["manufacturer_cluster"] == "Minamoto":
        hit = re.search(r"\bDCG\d+-\d+\b", row["name"], re.I)
        return hit.group(0) if hit else ""
    return ""


def main() -> None:
    selected = [row for row in read_csv(INPUT) if row["category_external_id"] == "seo:batteries-traction"]
    counts = Counter(row["manufacturer_cluster"] for row in selected)
    ids = [row["product_external_id"] for row in selected]
    if len(selected) != 115 or len(ids) != len(set(ids)) or counts != Counter(TARGETS):
        raise SystemExit(f"Wave215-B target union drift: {len(selected)} {dict(counts)}")
    scope_hits = [row["product_external_id"] for row in selected if re.search(r"\b(?:starter|automotive|electronics)\b|автомоб|стартер|электрон", row["name"], re.I)]
    if scope_hits:
        raise SystemExit(f"automotive starter/electronic scope violation: {scope_hits}")
    source, _ = source_record()
    registry = read_csv(REGISTRY)
    products = live_products()
    by_id = {row["external_id"]: row for row in products}
    missing_or_drift = [row["product_external_id"] for row in selected if row["product_external_id"] not in by_id or by_id[row["product_external_id"]]["name"] != row["name"]]
    if missing_or_drift:
        raise SystemExit(f"live product identity drift: {missing_or_drift}")

    canonical_peers: dict[str, list[str]] = defaultdict(list)
    live_peers: dict[str, list[str]] = defaultdict(list)
    for external_id, model in YUASA_EXACT.items():
        pattern = model_pattern(model)
        for entry in registry:
            if "yuasa" in entry.get("name", "").casefold() and pattern.search(entry.get("name", "").upper()) and entry["registry_id"] != external_id:
                canonical_peers[external_id].append(entry["registry_id"])
        for product in products:
            if product["external_id"] == external_id:
                continue
            mpn = normalized(str(product.get("mpn_normalized") or product.get("mpn") or ""))
            sku = normalized(str(product.get("sku_normalized") or product.get("sku") or ""))
            same_name = "yuasa" in str(product.get("name") or "").casefold() and bool(pattern.search(str(product.get("name") or "").upper()))
            if normalized(model) in {mpn, sku} or same_name:
                live_peers[external_id].append(product["external_id"])

    output: list[dict[str, str]] = []
    for row in selected:
        external_id = row["product_external_id"]
        family_model = title_model(row)
        product_class, compatibility = candidate_class(row)
        partition, reason = "hold_no_exact_primary_source", "no_SHA_pinned_official_exact_model_source"
        source_fields = {key: "" for key in ("source_tier", "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion")}
        if row["manufacturer_cluster"] == "unresolved_replacement":
            partition, reason = "hold_compatibility_context", "marine_or_boat_compatibility_does_not_prove_offered_battery_identity"
        elif external_id in YUASA_EXACT:
            peers = sorted(set(canonical_peers[external_id] + live_peers[external_id]))
            partition = "exact_safe" if not peers else "hold_identity_collision"
            reason = "" if not peers else "canonical_registry_or_live_database_identity_collision"
            source_fields = {
                "source_tier": "manufacturer_primary", "source_publisher": source["publisher"], "source_url": source["source_url"],
                "source_snapshot_path": "../audits/sources/wave215b-traction/yuasa-vehicle-battery-range-oct-2025.pdf",
                "source_snapshot_sha256": source["snapshot_sha256"], "source_assertion": "exact_model_in_pinned_official_catalogue",
            }
        output.append({
            "batch": "wave215b_traction", "product_external_id": external_id, "name": row["name"],
            "manufacturer_cluster": row["manufacturer_cluster"], "family_or_model": family_model,
            "product_class": product_class, "compatibility_context": compatibility, "partition": partition,
            **source_fields, "conflict_reason": reason,
            "canonical_registry_collision_ids": "|".join(sorted(set(canonical_peers[external_id]))),
            "live_db_collision_ids": "|".join(sorted(set(live_peers[external_id]))),
            "safe_to_apply": "true" if partition == "exact_safe" else "false",
        })
    manifest_products = [{
        "external_id": row["product_external_id"], "current_name": row["name"], "manufacturer": "Yuasa", "mpn": row["family_or_model"],
        "source_url": row["source_url"], "source_kind": "official_manufacturer_catalogue", "source_publisher": row["source_publisher"],
        "checked_at": CHECKED_AT, "product_type": "traction deep-cycle battery",
        "source_snapshot_path": row["source_snapshot_path"], "source_snapshot_sha256": row["source_snapshot_sha256"],
    } for row in output if row["safe_to_apply"] == "true"]
    if not manifest_products or len({normalized(row["mpn"]) for row in manifest_products}) != len(manifest_products):
        raise SystemExit("exact-safe manifest must be non-empty and use unique normalized MPNs")
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(output)
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_products}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    live = {
        "schema_version": 1, "mode": "read_only", "query_exit_code": 0, "database": "current Docker PostgreSQL",
        "candidate_rows_checked": len(YUASA_EXACT), "candidate_external_ids": sorted(YUASA_EXACT),
        "collisions": [
            {"candidate_external_id": key, "conflicting_external_ids": sorted(set(value))}
            for key, value in sorted(live_peers.items()) if value
        ],
        "database_mutations": 0,
    }
    LIVE.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dry_verified = False
    if DRY_RUN.is_file():
        dry = json.loads(DRY_RUN.read_text(encoding="utf-8-sig"))
        dry_verified = all((dry.get("mode") == "dry_run", dry.get("exit_code") == 0, dry.get("records") == len(manifest_products), dry.get("manifest_sha256") == sha256(MANIFEST), dry.get("commercial_fields_changed") == 0, dry.get("publication_fields_changed") == 0, dry.get("post_run_rows_with_manufacturer_or_mpn") == 0, dry.get("database_mutations") == 0))
    summary = {
        "schema_version": 1, "batch": "wave215b_traction", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(selected), "manufacturer_counts": dict(sorted(counts.items()))},
        "product_classification": {"actual_battery": len(selected), "accessory_or_device_only": 0, "compatibility_context_hold": 15},
        "scope_exclusion": {"automotive_starter_rows": 0, "electronic_component_rows": 0},
        "source_registry": {"path": SOURCE_REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE_REGISTRY), "pinned_sources": 1},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "collision_rows": sum(bool(row["canonical_registry_collision_ids"]) for row in output)},
        "live_collision_guard": {"path": LIVE.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE), "collision_rows": len(live["collisions"]), "database_mutations": 0},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)},
        "partition_counts": dict(sorted(Counter(row["partition"] for row in output).items())),
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_products), "laravel_dry_run_verified": dry_verified},
        "laravel_dry_run": {"path": DRY_RUN.relative_to(ROOT).as_posix(), "verified": dry_verified},
        "policy": {"exact_safe_manifest_only": True, "automatic_database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "partitions": summary["partition_counts"], "manifest_rows": len(manifest_products), "dry_run_verified": dry_verified}, ensure_ascii=False))


if __name__ == "__main__":
    main()
