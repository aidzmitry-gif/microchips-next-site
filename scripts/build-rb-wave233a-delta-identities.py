#!/usr/bin/env python3
"""Build the Wave233-A Delta-only OEM identity evidence packet.

This builder never downloads data and never connects to the application
database.  It consumes the approved gap export plus locally pinned Delta
evidence registries/snapshots.  Canonical collisions are a frozen read-only
database slice captured on 2026-07-29; any matching normalized MPN/SKU is a
hard HOLD.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKED_AT = "2026-07-29"
INPUT = Path("docs/audits/generated/rb-wave233-identity-media-gaps.csv")
LEDGER = Path("docs/audits/generated/rb-wave233a-delta-identity-ledger.csv")
SUMMARY = Path("docs/audits/generated/rb-wave233a-delta-identity-summary.json")
MANIFEST = Path("docs/imports/rb-delta-identity-stage-manifest-wave233a-2026-07-29.json")

# The rows below are the result of a read-only Products query on 2026-07-29.
# They intentionally include conflicts with a different manufacturer: the
# requested safety gate is normalized MPN/SKU equality, not a brand guess.
CANONICAL_CONFLICTS: dict[str, list[str]] = {
    "dt1240": ["ФР-00000946"], "dt1207": ["ФР-00000031"],
    "dt12032": ["ФР-00000147"], "dt612": ["ФР-00000233"],
    "dt1212": ["ФР-00000243"], "dtm1215": ["КА-00001967"],
    "dt401": ["ФР-00002172"], "dtm6012": ["КА-00005764"],
    "hrl12155w": ["КА-00005523"], "dt12100": ["ФР-00000106"],
    "dt12012": ["ФР-00000005"], "dt6028": ["КА-00001147"],
    "dtm12150l": ["ФР-00002021"], "dtm1233l": ["КА-00002816"],
    "cgd1208": ["КА-00003766"], "dt1233": ["КА-00002817"],
    "dtm1226": ["КА-00003468"], "cgd1233": ["КА-00003445"],
    "hr1224w": ["ФР-00001994"], "hr612": ["КА-00001895"],
    "ft12125m": ["КА-00002317"], "hrl12260w": ["КА-00005338"],
    "fts12100x": ["КА-00006757"], "hr1228w": ["bitrix:1624"],
    "hr1234w": ["bitrix:1635"], "hrl12420w": ["bitrix:1636"],
}

REGISTRIES = (
    ("wave198", Path("docs/audits/generated/rb-delta-wave198-official-evidence.csv"), "external_id", "model", "source_snapshot_path", "source_sha256"),
    ("wave206", Path("docs/audits/generated/rb-delta-wave206-official-evidence.csv"), "product_external_id", "legacy_model", "snapshot_path", "snapshot_sha256"),
    ("wave206-new", Path("docs/audits/generated/rb-delta-wave206-new-official-evidence.csv"), "external_id", "model", "source_snapshot_path", "source_sha256"),
    ("wave211b", Path("docs/audits/generated/wave211b-delta-primary-evidence.csv"), "external_id", "model", "source_snapshot_path", "source_sha256"),
)


def normalized(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def exact_mpn(name: str) -> str:
    match = re.fullmatch(r"Аккумулятор Delta\s+(.+?)\s+\(AGM,.*", name)
    if match is None:
        raise ValueError(f"unsupported Delta title: {name!r}")
    return match.group(1)


def resolve_snapshot(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def manifest_snapshot_path(path: Path) -> str:
    return Path("../audits") .joinpath(path.relative_to(ROOT / "docs/audits")).as_posix()


def local_evidence(root: Path) -> dict[str, list[dict[str, str]]]:
    candidates: dict[str, list[dict[str, str]]] = defaultdict(list)
    for registry_name, registry_path, id_key, model_key, path_key, hash_key in REGISTRIES:
        with (root / registry_path).open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                external_id = (row.get(id_key) or "").strip()
                declared_model = (row.get(model_key) or "").strip()
                source_url = (row.get("source_url") or "").strip()
                snapshot_value = (row.get(path_key) or "").strip()
                declared_hash = (row.get(hash_key) or "").strip().lower()
                if not all((external_id, declared_model, source_url, snapshot_value, declared_hash)):
                    continue
                if not source_url.startswith("https://delta-batt.com/"):
                    continue
                snapshot = resolve_snapshot(root, snapshot_value)
                if not snapshot.is_file() or hashlib.sha256(snapshot.read_bytes()).hexdigest() != declared_hash:
                    continue
                source_text = normalized(snapshot.read_text(encoding="utf-8", errors="replace"))
                model_key_normalized = normalized(declared_model)
                if model_key_normalized not in source_text:
                    continue
                candidates[external_id].append({
                    "registry": registry_name,
                    "declared_model": declared_model,
                    "source_url": source_url,
                    "source_snapshot_path": manifest_snapshot_path(snapshot),
                    "source_snapshot_sha256": declared_hash,
                    "source_publisher": (row.get("publisher") or row.get("source_publisher") or "DELTA Battery / ENERGON").strip(),
                })
    return candidates


def select_evidence(entries: list[dict[str, str]], mpn: str) -> dict[str, str] | None:
    wanted = normalized(mpn)
    exact = [entry for entry in entries if normalized(entry["declared_model"]) == wanted]
    return sorted(exact, key=lambda entry: (entry["registry"], entry["source_url"]))[0] if exact else None


def build(root: Path, output_root: Path) -> tuple[list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    with (root / INPUT).open(encoding="utf-8-sig", newline="") as handle:
        targets = [
            row for row in csv.DictReader(handle)
            if row["category_external_id"] == "seo:batteries-ups"
            and not row["manufacturer"].strip()
            and row["name"].startswith("Аккумулятор Delta")
        ]
    if len(targets) != 152 or len({row["external_id"] for row in targets}) != 152:
        raise ValueError("Wave233-A scope must contain exactly 152 unique Delta blank-manufacturer products")

    evidence_by_id = local_evidence(root)
    ledger: list[dict[str, str]] = []
    manifest_products: list[dict[str, str]] = []
    for row in sorted(targets, key=lambda item: item["external_id"]):
        mpn = exact_mpn(row["name"])
        mpn_normalized = normalized(mpn)
        evidence = select_evidence(evidence_by_id.get(row["external_id"], []), mpn)
        conflicts = CANONICAL_CONFLICTS.get(mpn_normalized, [])
        reasons: list[str] = []
        if evidence is None:
            reasons.append("NO_LOCAL_OFFICIAL_EXACT_MPN_EVIDENCE")
        if conflicts:
            reasons.append("CANONICAL_MPN_OR_SKU_CONFLICT")
        decision = "PASS" if not reasons else "HOLD"
        entry = {
            "external_id": row["external_id"], "current_name": row["name"],
            "manufacturer": "Delta", "mpn": mpn, "mpn_normalized": mpn_normalized,
            "source_registry": evidence["registry"] if evidence else "",
            "source_url": evidence["source_url"] if evidence else "",
            "source_snapshot_path": evidence["source_snapshot_path"] if evidence else "",
            "source_snapshot_sha256": evidence["source_snapshot_sha256"] if evidence else "",
            "canonical_conflict_external_ids": "|".join(conflicts),
            "decision": decision, "hold_reason": "|".join(reasons),
        }
        ledger.append(entry)
        if decision == "PASS":
            manifest_products.append({
                "external_id": row["external_id"], "current_name": row["name"],
                "manufacturer": "Delta", "mpn": mpn,
                "source_url": evidence["source_url"],
                "source_kind": "official_manufacturer_product_page",
                "source_publisher": evidence["source_publisher"], "checked_at": CHECKED_AT,
                "product_type": "stationary sealed rechargeable battery",
                "source_snapshot_path": evidence["source_snapshot_path"],
                "source_snapshot_sha256": evidence["source_snapshot_sha256"],
            })
    if len({entry["mpn_normalized"] for entry in ledger}) != 152:
        raise ValueError("scope unexpectedly repeats a normalized MPN")

    summary = {
        "schema_version": 1, "wave": "233-A", "checked_at": CHECKED_AT,
        "scope": "seo:batteries-ups blank-manufacturer titles starting Аккумулятор Delta",
        "input_records": len(ledger), "pass_records": len(manifest_products),
        "hold_records": len(ledger) - len(manifest_products),
        "hold_reasons": dict(sorted(Counter(reason for entry in ledger for reason in entry["hold_reason"].split("|") if reason).items())),
        "canonical_collision_slice": "read-only Products MPN/SKU query captured 2026-07-29",
        "network_downloads": 0, "media_promotions": 0, "price_or_stock_changes": 0,
    }
    manifest = {"schema_version": 1, "site_key": "microchips-by", "products": manifest_products}
    return ledger, summary, manifest


def write_outputs(ledger: list[dict[str, str]], summary: dict[str, Any], manifest: dict[str, Any], output_root: Path) -> None:
    ledger_path, summary_path, manifest_path = output_root / LEDGER, output_root / SUMMARY, output_root / MANIFEST
    for path in (ledger_path, summary_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]))
        writer.writeheader(); writer.writerows(ledger)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    args = parser.parse_args()
    ledger, summary, manifest = build(args.root.resolve(), args.output_root.resolve())
    write_outputs(ledger, summary, manifest, args.output_root.resolve())
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
