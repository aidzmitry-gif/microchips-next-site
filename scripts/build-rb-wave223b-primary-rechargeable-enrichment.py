#!/usr/bin/env python3
"""Build a no-apply, source-backed Wave223-B candidate and hold ledger.

The batch is deliberately limited to the 300 rows in the canonical Wave223-C
primary/rechargeable-cell queue. That queue already removes historical repeats
and applied Wave220 IDs. It does not query a database or execute an import
command.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
QUEUE = GEN / "rb-enrichment-queue-wave223c-b-primary-rechargeable.csv"
WAVE220 = ROOT / "docs/imports/rb-source-backed-description-drafts-wave220-2026-07-29.json"
CANDIDATES = ROOT / "docs/imports/rb-source-backed-description-candidates-wave223b-2026-07-29.json"
EVIDENCE = GEN / "rb-wave223b-primary-rechargeable-evidence.csv"
HOLDS = GEN / "rb-wave223b-primary-rechargeable-holds.csv"
GROUPS = GEN / "rb-wave223b-primary-rechargeable-model-core-groups.csv"
SUMMARY = GEN / "rb-wave223b-primary-rechargeable.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave223b-primary-rechargeable-enrichment.md"

CATEGORIES = {"seo:primary-cells", "seo:rechargeable-cells"}
# Wave223-A is defined to use only seo:batteries-ups and
# seo:batteries-industrial.  Keeping the assertion in code makes the
# no-overlap proof independent of whether A's artefact already exists.
WAVE223A_CATEGORIES = {"seo:batteries-ups", "seo:batteries-industrial"}
OFFICIAL_HOSTS = {
    "Panasonic": {"energy.panasonic.com", "industrial.panasonic.com"},
    "Energizer": {"energizer.com", "data.energizer.com"},
    "Saft": {"saft4u.saft.com"},
    "FANSO": {"www.fansobattery.com"},
    "PKCELL": {"www.pkcell.com"},
    "Robiton": {"www.robiton.ru"},
    "TEKCELL / Vitzrocell": {"www.vitzrocell.com"},
}
MANUFACTURER_ALIASES = {"Tekcell": "TEKCELL / Vitzrocell"}

EVIDENCE_FIELDS = [
    "priority", "product_external_id", "name", "category_external_id",
    "category_name", "manufacturer", "model_core", "group_key",
    "source_url", "source_kind", "source_tier", "source_manifest",
    "source_manifest_sha256", "technical_attributes_json",
    "description_candidate", "partition", "hold_reason", "safe_to_apply",
]
HOLD_FIELDS = [
    "priority", "product_external_id", "name", "category_external_id",
    "manufacturer", "model_core", "hold_reason", "source_manifest",
    "source_url", "safe_to_apply",
]
GROUP_FIELDS = [
    "manufacturer", "model_core", "group_key", "candidate_rows",
    "external_ids_json", "source_urls_json", "source_manifests_json",
    "attribute_key_union_json",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_manufacturer(value: str) -> str:
    return MANUFACTURER_ALIASES.get((value or "").strip(), (value or "").strip())


def normalized_core(value: str) -> str:
    return "".join(char for char in (value or "").upper() if char.isalnum())


def is_official_host(manufacturer: str, source_url: str) -> bool:
    host = (urlparse(source_url).hostname or "").lower()
    return host in OFFICIAL_HOSTS.get(canonical_manufacturer(manufacturer), set())


def source_rank(item: dict, manifest_name: str) -> tuple:
    """Prefer current manufacturer-primary catalogue evidence deterministically."""
    return (
        item.get("source_tier") == "manufacturer_primary",
        item.get("source_kind") == "official_manufacturer_catalogue",
        "official" in (item.get("source_kind") or "").casefold(),
        manifest_name,
        item.get("source_url") or "",
    )


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if CATEGORIES & WAVE223A_CATEGORIES:
        raise SystemExit("Wave223 category partition overlaps")
    wave220_ids = {item["external_id"] for item in read_json(WAVE220)["products"]}
    selected = read_csv(QUEUE)
    selected.sort(key=lambda row: (int(row["priority"]), row["product_external_id"]))
    selected_ids = {row["product_external_id"] for row in selected}
    if len(selected) != 300 or len(selected_ids) != 300:
        raise SystemExit("canonical Wave223-C B queue must contain exactly 300 unique rows")
    if {row["category_external_id"] for row in selected} - CATEGORIES:
        raise SystemExit("canonical Wave223-C B queue contains an out-of-scope category")
    if selected_ids & wave220_ids:
        raise SystemExit("canonical Wave223-C B queue overlaps Wave220 description candidates")

    source_files = sorted(
        path for path in (ROOT / "docs/imports").glob("rb-source-backed-description-drafts-*.json")
        if path != WAVE220
    )
    exact_sources: dict[str, list[tuple[Path, dict]]] = defaultdict(list)
    wanted = set(selected_ids)
    for path in source_files:
        document = read_json(path)
        for item in document.get("products", []):
            if item.get("external_id") not in wanted:
                continue
            if not item.get("source_url") or not item.get("technical_attributes"):
                continue
            exact_sources[item["external_id"]].append((path, item))

    candidate_rows: list[dict] = []
    hold_rows: list[dict] = []
    manifest_products: list[dict] = []
    source_hashes = {path.name: sha256(path) for path in source_files}
    for row in selected:
        external_id = row["product_external_id"]
        options = exact_sources.get(external_id, [])
        usable = [
            (path, item) for path, item in options
            if canonical_manufacturer(item.get("manufacturer", "")) == canonical_manufacturer(row["manufacturer"])
            and is_official_host(item.get("manufacturer", ""), item["source_url"])
            and normalized_core(item.get("model_core", ""))
        ]
        if not usable:
            reason = (
                "no_exact_primary_manufacturer_source_with_model_core"
                if not options else "exact_source_lacks_verified_model_core_or_official_manufacturer_host"
            )
            first_path, first_item = options[0] if options else (None, {})
            hold_rows.append({
                "priority": row["priority"], "product_external_id": external_id, "name": row["name"],
                "category_external_id": row["category_external_id"], "manufacturer": row["manufacturer"],
                "model_core": first_item.get("model_core", ""), "hold_reason": reason,
                "source_manifest": first_path.name if first_path else "",
                "source_url": first_item.get("source_url", ""), "safe_to_apply": "false",
            })
            continue
        path, item = max(usable, key=lambda pair: source_rank(pair[1], pair[0].name))
        manufacturer = canonical_manufacturer(item["manufacturer"])
        model_core = item["model_core"].strip()
        group_key = f"{manufacturer}|{normalized_core(model_core)}"
        description = f"{manufacturer} {model_core}: технические характеристики подтверждены первичным источником производителя."
        candidate = {
            "priority": row["priority"], "product_external_id": external_id, "name": row["name"],
            "category_external_id": row["category_external_id"], "category_name": row["category_name"],
            "manufacturer": manufacturer, "model_core": model_core, "group_key": group_key,
            "source_url": item["source_url"], "source_kind": item.get("source_kind", ""),
            "source_tier": item.get("source_tier", ""), "source_manifest": path.name,
            "source_manifest_sha256": source_hashes[path.name],
            "technical_attributes_json": json.dumps(item["technical_attributes"], ensure_ascii=False, sort_keys=True),
            "description_candidate": description, "partition": "exact_primary_source_candidate",
            "hold_reason": "", "safe_to_apply": "false",
        }
        candidate_rows.append(candidate)
        manifest_products.append({
            "external_id": external_id,
            "identity_scope": "model_core",
            "manufacturer": manufacturer,
            "model_core": model_core,
            "description_candidate": description,
            "technical_attributes": item["technical_attributes"],
            "source_url": item["source_url"],
            "source_kind": item.get("source_kind", ""),
            "source_tier": item.get("source_tier", ""),
            "source_manifest": path.relative_to(ROOT).as_posix(),
            "source_manifest_sha256": source_hashes[path.name],
            "evidence_scope": "exact_external_id_and_model_core",
            "apply_intent": False,
        })

    candidate_rows.sort(key=lambda item: (int(item["priority"]), item["product_external_id"]))
    hold_rows.sort(key=lambda item: (int(item["priority"]), item["product_external_id"]))
    if len(candidate_rows) + len(hold_rows) != 300:
        raise SystemExit("candidate and hold ledger do not cover the deterministic slice")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidate_rows:
        grouped[candidate["group_key"]].append(candidate)
    group_rows = []
    for key in sorted(grouped):
        entries = grouped[key]
        attributes = set()
        for entry in entries:
            attributes.update(json.loads(entry["technical_attributes_json"]).keys())
        group_rows.append({
            "manufacturer": entries[0]["manufacturer"], "model_core": entries[0]["model_core"],
            "group_key": key, "candidate_rows": len(entries),
            "external_ids_json": json.dumps([entry["product_external_id"] for entry in entries], ensure_ascii=False),
            "source_urls_json": json.dumps(sorted({entry["source_url"] for entry in entries}), ensure_ascii=False),
            "source_manifests_json": json.dumps(sorted({entry["source_manifest"] for entry in entries}), ensure_ascii=False),
            "attribute_key_union_json": json.dumps(sorted(attributes), ensure_ascii=False),
        })

    manifest = {
        "schema_version": 1,
        "purpose": "Wave223-B evidence-only description and technical-attribute candidates; no database apply.",
        "locale": "ru-BY",
        "products": manifest_products,
    }
    CANDIDATES.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(EVIDENCE, EVIDENCE_FIELDS, candidate_rows)
    write_csv(HOLDS, HOLD_FIELDS, hold_rows)
    write_csv(GROUPS, GROUP_FIELDS, group_rows)
    summary = {
        "schema_version": 1,
        "batch": "wave223b_primary_rechargeable_evidence_only",
        "selection": {
            "input": QUEUE.relative_to(ROOT).as_posix(), "input_sha256": sha256(QUEUE),
            "wave220_nonoverlap_guard_manifest": WAVE220.relative_to(ROOT).as_posix(),
            "wave220_nonoverlap_guard_ids": len(wave220_ids), "limit": 300,
            "priority_first": int(selected[0]["priority"]), "priority_last": int(selected[-1]["priority"]),
            "categories": sorted(CATEGORIES), "category_counts": dict(sorted(Counter(row["category_external_id"] for row in selected).items())),
            "wave223a_category_overlap": False,
        },
        "coverage": {
            "selected_rows": len(selected), "exact_primary_source_candidates": len(candidate_rows),
            "holds": len(hold_rows), "manufacturer_model_core_groups": len(group_rows),
        },
        "outputs": {
            "candidates_manifest": {"path": CANDIDATES.relative_to(ROOT).as_posix(), "sha256": sha256(CANDIDATES), "rows": len(manifest_products)},
            "evidence": {"path": EVIDENCE.relative_to(ROOT).as_posix(), "sha256": sha256(EVIDENCE), "rows": len(candidate_rows)},
            "holds": {"path": HOLDS.relative_to(ROOT).as_posix(), "sha256": sha256(HOLDS), "rows": len(hold_rows)},
            "groups": {"path": GROUPS.relative_to(ROOT).as_posix(), "sha256": sha256(GROUPS), "rows": len(group_rows)},
        },
        "safety": {
            "database_operations": 0, "apply_performed": False, "price_changes": 0,
            "stock_changes": 0, "identity_changes": 0, "media_changes": 0,
            "publication_changes": 0, "url_changes": 0,
        },
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave223-B: primary/rechargeable cells — source-backed candidates\n\n"
        "Wave223-B uses exactly the 300 unique rows in the canonical Wave223-C B queue (`rb-enrichment-queue-wave223c-b-primary-rechargeable.csv`). That queue has already removed the 596 historical repeats and applied Wave220 IDs; this builder asserts the latter non-overlap again as a guard. The selected priority range is 631–930; it currently contains 300 primary-cell rows. Wave223-A cannot overlap because its declared categories are `seo:batteries-ups` and `seo:batteries-industrial`.\n\n"
        f"Before any content proposal, records are grouped by canonical manufacturer and normalized model core. {len(candidate_rows)} records have an exact external-ID match to a prior source-backed record, an official manufacturer host, a non-empty model core, and source-backed technical attributes. They form {len(group_rows)} manufacturer/model-core groups. The candidate manifest preserves the source URL and SHA-256 of the referenced prior evidence manifest.\n\n"
        f"The hold ledger contains {len(hold_rows)} records: it retains products with no exact primary source or with evidence that cannot be grouped safely by a verified model core. No candidate is applied: this batch performs no database access and proposes no price, stock, identity, media, publication, or URL mutation.\n",
        encoding="utf-8",
    )
    print(json.dumps({"selected": 300, "candidates": len(candidate_rows), "holds": len(hold_rows), "groups": len(group_rows), "apply_performed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
