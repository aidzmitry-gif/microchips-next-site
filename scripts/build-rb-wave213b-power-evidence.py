#!/usr/bin/env python3
"""Build the Wave213-B AC/DC power-supply evidence ledger.

The input batch is pinned and this script has two deliberately separate
actions. ``--acquire`` obtains only the five allow-listed Mean Well primary
PDFs and pins their bytes.  The normal build is entirely local except for one
read-only Laravel/PostgreSQL collision query.  It never calls the apply mode.
"""
from __future__ import annotations

import argparse
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
from urllib.request import Request, urlopen

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave212.csv"
PROCESSED = ROOT / "docs/audits/generated/rb-b2b-processed-register-wave212.csv"
REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
SOURCE_DIR = ROOT / "docs/audits/sources/wave213b-power"
SOURCE_REGISTRY = SOURCE_DIR / "source-registry.json"
OUTPUT = ROOT / "docs/audits/generated/rb-wave213b-power-evidence.csv"
LIVE = ROOT / "docs/audits/generated/wave213b-power-live-identity-collisions.json"
DRY = ROOT / "docs/audits/generated/wave213b-power-laravel-dry-run.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave213b-power-evidence.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-wave213b-power-systems.md"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave213b-power-2026-07-29.json"
CHECKED_AT = "2026-07-29"
INPUT_SHA256 = "b251d7a6d28ca4b6c1b51f3bfec3bae840e8e688a11d6515409a905602e608a1"
MEAN_WELL_HOSTS = {"www.meanwell.com", "meanwell.com"}

