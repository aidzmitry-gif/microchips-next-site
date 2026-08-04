#!/usr/bin/env python3
"""Merge independently reviewed Wave229 media packages with replay guards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "external_id",
    "media_id",
    "content_sha256",
    "storage_path",
    "rights_basis",
    "identity_scope",
    "mpn",
    "identity_evidence_level",
    "visual_verification_note",
    "reviewed_at",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def merge_payloads(payloads: list[tuple[str, dict]], reviewed_payloads: list[dict]) -> list[dict]:
    prior_external_ids: set[str] = set()
    prior_media_ids: set[int] = set()
    prior_hashes: set[str] = set()
    for payload in reviewed_payloads:
        for row in payload.get("images", []):
            prior_external_ids.add(row["external_id"])
            prior_media_ids.add(int(row["media_id"]))
            prior_hashes.add(row["content_sha256"].lower())

    images: list[dict] = []
    seen_external_ids: set[str] = set()
    seen_media_ids: set[int] = set()
    seen_hashes: set[str] = set()
    for source_name, payload in payloads:
        if payload.get("locale") != "ru-BY" or not payload.get("images"):
            raise ValueError(f"{source_name}: expected ru-BY and a non-empty images list")
        for row in payload["images"]:
            missing = REQUIRED.difference(row)
            if missing:
                raise ValueError(f"{source_name}: missing fields {sorted(missing)}")
            if row["identity_scope"] != "exact" or row["identity_evidence_level"] != "visible_exact_mpn":
                raise ValueError(f"{source_name}: only visible exact-MPN evidence is accepted")
            if not str(row["mpn"]).strip() or not str(row["visual_verification_note"]).strip():
                raise ValueError(f"{source_name}: empty MPN or visual verification note")
            external_id = row["external_id"]
            media_id = int(row["media_id"])
            content_hash = row["content_sha256"].lower()
            if external_id in prior_external_ids or media_id in prior_media_ids or content_hash in prior_hashes:
                raise ValueError(f"{source_name}: replay of previously reviewed media for {external_id}")
            if external_id in seen_external_ids or media_id in seen_media_ids or content_hash in seen_hashes:
                raise ValueError(f"{source_name}: duplicate product/media/hash for {external_id}")
            seen_external_ids.add(external_id)
            seen_media_ids.add(media_id)
            seen_hashes.add(content_hash)
            images.append(row)

    images.sort(key=lambda row: (int(row["external_id"].split(":", 1)[1]), int(row["media_id"])))
    return images


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", required=True, type=Path)
    parser.add_argument("--reviewed", action="append", default=[], type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    images = merge_payloads(
        [(str(path), load(path)) for path in args.manifest],
        [load(path) for path in args.reviewed],
    )
    output = {
        "schema_version": 1,
        "purpose": "Promote only independently machine-vision-reviewed Wave229 company-owned legacy media with a visible exact MPN.",
        "locale": "ru-BY",
        "images": images,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"images": len(images), "database_apply": False}))


if __name__ == "__main__":
    main()
