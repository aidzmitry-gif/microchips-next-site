#!/usr/bin/env python3
"""Build a fail-closed Panasonic CR/BR Wave200 research manifest.

This is deliberately a research manifest, not an importer.  A catalog label is
not manufacturer evidence and no source or technical fact is inferred here.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re
from pathlib import Path

MODEL = re.compile(r"(?i)(?<![A-Z0-9])(CR|BR)[0-9][A-Z0-9/.-]*")
EXCLUDED_UNPARSEABLE_VARIANTS = {"23927"}  # CR2450 W/L: pack/lead variant is not exact in the catalog label.

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

def build(source: Path, out_dir: Path, expected: int = 153) -> dict[str, object]:
    with source.open(encoding="utf-8-sig", newline="") as f:
        raw = list(csv.DictReader(f))
    rows: list[dict[str, str]] = []
    for row in raw:
        name, ident = (row.get("name") or "").strip(), (row.get("bitrix_id") or "").strip()
        match = MODEL.search(name) if "panasonic" in name.casefold() else None
        if not match or ident in EXCLUDED_UNPARSEABLE_VARIANTS:
            continue
        # Preserve the complete catalog label as the pack-variant key.  The
        # model token is only a lookup aid and cannot authorize fact reuse.
        rows.append({"product_external_id": f"bitrix:{ident}", "legacy_name": name,
                     "manufacturer": "Panasonic", "family": match.group(1).upper(),
                     "model_token": match.group(0).upper(), "pack_variant_key": name,
                     "category_external_id": "seo:primary-cells",
                     "required_gate": "exact_first_party_panasonic_page_or_datasheet_per_pack_variant",
                     "safe_to_apply": "false"})
    if len(rows) != expected:
        raise ValueError(f"expected {expected} candidates, got {len(rows)}")
    if len({r['product_external_id'] for r in rows}) != len(rows):
        raise ValueError("duplicate product_external_id")
    fields = list(rows[0])
    out = out_dir / "rb-panasonic-wave200-candidates.csv"; write_csv(out, rows, fields)
    summary = {"wave": "wave200", "source": str(source), "source_sha256": sha(source),
               "candidate_artifact": str(out), "candidate_artifact_sha256": sha(out),
               "candidate_records": len(rows), "family_counts": {k: sum(r['family']==k for r in rows) for k in ('CR','BR')},
               "excluded_unparseable_pack_variant_bitrix_ids": sorted(EXCLUDED_UNPARSEABLE_VARIANTS),
               "facts_policy": "No facts, price, stock, availability, or cross-pack transfer are emitted.",
               "safe_to_apply": False, "automatic_database_mutations": 0}
    contract = out_dir / "rb-panasonic-wave200-preparation-contract.json"
    contract.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return summary

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--source", type=Path, required=True); p.add_argument("--out-dir", type=Path, required=True); p.add_argument("--expected", type=int, default=153)
    print(json.dumps(build(p.parse_args().source, p.parse_args().out_dir, p.parse_args().expected), ensure_ascii=False, indent=2))
