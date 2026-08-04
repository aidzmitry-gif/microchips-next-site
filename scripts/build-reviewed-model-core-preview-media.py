#!/usr/bin/env python3
"""Build noindex-preview and legacy-media manifests from completed visual review."""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def slug(value: str) -> str:
    aliases = {"b.b. battery": "bb-battery"}
    value = aliases.get(value.casefold(), value)
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def site_state_by_external_id(raw: object) -> dict[str, dict[str, object]]:
    if not isinstance(raw, list):
        raise ValueError("site state must be a JSON array")
    result: dict[str, dict[str, object]] = {}
    for index, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValueError(f"site state row {index} must be an object")
        product = row.get("product")
        external_id = row.get("external_id")
        if isinstance(product, dict):
            external_id = product.get("external_id")
        if not isinstance(external_id, str) or not external_id.strip():
            raise ValueError(f"site state row {index} has no external_id")
        if external_id in result:
            raise ValueError(f"duplicate site state external_id {external_id}")
        result[external_id] = row
    return result


def build(candidates_path: Path, bundle_path: Path, visual_paths: list[Path], state_path: Path,
          preview_output: Path, media_output: Path, excluded_ids: set[str]) -> dict[str, int]:
    candidates = {row["external_id"]: row for row in rows(candidates_path)}
    bundle = {row["external_id"]: row for row in rows(bundle_path)}
    state = site_state_by_external_id(json.loads(state_path.read_text(encoding="utf-8")))
    visual: dict[str, dict[str, str]] = {}
    for path in visual_paths:
        for row in rows(path):
            if row["external_id"] in visual:
                raise ValueError(f"duplicate visual verdict for {row['external_id']}")
            visual[row["external_id"]] = row

    preview: list[dict[str, object]] = []
    media: list[dict[str, str]] = []
    for external_id, verdict in sorted(visual.items()):
        if verdict.get("verdict") != "PASS" or external_id in excluded_ids:
            continue
        candidate = candidates.get(external_id)
        asset = bundle.get(external_id)
        product = state.get(external_id)
        if candidate is None or asset is None or product is None:
            raise ValueError(f"missing candidate, asset or site state for {external_id}")
        identity_scope = asset.get("identity_scope")
        if identity_scope not in {"exact", "model_core"} or not asset.get("identity"):
            raise ValueError(f"{external_id} is not a verified exact/model_core candidate")
        manufacturer = asset["manufacturer"].strip()
        identity = asset["identity"].strip()
        category_slug = ("catalog/industrial-batteries/batteries-industrial"
                         if identity == "STC 500" else "catalog/industrial-batteries/batteries-ups")
        preview_row: dict[str, object] = {
            "external_id": external_id,
            "manufacturer": manufacturer,
            "identity_scope": identity_scope,
            "source_url": candidate["source_url"],
            "category_slug": category_slug,
            "product_slug": slug(manufacturer + " " + identity),
            "replace_categories": True,
        }
        preview_row["mpn" if identity_scope == "exact" else "model_core"] = identity
        if product.get("price") is not None:
            preview_row["allow_verified_price"] = True
        preview.append(preview_row)
        media_row = {
            "external_id": external_id,
            "manufacturer": manufacturer,
            "identity_scope": identity_scope,
            "asset_file": asset["asset_file"],
            "sha256": asset["sha256"],
            "archive_member": asset["archive_member"],
            "rights_basis": "Company-owned Microchips legacy Bitrix upload backup; exact model and rating were visually verified.",
            "identity_evidence_level": "visible_exact_mpn" if identity_scope == "exact" else "visible_exact_model_core",
            "visual_verification_note": verdict["note"],
        }
        media_row["mpn" if identity_scope == "exact" else "model_core"] = identity
        media.append(media_row)

    preview_output.write_text(json.dumps({
        "schema_version": 2,
        "purpose": "Noindex preview for source-backed products with company-owned visually verified exact/model-core media.",
        "locale": "ru-BY",
        "products": preview,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    media_output.write_text(json.dumps({
        "schema_version": 3,
        "purpose": "Company-owned Bitrix images with visible exact identity and material rating.",
        "images": media,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "visual_rows": len(visual),
        "visual_pass": sum(1 for row in visual.values() if row.get("verdict") == "PASS"),
        "explicit_scope_exclusions": len(excluded_ids & set(visual)),
        "preview_products": len(preview),
        "media_images": len(media),
    }
    preview_output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--visual", type=Path, action="append", required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--preview-output", type=Path, required=True)
    parser.add_argument("--media-output", type=Path, required=True)
    parser.add_argument("--exclude-id", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(build(args.candidates, args.bundle, args.visual, args.state,
                           args.preview_output, args.media_output, set(args.exclude_id)), ensure_ascii=False))


if __name__ == "__main__":
    main()