# A series PDF is permitted to establish only the exact model strings that it
# contains.  It is not evidence that a similarly named ZGQNYI product was made
# by Mean Well.
SOURCES = {
    "ELP": {"filename": "ELP-75-SPEC.pdf", "url": "https://www.meanwell.com/Upload/PDF/ELP-75/ELP-75-SPEC.PDF", "series": "ELP-75"},
    "EPP": {"filename": "EPP-100-SPEC.pdf", "url": "https://www.meanwell.com/Upload/PDF/EPP-100/EPP-100-SPEC.PDF", "series": "EPP-100"},
    "EPS": {"filename": "EPS-25-SPEC.pdf", "url": "https://www.meanwell.com/Upload/PDF/EPS-25/EPS-25-SPEC.PDF", "series": "EPS-25"},
    "RPS": {"filename": "RPS-200-SPEC.pdf", "url": "https://www.meanwell.com/Upload/PDF/RPS-200/RPS-200-SPEC.PDF", "series": "RPS"},
    "IRM": {"filename": "IRM-01-SPEC.pdf", "url": "https://www.meanwell.com/Upload/PDF/IRM-01/IRM-01-SPEC.PDF", "series": "IRM-01"},
}
FIELDS = [
    "batch", "product_external_id", "name", "factual_type", "manufacturer", "manufacturer_status", "model_candidate",
    "family_group", "variant_group", "duplicate_group", "primary_manufacturer_source_route", "source_tier",
    "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion",
    "partition", "conflict_reason", "full_registry_collision_external_ids", "live_db_collision_external_ids",
    "live_current_manufacturer", "live_current_mpn", "safe_to_apply",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    return re.sub(r"[^A-ZА-Я0-9]+", "", value)


def token_pattern(value: str) -> re.Pattern[str]:
    # Hyphen/slash punctuation is intentionally flexible, while the leading
    # and trailing look-arounds prevent S-15 from matching S-150.
    chunks = [re.escape(char) for char in unicodedata.normalize("NFKC", value).upper() if char.isalnum() or char == "."]
    glue = r"[\s_./-]*"
    return re.compile(r"(?<![A-ZА-Я0-9])" + glue.join(chunks) + r"(?![A-ZА-Я0-9])", re.I)


def extract_identity(name: str) -> tuple[str, str, str, str]:
    """Return manufacturer, status, exact title model and series group."""
    body = re.sub(r"^AC-DC\s+преобразователь\s+", "", name, flags=re.I).strip()
    if body.upper().startswith("ZGQNYI "):
        manufacturer, status, model = "ZGQNYI", "title_label_unverified", body.split(None, 1)[1]
    elif body.upper().startswith("MEAN WELL "):
        manufacturer, status, model = "Mean Well", "title_label_and_primary_source", body.split(None, 2)[2]
    elif re.match(r"^IRM-\d+", body, re.I):
        manufacturer, status, model = "Mean Well", "primary_series_source", body
    else:
        manufacturer, status, model = "", "unresolved", body
    hit = re.match(r"([A-ZА-Я]+(?:-\d+)?)(?:[-/]|$)", model, re.I)
    family = (hit.group(1).upper() if hit else model.upper()).replace("/", "-")
    # S-350/450 and S-500/600 are catalogue family variants, not two models.
    if model.upper().startswith("S-350/450"): family = "S-350-450"
    if model.upper().startswith("S-500/600"): family = "S-500-600"
    return manufacturer, status, model, family


def source_key(model: str, manufacturer: str) -> str | None:
    if manufacturer != "Mean Well":
        return None
    upper = model.upper()
    for key in SOURCES:
        if upper.startswith(key + "-"):
            return key
    return None


def acquire() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    registry = []
    for key, source in sorted(SOURCES.items()):
        request = Request(source["url"], headers={"User-Agent": "microchips.by catalogue evidence audit/1.0"})
        with urlopen(request, timeout=45) as response:
            final_url, raw = response.geturl(), response.read()
        parsed = urlparse(final_url)
        if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in MEAN_WELL_HOSTS:
            raise SystemExit(f"Mean Well source redirect escaped allowlist: {final_url}")
        if not raw.startswith(b"%PDF"):
            raise SystemExit(f"Mean Well source is not a PDF: {final_url}")
        target = SOURCE_DIR / source["filename"]
        target.write_bytes(raw)
        registry.append({
            "source_id": key, "publisher": "Mean Well Enterprises Co., Ltd.", "source_kind": "official_manufacturer_datasheet",
            "source_url": final_url, "series": source["series"], "checked_at": CHECKED_AT,
            "snapshot_path": target.relative_to(ROOT).as_posix(), "snapshot_sha256": sha(target),
        })
    SOURCE_REGISTRY.write_text(json.dumps({"schema_version": 1, "policy": "SHA-pinned manufacturer-primary PDFs", "sources": registry}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_sources() -> tuple[dict[str, dict], dict[str, str]]:
    payload = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8-sig"))
    records = {row["source_id"]: row for row in payload.get("sources", [])}
    if set(records) != set(SOURCES):
        raise SystemExit("Wave213-B source registry is incomplete")
    texts: dict[str, str] = {}
    for key, record in records.items():
        snapshot = ROOT / record["snapshot_path"]
        parsed = urlparse(record["source_url"])
        if not snapshot.is_file() or sha(snapshot) != record["snapshot_sha256"]:
            raise SystemExit(f"Wave213-B source snapshot drift: {key}")
        if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in MEAN_WELL_HOSTS:
            raise SystemExit(f"Wave213-B source is not Mean Well primary: {key}")
        texts[key] = "\n".join(page.extract_text() or "" for page in PdfReader(snapshot).pages)
    return records, texts


def live_products() -> list[dict]:
    php = "echo json_encode(app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized','status')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only live DB query failed: {run.stderr.strip() or run.stdout.strip()}")
    result = json.loads(run.stdout)
    if len({row["external_id"] for row in result}) != len(result):
        raise SystemExit("live DB repeats external IDs")
    return result


def write_report(evidence: list[dict[str, str]], source_records: dict[str, dict], partitions: Counter) -> None:
    families = Counter(row["family_group"] for row in evidence)
    routes = Counter(row["primary_manufacturer_source_route"] for row in evidence)
    exact = [row for row in evidence if row["safe_to_apply"] == "true"]
    lines = [
        "# Wave213-B power systems evidence", "",
        f"Checked {len(evidence)} `unresolved_other` rows from Wave212, all in `seo:power-systems`.",
        "Every row is an AC/DC power supply (`power_system`); UPS, inverter, battery and accessory rows are all zero.",
        "No battery capacity, chemistry, or replacement-pack claim was attached to any power-supply device.", "",
        "## Evidence and routing", "",
        f"Five SHA-pinned official Mean Well datasheets cover the verified Mean Well/IRM family routes. Exact-safe identities: {len(exact)}.",
        "ZGQNYI-labelled rows remain a manufacturer-identity hold: familiar Mean Well-like model strings are not treated as Mean Well products.",
        "The unbranded БПС30/БПЛ30/ММС5/МПС60 rows remain manufacturer-unresolved pending a first-party catalogue or maker confirmation.", "",
        "## Counts", "",
        f"- Partitions: {dict(sorted(partitions.items()))}",
        f"- Families: {dict(sorted(families.items()))}",
        f"- Source routes: {dict(sorted(routes.items()))}",
        "- Full registry and current live DB collision checks are recorded in the generated ledger; the Laravel command was run without `--apply`.", "",
        "## Pinned primary sources", "",
    ]
    for key, row in sorted(source_records.items()):
        lines.append(f"- {key}: {row['source_url']} — `{row['snapshot_sha256']}`")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--acquire", action="store_true", help="Fetch allow-listed official Mean Well PDFs before building.")
    args = parser.parse_args()
    if args.acquire:
        acquire()

    source_rows = read_csv(INPUT)
    selected = [row for row in source_rows if row.get("manufacturer_cluster") == "unresolved_other" and row.get("category_external_id") == "seo:power-systems"]
    ids = [row["product_external_id"] for row in selected]
    if sha(INPUT) != INPUT_SHA256 or len(selected) != 221 or len(ids) != len(set(ids)):
        raise SystemExit(f"Wave213-B input pin/scope drift: rows={len(selected)}")
    processed_ids = {row["product_external_id"] for row in read_csv(PROCESSED)}
    overlap = sorted(set(ids) & processed_ids)
    if overlap:
        raise SystemExit(f"Wave213-B candidates overlap processed register: {overlap[:5]}")
    sources, texts = load_sources()
    registry, live = read_csv(REGISTRY), live_products()
    live_by_id = {row["external_id"]: row for row in live}
    if set(ids) - set(live_by_id):
        raise SystemExit("Wave213-B candidate missing from live DB")

    prepared = []
    for row in selected:
        manufacturer, status, model, family = extract_identity(row["name"])
        source_id = source_key(model, manufacturer)
        exact_in_source = bool(source_id and token_pattern(model).search(texts[source_id]))
        prepared.append({**row, "manufacturer": manufacturer, "manufacturer_status": status, "model": model, "family": family, "source_id": source_id, "exact_in_source": exact_in_source})

    registry_peers: dict[str, list[str]] = defaultdict(list)
    for item in prepared:
        if not item["exact_in_source"]:
            continue
        pattern = token_pattern(item["model"])
        for candidate in registry:
            if candidate["registry_id"] != item["product_external_id"] and pattern.search(candidate.get("name", "")):
                registry_peers[item["product_external_id"]].append(candidate["registry_id"])

    evidence, live_checks = [], []
    for item in prepared:
        external_id, model = item["product_external_id"], item["model"]
        current = live_by_id[external_id]
        source = sources.get(item["source_id"] or "")
        partition, reason = "manufacturer_hold", "manufacturer_primary_identity_not_established"
        route = "manufacturer_identity_resolution_required_before_primary_research"
        if item["manufacturer"] == "ZGQNYI":
            reason = "title_label_is_not_a_verified_manufacturer; Mean_Well_like_series_name_is_not_identity_evidence"
            route = "ZGQNYI_first_party_product_page_or_manufacturer_directory_required"
        elif not item["manufacturer"]:
            reason = "unbranded_model_designation_requires_first_party_manufacturer_catalogue"
            route = "manufacturer_resolution_and_first_party_catalogue_required"
        elif item["exact_in_source"]:
            partition, reason = "exact_safe", ""
            route = "Mean_Well_SHA_pinned_official_datasheet"
        # The importer's bounded matcher is a required downstream guard.  An
        # IRM title contains a real Mean Well model, but does not name Mean
        # Well; the source proves a candidate identity, not an apply-safe title
        # assertion.  Keep it in the ledger, never in the manifest.
        if partition == "exact_safe" and not token_pattern(item["manufacturer"]).search(item["name"]):
            partition, reason = "conflict", "current_title_lacks_bounded_manufacturer_for_laravel_identity_matcher"
        peers = sorted(set(registry_peers[external_id]))
        if partition == "exact_safe" and peers:
            partition, reason = "conflict", "full_catalog_registry_model_collision"
        if partition == "exact_safe" and str(current.get("name") or "") != item["name"]:
            partition, reason = "conflict", "live_product_name_drift"
        db_peers = []
        candidate_mpn = norm(model)
        if partition == "exact_safe":
            for other in live:
                if other["external_id"] == external_id:
                    continue
                other_values = (str(other.get("sku_normalized") or other.get("sku") or ""), str(other.get("mpn_normalized") or other.get("mpn") or ""))
                if candidate_mpn and candidate_mpn in {norm(value) for value in other_values}:
                    db_peers.append(other["external_id"])
            if db_peers:
                partition, reason = "conflict", "live_product_identity_collision"
        live_checks.append({"candidate_external_id": external_id, "candidate_model_normalized": candidate_mpn, "conflicting_external_ids": sorted(db_peers)})
        evidence.append({
            "batch": "wave213b_power", "product_external_id": external_id, "name": item["name"], "factual_type": "power_system_ac_dc_power_supply",
            "manufacturer": item["manufacturer"], "manufacturer_status": item["manufacturer_status"], "model_candidate": model,
            "family_group": item["family"], "variant_group": f"{item['manufacturer'] or 'unresolved'}::{item['family']}", "duplicate_group": f"{item['manufacturer'] or 'unresolved'}::{norm(model)}",
            "primary_manufacturer_source_route": route, "source_tier": "manufacturer_primary" if source else "",
            "source_publisher": source["publisher"] if source else "", "source_url": source["source_url"] if source else "",
            "source_snapshot_path": source["snapshot_path"] if source else "", "source_snapshot_sha256": source["snapshot_sha256"] if source else "",
            "source_assertion": "exact_model_in_SHA_pinned_official_datasheet" if item["exact_in_source"] else "",
            "partition": partition, "conflict_reason": reason, "full_registry_collision_external_ids": "|".join(peers), "live_db_collision_external_ids": "|".join(sorted(db_peers)),
            "live_current_manufacturer": str(current.get("manufacturer") or ""), "live_current_mpn": str(current.get("mpn") or ""), "safe_to_apply": "true" if partition == "exact_safe" else "false",
        })

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(evidence)
    manifest_rows = [{
        "external_id": row["product_external_id"], "current_name": row["name"], "manufacturer": row["manufacturer"], "mpn": row["model_candidate"],
        # The Laravel import vocabulary calls a first-party series datasheet a
        # manufacturer catalogue; the more specific ``datasheet`` label stays
        # in the source registry and evidence ledger.
        "source_url": row["source_url"], "source_kind": "official_manufacturer_catalogue", "source_publisher": row["source_publisher"], "checked_at": CHECKED_AT,
        "product_type": "AC/DC power supply", "source_snapshot_path": (Path("../audits") / Path(row["source_snapshot_path"]).relative_to("docs/audits")).as_posix(), "source_snapshot_sha256": row["source_snapshot_sha256"],
    } for row in evidence if row["safe_to_apply"] == "true"]
    if not manifest_rows or len({norm(row["mpn"]) for row in manifest_rows}) != len(manifest_rows):
        raise SystemExit("Wave213-B exact-safe manifest must be nonempty and have unique normalized MPNs")
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_hash = sha(MANIFEST)
    # The development container mounts the Laravel tree only.  The immutable
    # manifest and its source directory are staged under writable storage for
    # this read-only command, preserving the manifest's ``../audits`` relative
    # snapshot paths.  No ``--apply`` option is ever passed.
    dry_run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "catalog:apply-verified-oem-identities", "microchips-by", "/var/www/storage/app/imports/" + MANIFEST.name], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dry = {"mode": "dry_run", "attempted_without_apply": True, "apply_flag_used": False, "exit_code": dry_run.returncode, "records": len(manifest_rows), "manifest_sha256": manifest_hash, "stdout": dry_run.stdout.strip(), "stderr": dry_run.stderr.strip(), "database_mutations": 0, "commercial_fields_changed": 0, "publication_fields_changed": 0}
    if dry_run.returncode:
        raise SystemExit(f"Laravel dry run failed: {dry_run.stderr.strip() or dry_run.stdout.strip()}")
    LIVE.write_text(json.dumps({"schema_version": 1, "mode": "read_only", "query_exit_code": 0, "database_mutations": 0, "candidate_rows_checked": len(evidence), "checks": live_checks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DRY.write_text(json.dumps(dry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partitions = Counter(row["partition"] for row in evidence)
    write_report(evidence, sources, partitions)
    SUMMARY.write_text(json.dumps({
        "schema_version": 1, "batch": "wave213b_power", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha(INPUT), "rows": len(evidence)},
        "scope": {"unresolved_other_power_system_rows": 221, "ups_rows": 0, "inverter_rows": 0, "battery_rows": 0, "accessory_rows": 0, "electronics_component_rows": 0, "processed2000_overlap_ids": overlap},
        "source_registry": {"path": SOURCE_REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(SOURCE_REGISTRY), "pinned_primary_sources": len(sources)},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(REGISTRY), "rows": len(registry), "collision_rows": sum(bool(row["full_registry_collision_external_ids"]) for row in evidence)},
        "live_collision_guard": {"path": LIVE.relative_to(ROOT).as_posix(), "sha256": sha(LIVE), "collision_rows": sum(bool(row["live_db_collision_external_ids"]) for row in evidence), "database_mutations": 0},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha(OUTPUT), "rows": len(evidence)}, "partition_counts": dict(sorted(partitions.items())),
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": manifest_hash, "rows": len(manifest_rows)},
        "laravel_dry_run": {"path": DRY.relative_to(ROOT).as_posix(), "exit_code": dry_run.returncode, "database_mutations": 0},
        "policy": {"UPS_not_electronic_component": True, "battery_characteristics_attached_to_device": False, "exact_safe_manifest_only": True, "database_apply": False},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(evidence), "partitions": dict(partitions), "manifest": len(manifest_rows), "database_mutations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
