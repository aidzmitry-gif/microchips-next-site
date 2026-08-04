#!/usr/bin/env python3
"""Build exact General Security identities from a pinned official catalogue snapshot."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "docs/audits/generated/rb-wave234-c-remaining-ups-batteries.csv"
SNAPSHOT = ROOT / "docs/audits/sources/wave234c/general-security-product.html"
LEDGER = ROOT / "docs/audits/generated/rb-wave234c-general-security-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234c-general-security-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave234c-general-security-2026-07-29.json"
SOURCE_URL = "https://general-security.ru/product"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_model(value: str) -> str:
    return re.sub(r"[\s-]+", "", value.upper())


def parse_model(name: str) -> tuple[str, str]:
    match = re.search(r"\b(GSL|GS)\s*([0-9]+(?:\.[0-9]+)?-[0-9]+)(?:\s+(F[12]))?\b", name, re.I)
    if not match:
        raise SystemExit(f"Cannot parse General Security model: {name}")
    base = f"{match.group(1).upper()} {match.group(2)}"
    return base + (f" {match.group(3).upper()}" if match.group(3) else ""), match.group(3) or ""


def main() -> None:
    if not LANE.is_file() or not SNAPSHOT.is_file():
        raise SystemExit("Wave234-C lane or General Security snapshot is missing")
    with LANE.open(encoding="utf-8-sig", newline="") as handle:
        lane = [row for row in csv.DictReader(handle) if "General Security" in row["name"]]
    if len(lane) != 37 or len({row["external_id"] for row in lane}) != 37:
        raise SystemExit(f"General Security lane drift: rows={len(lane)}")

    soup = BeautifulSoup(SNAPSHOT.read_text(encoding="utf-8"), "html.parser")
    official_models = {compact_model(h.get_text(" ", strip=True)): h.get_text(" ", strip=True) for h in soup.select("h2")}
    if len(official_models) < 80:
        raise SystemExit(f"Official catalogue parse drift: models={len(official_models)}")

    ledger = []
    products = []
    snapshot_hash = sha256(SNAPSHOT)
    for row in lane:
        model, terminal_suffix = parse_model(row["name"])
        official = official_models.get(compact_model(model))
        exact = bool(official) and not terminal_suffix
        partition = "exact_safe" if exact else ("hold_terminal_suffix_not_in_official_model" if terminal_suffix else "hold_model_absent")
        reason = "" if exact else (
            "The legacy identity includes a terminal suffix not present in the official catalogue model heading."
            if terminal_suffix else "The exact offered model is absent from the pinned official catalogue."
        )
        ledger.append({
            "external_id": row["external_id"], "name": row["name"], "manufacturer": "General Security",
            "mpn_candidate": model, "official_heading": official or "", "partition": partition,
            "source_url": SOURCE_URL, "source_snapshot_path": SNAPSHOT.relative_to(ROOT).as_posix(),
            "source_snapshot_sha256": snapshot_hash, "hold_reason": reason,
            "safe_to_apply": "true" if exact else "false", "media_id": row["media_id"],
            "content_sha256": row["content_sha256"],
        })
        if exact:
            products.append({
                "external_id": row["external_id"], "current_name": row["name"],
                "manufacturer": "General Security", "mpn": model,
                "source_url": SOURCE_URL, "source_kind": "official_manufacturer_catalogue",
                "source_publisher": "General Security", "checked_at": "2026-07-29",
                "product_type": "stationary sealed rechargeable battery",
                "source_snapshot_path": "../audits/sources/wave234c/general-security-product.html",
                "source_snapshot_sha256": snapshot_hash,
            })

    # Laravel's canonical ProductIdentity normalizer removes punctuation. It
    # maps GSL 1.2-12 and GSL 12-12 to the same `gsl1212` key. Do not choose a
    # survivor arbitrarily: both remain HOLD until a catalogue-wide identity
    # normalization migration can be performed safely.
    normalized_groups: dict[str, list[str]] = {}
    for row in ledger:
        if row["safe_to_apply"] != "true":
            continue
        key = re.sub(r"[^\w]+", "", row["mpn_candidate"].lower(), flags=re.UNICODE)
        normalized_groups.setdefault(key, []).append(row["external_id"])
    collision_ids = {
        external_id
        for external_ids in normalized_groups.values()
        if len(external_ids) > 1
        for external_id in external_ids
    }
    for row in ledger:
        if row["external_id"] in collision_ids:
            row["partition"] = "hold_normalized_mpn_collision"
            row["hold_reason"] = "Distinct official models collide under the current catalogue MPN normalizer; neither may be selected arbitrarily."
            row["safe_to_apply"] = "false"
    products = [row for row in products if row["external_id"] not in collision_ids]

    fields = list(ledger[0])
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    manifest = {
        "schema_version": 1, "site_key": "microchips-by", "review_batch": "wave234c_general_security",
        "checked_at": "2026-07-29", "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partitions = Counter(row["partition"] for row in ledger)
    summary = {
        "schema_version": 1, "batch": "wave234c_general_security", "checked_at": "2026-07-29",
        "input": {"path": LANE.relative_to(ROOT).as_posix(), "sha256": sha256(LANE), "rows": len(lane)},
        "source": {"url": SOURCE_URL, "path": SNAPSHOT.relative_to(ROOT).as_posix(), "sha256": snapshot_hash,
                   "parsed_model_headings": len(official_models)},
        "partition_counts": dict(sorted(partitions.items())), "exact_primary_pass_rows": len(products),
        "normalized_mpn_collision_external_ids": sorted(collision_ids),
        "output": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(products)},
        "policy": {"terminal_suffix_requires_exact_source": True, "database_mutations": 0,
                   "media_mutations": 0, "commercial_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "pass_rows": len(products), "partitions": dict(sorted(partitions.items()))}))


if __name__ == "__main__":
    main()
