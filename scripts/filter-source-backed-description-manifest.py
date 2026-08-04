#!/usr/bin/env python3
"""Create a validated subset of a source-backed description manifest.

The helper keeps the original evidence verbatim and refuses a missing or
duplicated 1C external ID. It is used when an historical batch contains
already-applied or out-of-scope records and only existing draft records must
be sent through the editorial apply gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--external-id", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    requested = list(dict.fromkeys(item.strip() for item in args.external_id if item.strip()))
    if len(requested) != len(args.external_id):
        raise SystemExit("Every --external-id must be non-empty and unique")

    payload = json.loads(args.source.read_text(encoding="utf-8-sig"))
    products = payload.get("products")
    if not isinstance(products, list):
        raise SystemExit("Manifest must contain a products array")
    by_id = {
        str(row.get("external_id", "")).strip(): row
        for row in products
        if isinstance(row, dict) and str(row.get("external_id", "")).strip()
    }
    missing = [external_id for external_id in requested if external_id not in by_id]
    if missing:
        raise SystemExit(f"Requested external_id values missing from manifest: {', '.join(missing)}")

    output = {key: value for key, value in payload.items() if key != "products"}
    output["products"] = [by_id[external_id] for external_id in requested]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"selected_source_backed_drafts: {len(requested)}")


if __name__ == "__main__":
    main()
