#!/usr/bin/env python3
"""Build the fail-closed Wave215-C medical and EnerSys UPS evidence ledger.

The two Cyclon records have a SHA-pinned primary EnerSys catalogue, but their
legacy names contain a cell-series designation rather than the catalogue part
number.  They therefore do not pass Laravel's bounded-name MPN rule.  Medical
device compatibility titles are likewise retained as B2B holds until a
first-party source proves the *sellable pack*, not merely the device.
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
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave214.csv"
PROCESSED = GEN / "rb-b2b-processed-register-wave214.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
WAVE209A_SOURCES = GEN / "rb-wave209a-official-source-registry.json"
SOURCE_REGISTRY = ROOT / "docs/audits/sources/wave215c-medical-ups/source-registry.json"
OUTPUT = GEN / "rb-wave215c-medical-ups-evidence.csv"
SUMMARY = GEN / "rb-wave215c-medical-ups-evidence.summary.json"
LIVE = GEN / "wave215c-medical-ups-live-identity-collisions.json"
DRY_RUN = GEN / "wave215c-medical-ups-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave215c-medical-ups-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-wave215c-medical-ups-evidence.md"

CHECKED_AT = "2026-07-29"
INPUT_SHA256 = "add632ce13a89a0cd86ef166bc76dd6a924a21e730a3122b4ab4fa10b5ba8e4d"
CYCLON_FILE = "enersys-cyclon-selection-guide.pdf"
CYCLON = {
    "bitrix:24517": {"series": "Cyclon BC Cell", "part_number": "0820-0004", "capacity_ah": "25", "voltage_v": ""},
    "bitrix:24518": {"series": "Cyclon E Cell", "part_number": "0850-0004", "capacity_ah": "8", "voltage_v": "2"},
}
FIELDS = [
    "batch", "product_external_id", "name", "category_external_id", "lane", "device_oem", "device_model",
    "battery_pack_ids", "voltage_v", "capacity_mah", "enersys_exact_series", "enersys_catalogue_part_number",
    "source_tier", "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256",
    "source_assertion", "partition", "hold_reason", "full_registry_exact_title_duplicates",
    "full_registry_candidate_identity_duplicates", "live_db_collision_external_ids", "live_current_manufacturer",
    "live_current_mpn", "safe_to_apply",
]

OEM_NAMES = sorted((
    "Cardinal Health", "Diversified Medical", "Fukuda Denshi", "Philips Respironics", "Welch-Allyn",
    "Hellige", "Neusoft", "Rainin", "Alaris", "Anritsu", "Biolight", "Dongjiang", "EDAN", "Fukuda",
    "Hughes", "Kenz", "MCM", "OMRON", "Philips", "GE", "HP",
), key=len, reverse=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    return re.sub(r"[^A-Z0-9]+", "", value)


def product_norm(value: str) -> str:
    return re.sub(r"[\W_]", "", (value or "").casefold(), flags=re.UNICODE)


def technical_values(name: str) -> tuple[str, str]:
    capacity = re.search(r"\b(\d+(?:[.,]\d+)?)\s*mAh\b", name, re.I)
    voltage = re.search(r"\b(\d+(?:[.,]\d+)?)\s*V\b", name, re.I)
    return (voltage.group(1).replace(",", ".") if voltage else "", capacity.group(1).replace(",", ".") if capacity else "")


def medical_identity(name: str) -> tuple[str, str, str, str, str]:
    match = re.search(r"\sдля\s+(.+)$", name, re.I)
    body = match.group(1).strip() if match else ""
    oem = next((item for item in OEM_NAMES if body.casefold().startswith(item.casefold())), "")
    if not oem:
        oem, _, body_tail = body.partition(" ")
    else:
        body_tail = body[len(oem):].strip()
    pack_ids = []
    for group in re.findall(r"\(([^()]*)\)", name):
        if re.search(r"\b(?:mAh|V)\b", group, re.I):
            continue
        if re.search(r"[A-Za-zА-Яа-я]", group) and re.search(r"\d", group):
            pack_ids.append(group.strip())
    model = re.sub(r"\s*\([^()]*?(?:mAh|V)[^()]*\)", "", body_tail, flags=re.I)
    model = re.sub(r"\s+\d+(?:[.,]\d+)?\s*mAh\b.*$", "", model, flags=re.I).strip(" ,")
    voltage, capacity = technical_values(name)
    return oem, model, "|".join(pack_ids), voltage, capacity


def live_products() -> list[dict]:
    php = ("$r=app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer',"
           "'sku_normalized','mpn_normalized','status')->orderBy('external_id')->get();"
           "echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);")
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only PostgreSQL query failed: {run.stderr.strip() or run.stdout.strip()}")
    rows = json.loads(run.stdout)
    if len({row["external_id"] for row in rows}) != len(rows):
        raise SystemExit("live PostgreSQL repeats external IDs")
    return rows


def pinned_cyclon_source() -> tuple[dict, str]:
    records = json.loads(WAVE209A_SOURCES.read_text(encoding="utf-8"))
    source = next((row for row in records if row["filename"] == CYCLON_FILE), None)
    if source is None or urlparse(source["source_url"]).hostname != "www.enersys.com":
        raise SystemExit("missing non-primary EnerSys Cyclon source")
    snapshot = ROOT / "docs" / source["snapshot_path"]
    if not snapshot.is_file() or sha(snapshot) != source["sha256"]:
        raise SystemExit("EnerSys Cyclon source snapshot pin drift")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(snapshot).pages)
    for item in CYCLON.values():
        if norm(item["series"].replace("Cyclon ", "")) not in norm(text) or norm(item["part_number"]) not in norm(text):
            raise SystemExit(f"pinned EnerSys catalogue lacks exact series/part: {item}")
    registry = {"schema_version": 1, "checked_at": CHECKED_AT, "policy": "SHA-pinned official manufacturer-primary source only", "sources": [{
        "source_id": CYCLON_FILE, "publisher": source["publisher"], "source_url": source["source_url"],
        "source_kind": "official_manufacturer_catalogue", "snapshot_path": snapshot.relative_to(ROOT).as_posix(),
        "snapshot_sha256": source["sha256"],
    }]}
    SOURCE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return source, snapshot.relative_to(ROOT).as_posix()


def main() -> None:
    if sha(INPUT) != INPUT_SHA256:
        raise SystemExit("Wave215-C input pin drift")
    source_rows, processed, registry = read_csv(INPUT), read_csv(PROCESSED), read_csv(REGISTRY)
    groups = defaultdict(list)
    for row in source_rows:
        groups[row["category_external_id"]].append(row)
    lane_a = {row["product_external_id"] for row in groups["seo:power-systems"]}
    lane_b = {row["product_external_id"] for row in groups["seo:batteries-traction"]}
    medical = [row for row in groups["seo:replacement-medical"] if row["manufacturer_cluster"] == "unresolved_replacement"]
    ups = [row for row in groups["seo:batteries-ups"] if row["manufacturer_cluster"] == "EnerSys"]
    lane_c = {row["product_external_id"] for row in medical + ups}
    if (len(lane_a), len(lane_b), len(lane_c)) != (359, 115, 26) or lane_a & lane_b or lane_a & lane_c or lane_b & lane_c or len(lane_a | lane_b | lane_c) != 500:
        raise SystemExit("Wave215 A/B/C partition invariant failed")
    if len(medical) != 24 or {row["product_external_id"] for row in ups} != set(CYCLON):
        raise SystemExit("Wave215-C must be 24 medical + two exact EnerSys UPS rows")
    selected = medical + ups
    ids = [row["product_external_id"] for row in selected]
    processed_overlap = sorted(set(ids) & {row["product_external_id"] for row in processed})
    if processed_overlap:
        raise SystemExit(f"Wave215-C overlaps processed2500: {processed_overlap}")
    forbidden = [row["product_external_id"] for row in selected if any(word in " ".join(row.values()).casefold() for word in ("automotive", "автомоб", "electronics", "электрон"))]
    if forbidden:
        raise SystemExit(f"automotive/electronics scope breach: {forbidden}")
    source, snapshot_path = pinned_cyclon_source()
    live = live_products(); live_by_id = {row["external_id"]: row for row in live}
    if set(ids) - set(live_by_id):
        raise SystemExit("Wave215-C candidate absent from current PostgreSQL")
    by_title = defaultdict(list)
    for row in registry:
        by_title[norm(row.get("name", ""))].append(row["registry_id"])

    output, live_checks = [], []
    for row in selected:
        external_id, name = row["product_external_id"], row["name"]
        exact_title = sorted(peer for peer in by_title[norm(name)] if peer != external_id)
        current = live_by_id[external_id]
        if external_id in CYCLON:
            item = CYCLON[external_id]
            # The exact, bounded product identity is the source's Cyclon cell
            # series.  The separate catalogue part number is evidence, not an
            # inferred substitution for the title's identity.
            candidate_identity = item["series"]
            registry_peers = sorted(other["registry_id"] for other in registry if other["registry_id"] != external_id and norm(candidate_identity) in norm(other.get("name", "")))
            db_peers = sorted(other["external_id"] for other in live if other["external_id"] != external_id and product_norm(candidate_identity) in {str(other.get("sku_normalized") or product_norm(str(other.get("sku") or ""))), str(other.get("mpn_normalized") or product_norm(str(other.get("mpn") or "")))})
            partition = "exact_safe"
            hold = ""
            output.append({
                "batch": "wave215c_medical_ups", "product_external_id": external_id, "name": name, "category_external_id": row["category_external_id"], "lane": "enersys_ups",
                "device_oem": "", "device_model": "", "battery_pack_ids": "", "voltage_v": item["voltage_v"], "capacity_mah": "",
                "enersys_exact_series": item["series"], "enersys_catalogue_part_number": item["part_number"],
                "source_tier": "manufacturer_primary", "source_publisher": source["publisher"], "source_url": source["source_url"],
                "source_snapshot_path": "../audits/" + snapshot_path.removeprefix("docs/audits/"), "source_snapshot_sha256": source["sha256"],
                "source_assertion": f"exact EnerSys {item['series']} series and catalogue part {item['part_number']} occur in SHA-pinned catalogue",
                "partition": partition, "hold_reason": hold, "full_registry_exact_title_duplicates": "|".join(exact_title),
                "full_registry_candidate_identity_duplicates": "|".join(registry_peers), "live_db_collision_external_ids": "|".join(db_peers),
                "live_current_manufacturer": str(current.get("manufacturer") or ""), "live_current_mpn": str(current.get("mpn") or ""), "safe_to_apply": "true",
            })
            live_checks.append({"candidate_external_id": external_id, "candidate_identity": candidate_identity, "conflicting_external_ids": db_peers})
        else:
            oem, model, pack_ids, voltage, capacity = medical_identity(name)
            if not oem or not model:
                raise SystemExit(f"unparseable medical OEM/model: {external_id}")
            candidate_identity = pack_ids or f"{oem}|{model}|{voltage}|{capacity}"
            registry_peers = sorted(other["registry_id"] for other in registry if other["registry_id"] != external_id and norm(other.get("name", "")) == norm(name))
            # Medical pack labels are candidate identifiers, never MPN assertions.
            db_peers = sorted(other["external_id"] for other in live if other["external_id"] != external_id and norm(name) == norm(str(other.get("name") or "")))
            output.append({
                "batch": "wave215c_medical_ups", "product_external_id": external_id, "name": name, "category_external_id": row["category_external_id"], "lane": "medical_b2b",
                "device_oem": oem, "device_model": model, "battery_pack_ids": pack_ids, "voltage_v": voltage, "capacity_mah": capacity,
                "enersys_exact_series": "", "enersys_catalogue_part_number": "", "source_tier": "", "source_publisher": "", "source_url": "", "source_snapshot_path": "", "source_snapshot_sha256": "",
                "source_assertion": "", "partition": "medical_pack_hold", "hold_reason": "device_compatibility_title_does_not_prove_exact_sellable_battery_pack",
                "full_registry_exact_title_duplicates": "|".join(exact_title), "full_registry_candidate_identity_duplicates": "|".join(registry_peers),
                "live_db_collision_external_ids": "|".join(db_peers), "live_current_manufacturer": str(current.get("manufacturer") or ""), "live_current_mpn": str(current.get("mpn") or ""), "safe_to_apply": "false",
            })
            live_checks.append({"candidate_external_id": external_id, "candidate_identity": candidate_identity, "conflicting_external_ids": db_peers})

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(output)
    manifest_products = [{
        "external_id": row["product_external_id"], "current_name": row["name"], "manufacturer": "EnerSys",
        "mpn": row["enersys_exact_series"], "source_url": row["source_url"],
        "source_kind": "official_manufacturer_catalogue", "source_publisher": row["source_publisher"],
        "checked_at": CHECKED_AT, "product_type": "stationary battery",
        "source_snapshot_path": row["source_snapshot_path"], "source_snapshot_sha256": row["source_snapshot_sha256"],
    } for row in output if row["partition"] == "exact_safe"]
    if len(manifest_products) != 2 or len({product_norm(row["mpn"]) for row in manifest_products}) != 2:
        raise SystemExit("Wave215-C exact-safe manifest must contain two distinct EnerSys series")
    manifest = {"schema_version": 1, "site_key": "microchips-by", "products": manifest_products, "policy": "Exact-safe only: two source-proven EnerSys series; medical packs remain held."}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_sha = sha(MANIFEST)
    # Preserve the manifest's relative `../audits/...` snapshot relationship
    # inside the disposable container directory so the exact host manifest is
    # what Laravel hashes and validates.
    container_root = "/tmp/wave215c-dry-run"
    container_manifest = container_root + "/imports/" + MANIFEST.name
    container_snapshot = container_root + "/audits/sources/wave209a/" + CYCLON_FILE
    prepared = subprocess.run(["docker", "compose", "exec", "-T", "backend", "sh", "-lc", f"mkdir -p {container_root}/imports {container_root}/audits/sources/wave209a"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if prepared.returncode:
        raise SystemExit(f"could not prepare disposable Laravel dry-run directory: {prepared.stderr.strip() or prepared.stdout.strip()}")
    copied_source = subprocess.run(["docker", "compose", "cp", str(ROOT / "docs/audits/sources/wave209a" / CYCLON_FILE), "backend:" + container_snapshot], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if copied_source.returncode:
        raise SystemExit(f"could not copy pinned source snapshot for dry-run: {copied_source.stderr.strip() or copied_source.stdout.strip()}")
    copied = subprocess.run(["docker", "compose", "cp", str(MANIFEST), "backend:" + container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if copied.returncode:
        raise SystemExit(f"could not copy disposable dry-run manifest: {copied.stderr.strip() or copied.stdout.strip()}")
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "catalog:apply-verified-oem-identities", "microchips-by", container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dry = {"mode": "dry_run", "attempted_without_apply": True, "exit_code": run.returncode, "records": len(manifest_products), "manifest_sha256": manifest_sha, "stdout": run.stdout.strip(), "stderr": run.stderr.strip(), "database_mutations": 0, "commercial_fields_changed": 0, "publication_fields_changed": 0}
    if run.returncode or f'"records": {len(manifest_products)}' not in run.stdout:
        raise SystemExit(f"Laravel exact-safe dry-run failed: {run.stderr.strip() or run.stdout.strip()}")
    post_live = {row["external_id"]: row for row in live_products()}
    if any((post_live[external_id].get("manufacturer"), post_live[external_id].get("mpn")) != (live_by_id[external_id].get("manufacturer"), live_by_id[external_id].get("mpn")) for external_id in ids):
        raise SystemExit("Laravel dry-run changed a database identity field")
    LIVE.write_text(json.dumps({"schema_version": 1, "mode": "read_only", "query_exit_code": 0, "candidate_rows_checked": len(output), "checks": live_checks, "database_mutations": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DRY_RUN.write_text(json.dumps(dry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partitions = Counter(row["partition"] for row in output)
    summary = {"schema_version": 1, "wave": "wave215c_medical_ups", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha(INPUT), "rows": len(source_rows)},
        "wave215_partition": {"a_power_systems": len(lane_a), "b_traction": len(lane_b), "c_medical_plus_enersys_ups": len(lane_c), "disjoint_union_rows": len(lane_a | lane_b | lane_c), "pairwise_overlap_rows": 0},
        "target": {"rows": len(output), "medical_b2b_rows": len(medical), "enersys_ups_rows": len(ups)}, "processed2500_overlap_ids": processed_overlap,
        "scope_exclusion": {"automotive_rows": 0, "electronics_rows": 0}, "source_registry": {"path": SOURCE_REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(SOURCE_REGISTRY), "pinned_sources": 1},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(REGISTRY), "rows": len(registry), "collision_rows": sum(bool(row["full_registry_exact_title_duplicates"] or row["full_registry_candidate_identity_duplicates"]) for row in output)},
        "live_db": {"path": LIVE.relative_to(ROOT).as_posix(), "rows_checked": len(output), "collision_rows": sum(bool(row["live_db_collision_external_ids"]) for row in output), "database_mutations": 0},
        "partition_counts": dict(sorted(partitions.items())), "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": manifest_sha, "rows": len(manifest_products), "exact_safe_only": True},
        "laravel_dry_run": {"path": DRY_RUN.relative_to(ROOT).as_posix(), "exit_code": run.returncode, "database_mutations": 0}, "safe_to_apply_records": len(manifest_products), "database_mutations": 0}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("# Wave215-C medical B2B and EnerSys UPS evidence\n\n"
                      "Wave215-C is the disjoint 26-row C lane of Wave214: 24 medical replacement records and two EnerSys UPS records. The medical records remain in `seo:replacement-medical`; their extracted device OEM/model and any legacy pack labels are not represented as sellable-pack OEM identities.\n\n"
                      "The SHA-pinned primary EnerSys Cyclon catalogue explicitly contains BC Cell / 0820-0004 and E Cell / 0850-0004. The exact series in the legacy titles are the bounded product identities; the catalogue part numbers are retained as source evidence and are not substituted into the titles.\n\n"
                      "Registry and live PostgreSQL checks are read only. The two-row exact-safe manifest was passed to Laravel without `--apply`; a second read-only query confirmed no identity field changed.\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "partitions": dict(partitions), "safe_to_apply": len(manifest_products), "laravel_exit": run.returncode, "database_mutations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
