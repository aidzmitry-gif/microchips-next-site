#!/usr/bin/env python3
"""Build deterministic, non-public 1C staging waves.

The 1C code remains the sole identity in this step.  We intentionally do not
copy a possibly empty or warehouse-like supplier article into SKU/MPN and we
do not merge any legacy Bitrix record here.  That makes this input suitable
for staging review drafts only; later evidence may enrich a canonical product.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re


GROUP_TRUE = {"истина", "true", "1", "yes", "y"}
GROUP_FALSE = {"ложь", "false", "0", "no", "n"}
NON_PRODUCT_NAME = re.compile(r"(?:доставк|товарн\w*\s+накладн|книг\w*\s+замечан|\bбсо\b|услуг\w*)", re.IGNORECASE)


def clean(value: str | None) -> str:
    return (value or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--wave-size", type=int, default=500)
    args = parser.parse_args()
    if args.wave_size < 1:
        raise SystemExit("--wave-size must be positive")

    with args.source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        required = {"Код", "Наименование", "ЭтоГруппа"}
        if not required.issubset(reader.fieldnames or set()):
            raise SystemExit("1C export misses required headers: Код, Наименование, ЭтоГруппа")

        products: list[dict[str, str]] = []
        rejected: list[dict[str, str]] = []
        seen: set[str] = set()
        for row_number, row in enumerate(reader, start=2):
            flag = clean(row.get("ЭтоГруппа")).casefold()
            if flag in GROUP_TRUE:
                continue
            code = clean(row.get("Код"))
            name = clean(row.get("Наименование"))
            if flag not in GROUP_FALSE:
                rejected.append({"row_number": str(row_number), "external_id": code, "name": name, "reason": "unknown_group_flag"})
                continue
            if not code or not name:
                rejected.append({"row_number": str(row_number), "external_id": code, "name": name, "reason": "missing_external_id_or_name"})
                continue
            if NON_PRODUCT_NAME.search(name):
                rejected.append({"row_number": str(row_number), "external_id": code, "name": name, "reason": "suspected_non_product"})
                continue
            if len(name) > 255:
                rejected.append({"row_number": str(row_number), "external_id": code, "name": name, "reason": "name_exceeds_255_characters"})
                continue
            if code in seen:
                rejected.append({"row_number": str(row_number), "external_id": code, "name": name, "reason": "duplicate_external_id_in_source"})
                continue
            seen.add(code)
            products.append({
                "external_id": code,
                "name": name,
                # A stable internal draft slug avoids accidental URL collisions.
                "slug": "draft-" + hashlib.sha256(code.encode("utf-8")).hexdigest()[:16],
            })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for old in args.out_dir.glob("wave-*.csv"):
        old.unlink()
    for old in [args.out_dir / "manifest.json", args.out_dir / "rejected.csv"]:
        old.unlink(missing_ok=True)

    waves = []
    for index in range(0, len(products), args.wave_size):
        wave = products[index:index + args.wave_size]
        filename = f"wave-{index // args.wave_size + 1:03d}.csv"
        with (args.out_dir / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["external_id", "name", "slug"], delimiter=";")
            writer.writeheader()
            writer.writerows(wave)
        waves.append({"file": filename, "count": len(wave), "first_external_id": wave[0]["external_id"], "last_external_id": wave[-1]["external_id"]})

    with (args.out_dir / "rejected.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row_number", "external_id", "name", "reason"])
        writer.writeheader()
        writer.writerows(rejected)

    manifest = {
        "source": str(args.source),
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "identity_rule": "1C external_id only; never auto-merge with legacy Bitrix or infer SKU/MPN",
        "publication_rule": "staging drafts only; every SiteProduct stays unpublished",
        "source_product_rows": len(products) + len(rejected),
        "accepted_products": len(products),
        "rejected_products": len(rejected),
        "wave_size": args.wave_size,
        "waves": waves,
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"accepted_products": len(products), "rejected_products": len(rejected), "waves": len(waves)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
