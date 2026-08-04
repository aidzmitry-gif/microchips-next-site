#!/usr/bin/env python3
"""Convert approved MPN evidence into an importable editorial-draft package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True, action="append")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    decisions = []
    for evidence in args.evidence:
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        batch = payload.get("decisions")
        if not isinstance(batch, list):
            raise SystemExit("Evidence package must contain a decisions array")
        decisions.extend(batch)
    output = []
    seen = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            raise SystemExit("Decision is not an object")
        external_id = str(decision.get("external_id_1c", "")).strip()
        if not external_id or external_id in seen:
            raise SystemExit(f"Missing or duplicate external_id_1c: {external_id!r}")
        seen.add(external_id)
        output.append({
            "external_id": external_id,
            "manufacturer": str(decision.get("manufacturer", "")).strip(),
            "mpn": str(decision.get("confirmed_mpn", "")).strip(),
            "technology": str(decision.get("category", "")).strip(),
            "source_url": str(decision.get("source_url", "")).strip(),
            "source_kind": str(decision.get("source_kind", "")).strip(),
            "checked_at": str(decision.get("checked_at", "")).strip(),
        })
    if any(not item["manufacturer"] or not item["mpn"] or not item["source_url"] for item in output):
        raise SystemExit("Every decision requires manufacturer, mpn and source_url")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"locale": "ru-BY", "products": output}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"source-backed drafts: {len(output)}")


if __name__ == "__main__":
    main()
