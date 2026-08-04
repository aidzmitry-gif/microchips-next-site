#!/usr/bin/env python3
"""Build a fail-closed, exact-only primary-source identity batch for Wave209-C.

The batch deliberately reuses immutable, SHA-pinned manufacturer snapshots from
the earlier source-acquisition waves.  A legacy title is never promoted merely
because its series is known: only the model mappings declared in ``EXACT`` are
allowed into the manifest.
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


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave208.csv"
WAVE206 = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv"
WAVE208S = ROOT / "docs/audits/generated/rb-wave208s-stationary-evidence.csv"
REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
SOURCE_REGISTRY = ROOT / "docs/audits/sources/wave209c-stationary/source-registry.json"
LIVE_GUARD = ROOT / "docs/audits/generated/wave209c-stationary-live-identity-collisions.json"
DRY_RUN = ROOT / "docs/audits/generated/wave209c-stationary-laravel-dry-run.json"
OUTPUT = ROOT / "docs/audits/generated/rb-wave209c-stationary-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave209c-stationary-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave209c-stationary-2026-07-29.json"

EXPECTED = {
    "B.B. Battery": 11, "CSB": 9, "Casil": 3, "Panasonic": 3,
    "Robiton": 2, "Sprinter": 6, "Ventura": 25, "WBR": 10, "Yuasa": 12,
}
CHECKED_AT = "2026-07-29"

SOURCES = {
    "bb_bc": {
        "publisher": "B.B.Battery (Taiwan) Co., Ltd.",
        "url": "https://www.bb-bat.com/en/BC.html",
        "path": "docs/audits/sources/wave206-fiamm-bb-csb/bb-bc-series-2026-07-29.html",
        "kind": "official_manufacturer_product_page",
    },
    "bb_hr": {
        "publisher": "B.B.Battery (Taiwan) Co., Ltd.",
        "url": "https://www.bb-bat.com/en/HR.html",
        "path": "docs/audits/sources/wave206-fiamm-bb-csb/bb-hr-series-2026-07-29.html",
        "kind": "official_manufacturer_product_page",
    },
    "bb_hrl": {
        "publisher": "B.B.Battery (Taiwan) Co., Ltd.",
        "url": "https://www.bb-bat.com/en/HRL.html",
        "path": "docs/audits/sources/wave206-fiamm-bb-csb/bb-hrl-series-2026-07-29.html",
        "kind": "official_manufacturer_product_page",
    },
    "ventura_2023": {
        "publisher": "Ventura",
        "url": "https://ventura-battery.ru/upload/iblock/836/n52d2cyekiv52rav9o0vwctttvggje9j/Catalog_Ventura_2023.pdf",
        "path": "docs/audits/sources/wave206-panasonic-ventura-mnb/ventura-catalogue-2023.txt",
        "snapshot": "docs/audits/sources/wave206-panasonic-ventura-mnb/ventura-catalogue-2023.pdf",
        "kind": "official_manufacturer_catalogue",
    },
}

# Exact model tokens were independently inspected in the pinned snapshot.  Do
# not add a model here from a retailer, a series page, or a compatibility list.
EXACT = {
    "bitrix:1612": ("B.B. Battery", "HRL 50-12", "bb_hrl"),
    "bitrix:1617": ("B.B. Battery", "HR 5.8-12", "bb_hr"),
    "bitrix:1625": ("B.B. Battery", "BC 7.2-12", "bb_bc"),
    "bitrix:1631": ("B.B. Battery", "HRL 75-12", "bb_hrl"),
    "bitrix:1633": ("B.B. Battery", "HR 9-6", "bb_hr"),
    "bitrix:1640": ("B.B. Battery", "HR 9-12", "bb_hr"),
    "bitrix:1645": ("B.B. Battery", "BC 7-12", "bb_bc"),
    "bitrix:1597": ("Ventura", "HRL 12210W", "ventura_2023"),
    "bitrix:1606": ("Ventura", "GP 12-4.5", "ventura_2023"),
    "bitrix:1607": ("Ventura", "GP 6-4.5", "ventura_2023"),
    "bitrix:1609": ("Ventura", "GP 12-40", "ventura_2023"),
    "bitrix:1610": ("Ventura", "GPL 12-40", "ventura_2023"),
    "bitrix:1611": ("Ventura", "GPL 12-45", "ventura_2023"),
    "bitrix:1615": ("Ventura", "GP 12-5", "ventura_2023"),
    "bitrix:1616": ("Ventura", "HR 1221W", "ventura_2023"),
    "bitrix:1620": ("Ventura", "GPL 12-55", "ventura_2023"),
    "bitrix:1622": ("Ventura", "HRL 12260W", "ventura_2023"),
    "bitrix:1623": ("Ventura", "GPL 12-65", "ventura_2023"),
    "bitrix:1624": ("Ventura", "HR 1228W", "ventura_2023"),
    "bitrix:1628": ("Ventura", "GP 12-7.2", "ventura_2023"),
    "bitrix:1632": ("Ventura", "GPL 12-75", "ventura_2023"),
    "bitrix:1635": ("Ventura", "HR 1234W", "ventura_2023"),
    "bitrix:1636": ("Ventura", "HRL 12420W", "ventura_2023"),
    "bitrix:1642": ("Ventura", "GP 12-9", "ventura_2023"),
    "bitrix:1643": ("Ventura", "GP 6-9", "ventura_2023"),
    "bitrix:1797": ("Ventura", "GP 12-2.3", "ventura_2023"),
}

FIELDS = [
    "batch", "product_external_id", "name", "manufacturer_cluster", "model_candidate",
    "partition", "source_tier", "source_publisher", "source_url", "source_assertion",
    "verified_facts", "snapshot_path", "snapshot_sha256", "conflict_reason",
    "duplicate_cluster_ids", "duplicate_decision", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value).upper())


def model_pattern(model: str) -> re.Pattern[str]:
    chars = [re.escape(char) for char in unicodedata.normalize("NFKC", model).upper() if char.isalnum()]
    return re.compile(r"(?<![A-Z0-9])" + r"[\s,._/-]*".join(chars) + r"(?![A-Z0-9])", re.I)


def title_model(name: str, brand: str) -> str:
    match = re.search(rf"\b{re.escape(brand)}\b\s+(.+?)(?:\s+для\b|\s+\()", name, re.I)
    return match.group(1).strip() if match else ""


def source_registry() -> dict[str, dict]:
    records = {}
    for source_id, source in SOURCES.items():
        snapshot = ROOT / source.get("snapshot", source["path"])
        text_path = ROOT / source["path"]
        if not snapshot.is_file() or not text_path.is_file():
            raise SystemExit(f"Pinned source is missing: {source_id}")
        records[source_id] = {
            "source_id": source_id, "publisher": source["publisher"], "source_url": source["url"],
            "source_kind": source["kind"], "checked_at": CHECKED_AT,
            "snapshot_path": snapshot.relative_to(ROOT).as_posix(), "snapshot_sha256": sha256(snapshot),
            "text_path": text_path.relative_to(ROOT).as_posix(), "text_sha256": sha256(text_path),
        }
    SOURCE_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_REGISTRY.write_text(json.dumps({"schema_version": 1, "checked_at": CHECKED_AT, "sources": list(records.values())}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return records


def live_products() -> list[dict]:
    php = (
        "$r=app('db')->table('products')->select('external_id','name','manufacturer','mpn','status')"
        "->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    payload = run.stdout.strip()
    if run.returncode or not payload.startswith("["):
        raise SystemExit(f"Live PostgreSQL collision query failed: {payload or run.stderr.strip()}")
    products = json.loads(payload)
    if len({item["external_id"] for item in products}) != len(products):
        raise SystemExit("Live PostgreSQL registry has duplicate external IDs")
    return products


def main() -> None:
    selected = [row for row in read_csv(INPUT) if row["manufacturer_cluster"] in EXPECTED]
    counts = Counter(row["manufacturer_cluster"] for row in selected)
    selected_ids = {row["product_external_id"] for row in selected}
    if counts != Counter(EXPECTED) or len(selected) != 81 or len(selected_ids) != 81:
        raise SystemExit(f"Wave209-C input drift: rows={len(selected)}, groups={dict(counts)}")
    prior_ids = set()
    for path in (WAVE206, WAVE208S):
        prior_ids.update(row["product_external_id"] for row in read_csv(path))
    overlap = sorted(selected_ids & prior_ids)
    if overlap:
        raise SystemExit(f"Wave209-C repeats previous evidence IDs: {overlap}")
    automotive_or_electronics = [row["product_external_id"] for row in selected if re.search(r"автомоб|стартер|electronics|электрон", row["name"], re.I)]
    if automotive_or_electronics:
        raise SystemExit(f"Out-of-scope automotive/electronics rows: {automotive_or_electronics}")
    if not set(EXACT) <= selected_ids:
        raise SystemExit("Exact source mapping contains an ID outside Wave209-C")

    sources = source_registry()
    source_text = {}
    for source_id, source in sources.items():
        path = ROOT / source["text_path"]
        if sha256(path) != source["text_sha256"]:
            raise SystemExit(f"Pinned source text changed: {source_id}")
        source_text[source_id] = path.read_text(encoding="utf-8-sig", errors="replace")
    for external_id, (_, model, source_id) in EXACT.items():
        if not model_pattern(model).search(source_text[source_id].upper()):
            raise SystemExit(f"Declared exact model is absent from primary snapshot: {external_id} {model}")

    registry = read_csv(REGISTRY)
    registry_peers: dict[str, list[str]] = {}
    for external_id, (brand, model, _) in EXACT.items():
        pattern = model_pattern(model)
        peers = [row["registry_id"] for row in registry if re.search(rf"\b{re.escape(brand)}\b", row["name"], re.I) and pattern.search(row["name"].upper()) and row["registry_id"] != external_id]
        registry_peers[external_id] = sorted(set(peers))

    products = live_products()
    live_by_id = {row["external_id"]: row for row in products}
    missing_or_renamed = [row["product_external_id"] for row in selected if row["product_external_id"] not in live_by_id or live_by_id[row["product_external_id"]]["name"] != row["name"]]
    if missing_or_renamed:
        raise SystemExit(f"Live candidate ID/name mismatch: {missing_or_renamed}")
    live_collisions: dict[str, list[str]] = defaultdict(list)
    for external_id, (brand, model, _) in EXACT.items():
        model_norm = compact(model)
        for product in products:
            if product["external_id"] == external_id:
                continue
            existing_mpn = compact(str(product.get("mpn") or ""))
            existing_maker = compact(str(product.get("manufacturer") or ""))
            name = str(product.get("name") or "")
            name_match = re.search(rf"\b{re.escape(brand)}\b", name, re.I) and bool(model_pattern(model).search(name.upper()))
            identity_match = existing_mpn == model_norm and (not existing_maker or existing_maker == compact(brand))
            if name_match or identity_match:
                live_collisions[external_id].append(product["external_id"])
    live_guard = {
        "schema_version": 1, "checked_at": CHECKED_AT, "query_exit_code": 0,
        "normalizer": "App\\Domain\\Imports\\ProductIdentity::normalize",
        "candidate_rows_checked": len(EXACT), "candidate_external_ids": sorted(EXACT),
        "candidate_mpn_normalized": {external_id: compact(model) for external_id, (_, model, _) in sorted(EXACT.items())},
        "collisions": [{"candidate_external_id": external_id, "conflicting_external_ids": sorted(set(peers))} for external_id, peers in sorted(live_collisions.items())],
        "candidate_rows_with_manufacturer_or_mpn": sorted(
            external_id for external_id in EXACT
            if str(live_by_id[external_id].get("manufacturer") or "") or str(live_by_id[external_id].get("mpn") or "")
        ),
        "database_mutations": 0,
    }
    LIVE_GUARD.write_text(json.dumps(live_guard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output = []
    for candidate in selected:
        external_id = candidate["product_external_id"]
        brand = candidate["manufacturer_cluster"]
        model = title_model(candidate["name"], brand)
        partition = "no_evidence"
        source_tier = publisher = url = assertion = facts = snapshot_path = snapshot_hash = ""
        reason = "No SHA-pinned primary manufacturer page or catalogue proves this exact offered model."
        peers: list[str] = []
        if external_id in EXACT:
            exact_brand, exact_model, source_id = EXACT[external_id]
            if exact_brand != brand or compact(exact_model) != compact(model):
                raise SystemExit(f"Exact mapping/title model drift: {external_id}")
            source = sources[source_id]
            peers = sorted(set(registry_peers[external_id] + live_collisions.get(external_id, [])))
            partition = "exact_safe" if not peers else "conflict"
            source_tier = "manufacturer_primary"
            publisher, url = source["publisher"], source["source_url"]
            assertion = "exact_model_in_pinned_first_party_snapshot"
            facts = f"manufacturer={brand}|mpn={exact_model}"
            snapshot_path, snapshot_hash = source["snapshot_path"], source["snapshot_sha256"]
            reason = "" if not peers else "Full registry or live PostgreSQL identity collision blocks apply."
        output.append({
            "batch": "wave209c_stationary", "product_external_id": external_id, "name": candidate["name"],
            "manufacturer_cluster": brand, "model_candidate": model, "partition": partition,
            "source_tier": source_tier, "source_publisher": publisher, "source_url": url,
            "source_assertion": assertion, "verified_facts": facts, "snapshot_path": snapshot_path,
            "snapshot_sha256": snapshot_hash, "conflict_reason": reason,
            "duplicate_cluster_ids": "|".join(peers),
            "duplicate_decision": "hold_registry_or_live_collision" if peers else "unique_exact_identity" if partition == "exact_safe" else "not_applicable",
            "safe_to_apply": "true" if partition == "exact_safe" else "false",
        })
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(output)
    manifest_rows = []
    for row in output:
        if row["safe_to_apply"] != "true":
            continue
        manifest_rows.append({
            "external_id": row["product_external_id"], "current_name": row["name"],
            "manufacturer": row["manufacturer_cluster"], "mpn": row["model_candidate"],
            "source_url": row["source_url"], "source_kind": SOURCES[EXACT[row["product_external_id"]][2]]["kind"],
            "source_publisher": row["source_publisher"], "checked_at": CHECKED_AT,
            "product_type": "stationary sealed rechargeable battery",
            "source_snapshot_path": (Path("../audits") / Path(row["snapshot_path"]).relative_to("docs/audits")).as_posix(),
            "source_snapshot_sha256": row["snapshot_sha256"],
        })
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    dry_run_verified = False
    if DRY_RUN.is_file():
        dry_run = json.loads(DRY_RUN.read_text(encoding="utf-8-sig"))
        dry_run_verified = (
            dry_run.get("mode") == "dry_run" and dry_run.get("exit_code") == 0
            and dry_run.get("records") == len(manifest_rows)
            and dry_run.get("manifest_sha256") == sha256(MANIFEST)
            and dry_run.get("commercial_fields_changed") == 0
            and dry_run.get("publication_fields_changed") == 0
            and dry_run.get("post_run_rows_with_manufacturer_or_mpn") == 0
            and dry_run.get("database_mutations") == 0
        )
    parts = Counter(row["partition"] for row in output)
    summary = {
        "schema_version": 1, "batch": "wave209c_stationary", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(selected), "manufacturer_counts": dict(sorted(counts.items()))},
        "previous_wave_exclusion": {"wave206": WAVE206.relative_to(ROOT).as_posix(), "wave208s": WAVE208S.relative_to(ROOT).as_posix(), "overlap_ids": overlap},
        "scope_exclusion": {"automotive_rows": 0, "electronics_rows": 0},
        "source_registry": {"path": SOURCE_REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(SOURCE_REGISTRY), "pinned_sources": len(sources)},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "rows": len(registry)},
        "live_collision_guard": {"path": LIVE_GUARD.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE_GUARD), "candidate_rows_checked": len(EXACT), "collision_rows": len(live_guard["collisions"])},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)},
        "partition_counts": dict(sorted(parts.items())),
        "safe_to_apply": {"rows": len(manifest_rows), "external_ids": [row["external_id"] for row in manifest_rows]},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_rows), "laravel_dry_run_verified": dry_run_verified},
        "laravel_dry_run": {"path": DRY_RUN.relative_to(ROOT).as_posix(), "sha256": sha256(DRY_RUN) if DRY_RUN.is_file() else "", "verified": dry_run_verified},
        "policy": {"primary_official_sources_only": True, "exact_safe_manifest_only": True, "automotive_and_electronics": 0, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "partitions": dict(parts), "manifest": len(manifest_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
