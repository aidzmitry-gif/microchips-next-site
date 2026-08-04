#!/usr/bin/env python3
"""Materialize the Wave223-B evidence into a strict, no-apply Laravel manifest."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
WAVE223B = IMPORTS / "rb-source-backed-description-candidates-wave223b-2026-07-29.json"
WAVE220 = IMPORTS / "rb-source-backed-description-drafts-wave220-2026-07-29.json"
WAVE223A = GEN / "rb-enrichment-queue-wave223c-a-ups-industrial.csv"
STAGEABLE = IMPORTS / "rb-source-backed-description-stageable-wave224b-2026-07-29.json"
LEDGER = GEN / "rb-wave224b-stageable-description-materialization.csv"
SUMMARY = GEN / "rb-wave224b-stageable-description-materialization.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave224b-stageable-description-materialization.md"

ALLOWED_PRODUCT_FIELDS = {
    "external_id", "identity_scope", "manufacturer", "model_core", "technology",
    "source_url", "technical_attributes", "source_kind", "source_tier",
    "source_publisher", "manufacturer_primary", "evidence_scope", "checked_at",
}
LEDGER_FIELDS = [
    "external_id", "manufacturer", "model_core", "technology", "source_url",
    "source_host", "source_kind", "source_tier", "source_publisher", "checked_at",
    "source_manifest", "source_manifest_sha256", "source_manifest_actual_sha256",
    "source_row_verified", "safe_to_apply",
]

# Each URL is registered from already pinned Wave223-B source evidence.  The
# registry is intentionally URL-specific: it does not infer a kind from a file
# extension.  A missing URL, domain, publisher, or kind fails closed.
TRUSTED_SOURCE_REGISTRY = {
    'https://data.energizer.com/pdfs/386-301.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/E95_Max_AP.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/EN91_Industrial_NA.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/L92GL0725.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/a23.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/a544_eu.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/a76.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/cr1632.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/e91_ap.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/en92.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/ind-6lr61pl_eu.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://data.energizer.com/pdfs/l91.pdf': ('data.energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_catalogue'),
    'https://energizer.com/eu/uk/product/energizer-electronic-batteries-a23-e23a/': ('energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_product_page'),
    'https://energizer.com/eu/uk/product/energizer-electronics-batteries-cr2032/': ('energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_product_page'),
    'https://energizer.com/product/power/energizer-max/energizer-max-aaa-batteries-10-pack-triple-a-alkaline-batteries/': ('energizer.com', 'Energizer Holdings, Inc.', 'official_manufacturer_product_page'),
    'https://energy.panasonic.com/dam/master/pdf/en/material/lithium/Introduction_of_coin_type_primary_lithium_batteries_EN.pdf': ('energy.panasonic.com', 'Panasonic Energy Co., Ltd.', 'official_manufacturer_catalogue'),
    'https://energy.panasonic.com/dam/master/pdf/en/material/lithium/Introduction_of_primary_lithium_batteries_cylindrical_type_CR_series_longlife_EN.pdf': ('energy.panasonic.com', 'Panasonic Energy Co., Ltd.', 'official_manufacturer_catalogue'),
    'https://energy.panasonic.com/eu/business/products/lithium/coin-br-high-temp/models/BR1632A': ('energy.panasonic.com', 'Panasonic Energy Co., Ltd.', 'official_manufacturer_product_page'),
    'https://energy.panasonic.com/na/business/products/lithium/coin-br-standard/models/BR2032': ('energy.panasonic.com', 'Panasonic Energy Co., Ltd.', 'official_manufacturer_product_page'),
    'https://energy.panasonic.com/na/business/products/lithium/coin-cr-standard/models/CR2012': ('energy.panasonic.com', 'Panasonic Energy Co., Ltd.', 'official_manufacturer_product_page'),
    'https://energy.panasonic.com/na/business/products/lithium/cylindrical-cr-standard/models/2CR5': ('energy.panasonic.com', 'Panasonic Energy Co., Ltd.', 'official_manufacturer_product_page'),
    'https://energy.panasonic.com/tw/business/products/lithium/cylindrical-br/models/BR-2-3A': ('energy.panasonic.com', 'Panasonic Energy Co., Ltd.', 'official_manufacturer_product_page'),
    'https://saft4u.saft.com/en/download_file/133c84de-f6e9-46b6-a412-fc4ed453fb5c/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://saft4u.saft.com/en/download_file/5241def1-8668-4a68-9d2e-820bd3c68589/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://saft4u.saft.com/en/download_file/738dfd7b-3131-4e31-8924-401cd9a36bbc/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://saft4u.saft.com/en/download_file/8bdd6f76-c9c5-422e-95bd-a18e0a12d80f/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://saft4u.saft.com/en/download_file/da7e4f7d-920b-46c7-bce2-5febf9abe7d1/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://saft4u.saft.com/en/download_file/e9a98622-3564-4570-bca2-d6ce1504589a/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://saft4u.saft.com/fr/download_file/6fbdd60f-bba6-4f67-81a0-85ce1b412664/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://saft4u.saft.com/fr/download_file/e45bd03f-3674-4eeb-bd5d-431d53253df1/English': ('saft4u.saft.com', 'Saft SAS', 'official_manufacturer_catalogue'),
    'https://www.fansobattery.com/?list_43%2F502.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_43%2F503.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_43%2F504.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_43%2F505.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_43%2F506.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_43%2F507.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_43%2F508.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_43%2F=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_catalogue'),
    'https://www.fansobattery.com/?list_44%2F509.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.fansobattery.com/?list_44%2F511.html=': ('www.fansobattery.com', 'FANSO', 'official_manufacturer_product_page'),
    'https://www.pkcell.com/product-category/alkaline-battery/': ('www.pkcell.com', 'Shenzhen Pkcell Battery Co., Ltd.', 'official_manufacturer_catalogue'),
    'https://www.pkcell.com/product/aaa-ni-mh-battery/': ('www.pkcell.com', 'Shenzhen Pkcell Battery Co., Ltd.', 'official_manufacturer_product_page'),
    'https://www.robiton.ru/news/robiton-standard-4-lr-44-moschniy-kompaktniy-istochnik-6-v/': ('www.robiton.ru', 'ROBITON', 'official_manufacturer_product_page'),
    'https://www.robiton.ru/product/12288/': ('www.robiton.ru', 'ROBITON', 'official_manufacturer_product_page'),
    'https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=11&mode=view&offset=0': ('www.vitzrocell.com', 'Vitzrocell Co., Ltd.', 'official_manufacturer_product_page'),
    'https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=6&mode=view&offset=0': ('www.vitzrocell.com', 'Vitzrocell Co., Ltd.', 'official_manufacturer_product_page'),
    'https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=8&mode=view&offset=': ('www.vitzrocell.com', 'Vitzrocell Co., Ltd.', 'official_manufacturer_product_page'),
    'https://www.vitzrocell.com/en/sub/sub02_01.php?cat_no=&idx=9&mode=view&offset=0': ('www.vitzrocell.com', 'Vitzrocell Co., Ltd.', 'official_manufacturer_product_page'),
    'https://www.vitzrocell.com/sub/sub02_01.php?cat_no=&idx=12&mode=view&offset=12': ('www.vitzrocell.com', 'Vitzrocell Co., Ltd.', 'official_manufacturer_product_page'),
    'https://www.vitzrocell.com/sub/sub02_01.php?cat_no=10&idx=7&mode=view&offset=': ('www.vitzrocell.com', 'Vitzrocell Co., Ltd.', 'official_manufacturer_product_page'),
    'https://www.vitzrocell.com/sub/sub02_01.php?cat_no=29&idx=161&mode=view&offset=12': ('www.vitzrocell.com', 'Vitzrocell Co., Ltd.', 'official_manufacturer_product_page'),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def canonical_manufacturer(value: str) -> str:
    return {"Tekcell": "TEKCELL / Vitzrocell"}.get(value, value)


def source_date(path: Path, source_row: dict) -> str:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})\.json$", path.name)
    if match is None:
        raise SystemExit(f"pinned evidence date absent from filename: {path.name}")
    date = match.group(1)
    checked_at = source_row.get("checked_at")
    if checked_at not in (None, "", date):
        raise SystemExit(f"pinned evidence date mismatch: {path.name}")
    return date


def exact_source_row(candidate: dict) -> tuple[Path, dict]:
    relative = candidate.get("source_manifest")
    if not isinstance(relative, str) or not relative.startswith("docs/imports/"):
        raise SystemExit(f"invalid pinned source manifest: {relative!r}")
    path = ROOT / relative
    expected_hash = candidate.get("source_manifest_sha256")
    if not path.is_file() or not isinstance(expected_hash, str) or sha256(path) != expected_hash:
        raise SystemExit(f"source manifest SHA mismatch: {relative}")
    matches = [row for row in read_json(path).get("products", []) if row.get("external_id") == candidate["external_id"]]
    if len(matches) != 1:
        raise SystemExit(f"pinned source must contain one exact external ID: {candidate['external_id']}")
    source = matches[0]
    required = ("manufacturer", "model_core", "technology", "technical_attributes", "source_url")
    if any(not source.get(key) for key in required):
        raise SystemExit(f"pinned source row incomplete: {candidate['external_id']}")
    if canonical_manufacturer(source["manufacturer"]) != candidate["manufacturer"] or source["model_core"] != candidate["model_core"]:
        raise SystemExit(f"Wave223-B candidate differs from its pinned source row: {candidate['external_id']}")
    if source["source_url"] != candidate["source_url"] or source["technical_attributes"] != candidate["technical_attributes"]:
        raise SystemExit(f"Wave223-B source fact drift: {candidate['external_id']}")
    return path, source


def main() -> None:
    candidates = read_json(WAVE223B)["products"]
    candidate_ids = [row["external_id"] for row in candidates]
    if len(candidates) != 294 or len(set(candidate_ids)) != 294:
        raise SystemExit("Wave224-B requires exactly the 294 unique canonical Wave223-B candidates")
    wave220_ids = {row["external_id"] for row in read_json(WAVE220)["products"]}
    wave223a_ids = {row["product_external_id"] for row in read_csv(WAVE223A)}
    if set(candidate_ids) & wave220_ids or set(candidate_ids) & wave223a_ids:
        raise SystemExit("Wave224-B overlaps Wave220 or Wave223-A")

    products, ledger = [], []
    for candidate in candidates:
        path, source = exact_source_row(candidate)
        source_url = source["source_url"]
        registry = TRUSTED_SOURCE_REGISTRY.get(source_url)
        host = urlparse(source_url).hostname
        if registry is None or host != registry[0]:
            raise SystemExit(f"unregistered or domain-mismatched manufacturer source: {source_url}")
        publisher, source_kind = registry[1], registry[2]
        if source_kind not in {"official_manufacturer_catalogue", "official_manufacturer_product_page"}:
            raise SystemExit(f"unsupported registered source kind: {source_url}")
        product = {
            "external_id": source["external_id"], "identity_scope": "model_core",
            "manufacturer": source["manufacturer"], "model_core": source["model_core"],
            "technology": source["technology"], "source_url": source_url,
            "technical_attributes": source["technical_attributes"], "source_kind": source_kind,
            "source_tier": "manufacturer_primary", "source_publisher": publisher,
            "manufacturer_primary": True, "evidence_scope": "model_core",
            "checked_at": source_date(path, source),
        }
        if set(product) != ALLOWED_PRODUCT_FIELDS:
            raise SystemExit("stageable product field contract drift")
        products.append(product)
        ledger.append({
            "external_id": product["external_id"], "manufacturer": product["manufacturer"],
            "model_core": product["model_core"], "technology": product["technology"],
            "source_url": source_url, "source_host": host, "source_kind": source_kind,
            "source_tier": "manufacturer_primary", "source_publisher": publisher,
            "checked_at": product["checked_at"], "source_manifest": path.relative_to(ROOT).as_posix(),
            "source_manifest_sha256": candidate["source_manifest_sha256"],
            "source_manifest_actual_sha256": sha256(path), "source_row_verified": "true",
            "safe_to_apply": "false",
        })
    manifest = {"locale": "ru-BY", "products": products}
    STAGEABLE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    kind_counts = {kind: sum(row["source_kind"] == kind for row in products) for kind in sorted({row["source_kind"] for row in products})}
    summary = {
        "schema_version": 1, "batch": "wave224b_stageable_description_materialization",
        "input": {"path": WAVE223B.relative_to(ROOT).as_posix(), "sha256": sha256(WAVE223B), "rows": 294},
        "nonoverlap_guards": {
            "wave220_manifest": WAVE220.relative_to(ROOT).as_posix(), "wave220_overlap": 0,
            "wave223a_queue": WAVE223A.relative_to(ROOT).as_posix(), "wave223a_overlap": 0,
        },
        "source_registry": {"registered_urls": len(TRUSTED_SOURCE_REGISTRY), "used_urls": len({row["source_url"] for row in products})},
        "manifest": {"path": STAGEABLE.relative_to(ROOT).as_posix(), "sha256": sha256(STAGEABLE), "rows": len(products), "kind_counts": kind_counts},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "safety": {"database_operations": 0, "apply_performed": False, "commercial_changes": 0, "media_changes": 0, "publication_changes": 0, "url_changes": 0, "identity_changes": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave224-B: stageable manufacturer-primary materialization\n\n"
        "The manifest contains exactly the 294 canonical Wave223-B candidates. Every product row copies manufacturer, model core, technology, technical attributes and source URL from the exact external-ID row in its SHA-pinned original source manifest. The only added provenance values are the strict source kind/tier, a publisher from the explicit URL/domain registry, model-core scopes and the date of the pinned source evidence.\n\n"
        f"The explicit registry covers {len(TRUSTED_SOURCE_REGISTRY)} source URLs. It marks {kind_counts.get('official_manufacturer_catalogue', 0)} official catalogues/datasheets and {kind_counts.get('official_manufacturer_product_page', 0)} official HTML product pages. It never infers a kind from a file extension. The stageable product contract has no claim text or fields outside Laravel's source-evidence allow-list.\n\n"
        "No Laravel command or database access was run. The materialization contains no price, stock, media, publication, URL or identity mutation intent; it is a separately reviewed stage input only.\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(products), "kind_counts": kind_counts, "database_operations": 0, "apply_performed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
