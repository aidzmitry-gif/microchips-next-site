#!/usr/bin/env python3
"""Build Wave211-C from pinned, first-party battery catalogues only.

This is intentionally a read-only, fail-closed evidence builder.  A model is
eligible only when its exact token occurs in an SHA-pinned manufacturer PDF
snapshot.  Manufacturer/family knowledge alone never creates an identity.
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
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave210.csv"
REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
WAVE209A_SOURCES = ROOT / "docs/audits/generated/rb-wave209a-official-source-registry.json"
WAVE206_SOURCES = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/snapshot-index.json"
SOURCE_REGISTRY = ROOT / "docs/audits/sources/wave211c-stationary/source-registry.json"
OUTPUT = ROOT / "docs/audits/generated/rb-wave211c-stationary-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave211c-stationary-evidence.summary.json"
LIVE = ROOT / "docs/audits/generated/wave211c-stationary-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave211c-stationary-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave211c-stationary-2026-07-29.json"
CHECKED_AT = "2026-07-29"

TARGETS = {"Sonnenschein": 40, "Yuasa": 23, "Panasonic": 15, "MNB": 24, "Sprinter": 10, "WBR": 16, "EnerSys": 1}
NO_PINNED_EXACT_SOURCE = {"Yuasa", "Sprinter", "WBR"}
EXIDE_FILES = {
    "a400": "exide-sonnenschein-a400.pdf", "a500": "exide-sonnenschein-a500.pdf",
    "a600": "exide-sonnenschein-a600.pdf", "a600solar": "exide-sonnenschein-a600-solar.pdf",
    "a700": "exide-sonnenschein-a700.pdf", "solar": "exide-sonnenschein-solar-block.pdf",
}
FIELDS = [
    "batch", "product_external_id", "name", "manufacturer_cluster", "model_token", "partition",
    "source_tier", "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256",
    "source_assertion", "verified_facts", "conflict_reason", "full_registry_collision_count",
    "full_registry_collision_external_ids", "live_db_collision_count", "live_db_collision_external_ids",
    "live_current_manufacturer", "live_current_mpn", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


CYRILLIC_TO_LATIN = str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX")


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper().translate(CYRILLIC_TO_LATIN)
    return re.sub(r"[^A-Z0-9]", "", value)


def product_identity_normalize(value: str) -> str:
    return re.sub(r"[\W_]", "", (value or "").casefold(), flags=re.UNICODE)


def model_token(name: str, brand: str) -> str:
    if brand == "Sonnenschein":
        hit = re.search(r"\b(?:A\d{3}/\d+(?:[.,]\d+)?(?:\s*(?:F10|G5|G6|SR|FT|A|S|C))?|(?:SB|S)\s*12/\d+(?:\s*(?:A|G5|G6))?)\b", name, re.I)
        return re.sub(r"\s+", " ", hit.group(0)).strip() if hit else ""
    if brand == "EnerSys":
        # A generic Cyclon D Cell is a cell format, not a uniquely saleable MPN.
        hit = re.search(r"\b(?:\dX)?\d{4}-\d{4}[A-Z]?\b", name, re.I)
        return hit.group(0) if hit else ""
    body = name.split(brand, 1)[1].split("(", 1)[0].strip() if brand in name else ""
    if brand == "MNB":
        body = unicodedata.normalize("NFKC", body).upper().translate(CYRILLIC_TO_LATIN)
        hit = re.search(r"\bM(?:NG|S|M|R|H)\s*\d+(?:[.]\d+)?\s*[-–]\s*\d+(?:\s*[A-Z0-9.]+)?", body)
        return re.sub(r"\s+", " ", hit.group(0)).strip() if hit else ""
    return body


def scope_is_allowed(row: dict[str, str]) -> bool:
    haystack = " ".join(row.get(key, "") for key in ("name", "family_cluster", "category_external_id")).casefold()
    return not any(token in haystack for token in ("automotive", "автомоб", "electronics", "электрон"))


def source_key(brand: str, name: str, token: str) -> str | None:
    if brand == "Panasonic": return "panasonic_vrla_professional_catalogue"
    if brand == "MNB": return "mnb_official_catalogue"
    if brand == "EnerSys": return "enersys-cyclon-selection-guide.pdf"
    if brand != "Sonnenschein": return None
    upper = name.upper()
    if token.startswith("A4"): return EXIDE_FILES["a400"]
    if token.startswith("A5"): return EXIDE_FILES["a500"]
    if token.startswith("A7"): return EXIDE_FILES["a700"]
    if token.startswith(("SB", "S 12")): return EXIDE_FILES["solar"]
    if "SOLAR" in upper: return EXIDE_FILES["a600solar"]
    return EXIDE_FILES["a600"]


def load_sources() -> tuple[dict[str, dict], dict[str, str]]:
    wave209a = json.loads(WAVE209A_SOURCES.read_text(encoding="utf-8-sig"))
    wave206 = json.loads(WAVE206_SOURCES.read_text(encoding="utf-8-sig"))
    records: dict[str, dict] = {}
    texts: dict[str, str] = {}
    for record in wave209a:
        if record["filename"] not in set(EXIDE_FILES.values()) | {"enersys-cyclon-selection-guide.pdf"}:
            continue
        snapshot = ROOT / "docs" / record["snapshot_path"]
        if not snapshot.is_file() or sha256(snapshot) != record["sha256"]:
            raise SystemExit(f"Wave209-A snapshot mismatch: {record['filename']}")
        if urlparse(record["source_url"]).hostname not in {"www.exidegroup.com", "www.enersys.com"}:
            raise SystemExit(f"non-primary Wave209-A source: {record['source_url']}")
        records[record["filename"]] = {
            "source_id": record["filename"], "publisher": record["publisher"], "source_url": record["source_url"],
            "source_kind": "official_manufacturer_catalogue", "checked_at": CHECKED_AT,
            "snapshot_path": snapshot.relative_to(ROOT).as_posix(), "snapshot_sha256": record["sha256"],
        }
        texts[record["filename"]] = normalize("\n".join(page.extract_text() or "" for page in PdfReader(snapshot).pages))
    for record in wave206["sources"]:
        if record["source_id"] not in {"panasonic_vrla_professional_catalogue", "mnb_official_catalogue"}:
            continue
        snapshot, extracted = ROOT / record["snapshot_path"], ROOT / record["extracted_text_path"]
        if not snapshot.is_file() or sha256(snapshot) != record["snapshot_sha256"]:
            raise SystemExit(f"Wave206 snapshot mismatch: {record['source_id']}")
        if not extracted.is_file() or sha256(extracted) != record["extracted_text_sha256"]:
            raise SystemExit(f"Wave206 extracted text mismatch: {record['source_id']}")
        if urlparse(record["source_url"]).hostname not in {"mediap.industry.panasonic.eu", "mnb-battery.ru"}:
            raise SystemExit(f"non-primary Wave206 source: {record['source_url']}")
        records[record["source_id"]] = {key: record[key] for key in ("source_id", "publisher", "source_url", "source_kind", "checked_at", "snapshot_path", "snapshot_sha256")}
        texts[record["source_id"]] = normalize(extracted.read_text(encoding="utf-8-sig"))
    expected = set(EXIDE_FILES.values()) | {"enersys-cyclon-selection-guide.pdf", "panasonic_vrla_professional_catalogue", "mnb_official_catalogue"}
    if set(records) != expected:
        raise SystemExit("Wave211-C source registry is incomplete")
    SOURCE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_REGISTRY.write_text(json.dumps({"schema_version": 1, "checked_at": CHECKED_AT, "policy": "SHA-pinned official manufacturer-primary sources only", "sources": [records[key] for key in sorted(records)]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return records, texts


def prior_evidence_ids() -> tuple[set[str], list[str]]:
    ids: set[str] = set(); files: list[str] = []
    for path in sorted((ROOT / "docs/audits/generated").glob("*evidence*.csv")):
        if path == OUTPUT: continue
        rows = read_csv(path)
        if not rows: continue
        field = "product_external_id" if "product_external_id" in rows[0] else "external_id" if "external_id" in rows[0] else None
        if field:
            ids.update(row[field] for row in rows if row.get(field))
            files.append(path.relative_to(ROOT).as_posix())
    return ids, files


def live_products() -> list[dict]:
    php = "$r=app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized','status')->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only PostgreSQL query failed: {run.stderr.strip() or run.stdout.strip()}")
    products = json.loads(run.stdout.strip())
    if len({row["external_id"] for row in products}) != len(products):
        raise SystemExit("live PostgreSQL has duplicate external IDs")
    return products


def main() -> None:
    selected = [row for row in read_csv(INPUT) if row["manufacturer_cluster"] in TARGETS]
    counts = Counter(row["manufacturer_cluster"] for row in selected)
    ids = [row["product_external_id"] for row in selected]
    if counts != Counter(TARGETS) or len(selected) != 129 or len(ids) != len(set(ids)):
        raise SystemExit(f"Wave211-C target union mismatch: {dict(counts)}")
    automotive_electronics = [row["product_external_id"] for row in selected if not scope_is_allowed(row)]
    if automotive_electronics:
        raise SystemExit(f"automotive/electronics scope gate failed: {automotive_electronics}")
    old_ids, prior_files = prior_evidence_ids()
    overlap = sorted(set(ids) & old_ids)
    if overlap:
        raise SystemExit(f"previous evidence-wave ID overlap: {overlap}")
    sources, texts = load_sources()
    canonical = read_csv(REGISTRY)
    live = live_products(); live_by_id = {row["external_id"]: row for row in live}
    if set(ids) - set(live_by_id):
        raise SystemExit("Wave211-C candidate missing from current PostgreSQL")

    prepared = []
    for row in selected:
        brand, token = row["manufacturer_cluster"], model_token(row["name"], row["manufacturer_cluster"])
        source_id = source_key(brand, row["name"], token)
        exact_in_source = bool(source_id and token and normalize(token) in texts[source_id])
        prepared.append({**row, "model_token": token, "source_id": source_id, "exact_in_source": exact_in_source})
    canonical_collisions: dict[str, list[str]] = defaultdict(list)
    for item in prepared:
        if not item["exact_in_source"]: continue
        for row in canonical:
            name = row.get("name", "")
            registry_token = model_token(name, item["manufacturer_cluster"])
            if (item["manufacturer_cluster"].casefold() in name.casefold()
                    and normalize(registry_token) == normalize(item["model_token"])
                    and row["registry_id"] != item["product_external_id"]):
                canonical_collisions[item["product_external_id"]].append(row["registry_id"])
    output: list[dict[str, str]] = []
    live_collisions = []
    for item in prepared:
        external_id, brand, token = item["product_external_id"], item["manufacturer_cluster"], item["model_token"]
        source = sources.get(item["source_id"] or "")
        partition, reason = "no_evidence", "exact_model_absent_from_pinned_official_sources"
        if brand in NO_PINNED_EXACT_SOURCE:
            reason = "no_SHA_pinned_official_manufacturer_source_for_exact_model"
        elif brand == "EnerSys" and not token:
            reason = "generic_cell_format_is_not_a_unique_saleable_mpn"
        elif item["exact_in_source"]:
            partition, reason = "exact_safe", ""
        registry_peers = sorted(set(canonical_collisions[external_id]))
        if partition == "exact_safe" and registry_peers:
            partition, reason = "conflict", "full_registry_identity_collision"
        current = live_by_id[external_id]
        if partition == "exact_safe" and str(current.get("name") or "") != item["name"]:
            partition, reason = "conflict", "live_current_name_drift"
        # Laravel's bounded matcher deliberately does not transliterate visual
        # Cyrillic/Latin homoglyphs.  Do the same preflight here so a source
        # exact MPN never enters a manifest the command must reject.
        if partition == "exact_safe" and token.casefold() not in item["name"].casefold():
            partition, reason = "conflict", "laravel_bounded_name_matcher_conflict"
        candidate_mpn = product_identity_normalize(token)
        db_peers = []
        if partition == "exact_safe":
            for other in live:
                if other["external_id"] == external_id: continue
                sku = other.get("sku_normalized") or product_identity_normalize(str(other.get("sku") or ""))
                mpn = other.get("mpn_normalized") or product_identity_normalize(str(other.get("mpn") or ""))
                if candidate_mpn and candidate_mpn in {sku, mpn}:
                    db_peers.append(other["external_id"])
            if db_peers:
                partition, reason = "conflict", "live_product_identity_collision"
                live_collisions.append({"candidate_external_id": external_id, "candidate_mpn_normalized": candidate_mpn, "conflicting_external_ids": sorted(db_peers)})
        output.append({
            "batch": "wave211c_stationary", "product_external_id": external_id, "name": item["name"], "manufacturer_cluster": brand,
            "model_token": token, "partition": partition, "source_tier": "manufacturer_primary" if source else "",
            "source_publisher": source["publisher"] if source else "", "source_url": source["source_url"] if source else "",
            "source_snapshot_path": ("../audits/" + source["snapshot_path"].removeprefix("docs/audits/")) if source else "",
            "source_snapshot_sha256": source["snapshot_sha256"] if source else "", "source_assertion": "exact_model_in_pinned_official_catalogue" if item["exact_in_source"] else "",
            "verified_facts": f"manufacturer={brand}|mpn={token}" if partition == "exact_safe" else "", "conflict_reason": reason,
            "full_registry_collision_count": str(len(registry_peers)), "full_registry_collision_external_ids": "|".join(registry_peers),
            "live_db_collision_count": str(len(db_peers)), "live_db_collision_external_ids": "|".join(sorted(db_peers)),
            "live_current_manufacturer": str(current.get("manufacturer") or ""), "live_current_mpn": str(current.get("mpn") or ""),
            "safe_to_apply": "true" if partition == "exact_safe" else "false",
        })
    manifest_products = [{
        "external_id": row["product_external_id"], "current_name": row["name"], "manufacturer": row["manufacturer_cluster"], "mpn": row["model_token"],
        "source_url": row["source_url"], "source_kind": "official_manufacturer_catalogue", "source_publisher": row["source_publisher"], "checked_at": CHECKED_AT,
        "product_type": "stationary battery", "source_snapshot_path": row["source_snapshot_path"], "source_snapshot_sha256": row["source_snapshot_sha256"],
    } for row in output if row["safe_to_apply"] == "true"]
    mpns = [product_identity_normalize(row["mpn"]) for row in manifest_products]
    if not manifest_products or len(mpns) != len(set(mpns)):
        raise SystemExit("exact-safe manifest is empty or repeats a normalized MPN")
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(output)
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_products}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    live_payload = {"schema_version": 1, "mode": "read_only", "query_exit_code": 0, "database": "current Docker PostgreSQL", "normalizer": "App\\Domain\\Imports\\ProductIdentity::normalize", "candidate_rows_checked": sum(row["partition"] == "exact_safe" for row in output) + len(live_collisions), "candidate_external_ids": [row["product_external_id"] for row in output if row["source_assertion"]], "collisions": live_collisions, "database_mutations": 0}
    LIVE.write_text(json.dumps(live_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dry_run_verified = False
    if DRY_RUN.is_file():
        dry = json.loads(DRY_RUN.read_text(encoding="utf-8-sig"))
        dry_run_verified = all((dry.get("mode") == "dry_run", dry.get("exit_code") == 0, dry.get("records") == len(manifest_products), dry.get("manifest_sha256") == sha256(MANIFEST), dry.get("commercial_fields_changed") == 0, dry.get("publication_fields_changed") == 0, dry.get("post_run_rows_with_manufacturer_or_mpn") == 0, dry.get("database_mutations") == 0))
    partitions = Counter(row["partition"] for row in output)
    summary = {"schema_version": 1, "batch": "wave211c_stationary", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(output), "manufacturer_counts": dict(sorted(counts.items()))},
        "previous_wave_exclusion": {"evidence_files_checked": prior_files, "overlap_ids": overlap}, "scope_exclusion": {"automotive_rows": 0, "electronics_rows": 0},
        "source_registry": {"path": SOURCE_REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE_REGISTRY), "pinned_sources": len(sources)},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "rows": len(canonical), "collision_rows": sum(bool(row["full_registry_collision_count"] != "0") for row in output)},
        "live_collision_guard": {"path": LIVE.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE), "collision_rows": len(live_collisions), "database_mutations": 0},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)}, "partition_counts": dict(sorted(partitions.items())),
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_products), "laravel_dry_run_verified": dry_run_verified},
        "laravel_dry_run": {"path": DRY_RUN.relative_to(ROOT).as_posix(), "sha256": sha256(DRY_RUN) if DRY_RUN.is_file() else "", "verified": dry_run_verified},
        "policy": {"official_manufacturer_primary_pinned_sources_only": True, "exact_safe_manifest_only": True, "automotive_and_electronics": 0, "database_mutations": 0}}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "partitions": dict(partitions), "safe_to_apply": len(manifest_products), "dry_run_verified": dry_run_verified}, ensure_ascii=False))


if __name__ == "__main__":
    main()
