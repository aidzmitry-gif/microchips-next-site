#!/usr/bin/env python3
"""Materialize the 50 exact-source Delta Wave198 rows into gated app manifests."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def build(evidence_path: Path, contract_path: Path, descriptions_path: Path, previews_path: Path, holds_path: Path | None = None) -> dict[str, object]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    evidence_raw = evidence_path.read_bytes()
    if contract.get("official_evidence_sha256") != hashlib.sha256(evidence_raw).hexdigest():
        raise ValueError("preparation contract does not pin the supplied evidence")
    with evidence_path.open(encoding="utf-8-sig", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    if len(evidence) != contract.get("official_exact_matches") or not evidence:
        raise ValueError("evidence count does not match the preparation contract")

    holds: dict[str, dict[str, str]] = {}
    if holds_path is not None:
        with holds_path.open(encoding="utf-8-sig", newline="") as handle:
            hold_rows = list(csv.DictReader(handle))
        for row in hold_rows:
            external_id = row.get("external_id", "").strip()
            if not external_id or external_id in holds or row.get("reason") != "existing_product_identity":
                raise ValueError("identity holds must be unique and explicitly reasoned")
            holds[external_id] = row

    descriptions, previews = [], []
    seen_external_ids: set[str] = set()
    seen_slugs: set[str] = set()
    for row in evidence:
        external_id, model = row["external_id"].strip(), row["model"].strip()
        if external_id in holds:
            if holds[external_id].get("model", "").strip() != model or not holds[external_id].get("existing_external_id", "").strip():
                raise ValueError("identity hold does not match the exact evidence row")
            continue
        if external_id in seen_external_ids:
            raise ValueError("duplicate external_id in evidence")
        seen_external_ids.add(external_id)
        slug = slugify(f"delta {model}")
        if not slug or slug in seen_slugs:
            raise ValueError("duplicate or empty storefront slug")
        seen_slugs.add(slug)
        descriptions.append({
            "external_id": external_id,
            "identity_scope": "exact",
            "manufacturer": "DELTA",
            "mpn": model,
            "technology": "VRLA AGM",
            "source_url": row["source_url"],
            "technical_attributes": {
                "Номинальное напряжение": f'{row["voltage_v"]} В',
                "Номинальная ёмкость": f'{row["capacity_ah"]} А·ч',
            },
            "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary",
            "source_publisher": row["publisher"],
            "manufacturer_primary": True,
            "evidence_scope": "exact_model",
            "checked_at": "2026-07-29",
        })
        previews.append({
            "external_id": external_id,
            "manufacturer": "DELTA",
            "identity_scope": "exact",
            "mpn": model,
            "source_url": row["source_url"],
            "category_slug": "catalog/industrial-batteries/batteries-ups",
            "product_slug": slug,
            "replace_categories": True,
        })

    purpose = "Wave 198: exact first-party DELTA product-page enrichment for existing namespaced Bitrix drafts only. No price, availability, image, indexability or Offer authorization."
    descriptions_payload = {"schema_version": 1, "purpose": purpose, "locale": "ru-BY", "products": descriptions}
    previews_payload = {"schema_version": 1, "purpose": purpose, "locale": "ru-BY", "products": previews}
    descriptions_path.parent.mkdir(parents=True, exist_ok=True)
    descriptions_path.write_text(json.dumps(descriptions_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    previews_path.write_text(json.dumps(previews_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "records": len(descriptions),
        "identity_holds": len(holds),
        "description_sha256": hashlib.sha256(descriptions_path.read_bytes()).hexdigest(),
        "preview_sha256": hashlib.sha256(previews_path.read_bytes()).hexdigest(),
        "price_authorizations": 0,
        "availability_authorizations": 0,
        "indexability_authorizations": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--descriptions", type=Path, required=True)
    parser.add_argument("--previews", type=Path, required=True)
    parser.add_argument("--holds", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.evidence, args.contract, args.descriptions, args.previews, args.holds), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
