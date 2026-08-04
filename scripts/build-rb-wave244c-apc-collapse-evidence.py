#!/usr/bin/env python3
"""Build a fail-closed APC duplicate-collapse partition and dry-run manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "docs/audits/generated/rb-wave244c-live-safety.json"
REGISTRY = ROOT / "docs/audits/sources/wave244c-apc/source-registry.json"
OLD_LEDGER = ROOT / "docs/audits/generated/rb-wave234b-apc-enersys-identity-ledger.csv"
OLD_EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave243a-prior-source-exclusions.json"
OLD_HOLDS = ROOT / "docs/imports/rb-apc-wave199-existing-identity-holds.csv"
EVIDENCE_DIR = ROOT / "docs/audits/evidence/wave244c-apc"
LEDGER = ROOT / "docs/audits/generated/rb-wave244c-apc-collapse-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave244c-apc-collapse.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-noindex-duplicate-collapse-wave244c-2026-07-30.json"

PINS = {
    LIVE: "e4223eb1eb31ac84f14f81dcf99f5d07d355d584fcc74a85ed1dc3847269687d",
    OLD_LEDGER: "75c3cfb0cdaaa514a7ef7bb9d7f9539abfc7d494f8d56d6ceb255f38ef39e61c",
    OLD_EXCLUSIONS: "a9a5aa9f109fddb0d320301f7007d829021ede9a60b508482d36c45fa2ef76ac",
    OLD_HOLDS: "73ac91d84f8401c7bb6a0225e82eaa7806a9e497a05547e9801d0a5702e430a1",
}
PAIRS = [
    ("bitrix:23799", "КА-00005164", "RBC23", "12V", "7Ah", "RBC7_RBC23_RBC31"),
    ("bitrix:23811", "КА-00003200", "RBC31", "48V", "9Ah", "RBC7_RBC23_RBC31"),
    ("bitrix:20088", "КА-00003292", "RBC7", "12V", "17Ah", "RBC7_RBC23_RBC31"),
    ("bitrix:23818", "КА-00003237", "APCRBC141", "72V", "5Ah", "APCRBC141"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bounded(name: str, token: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", name, re.I) is not None


def noindex_shape(row: dict) -> bool:
    return (
        row["published"] is True
        and len(row["urls"]) == 1 and row["urls"][0]["is_indexable"] is False
        and len(row["seo"]) >= 1
        and all(item["is_indexable"] is False and item["schema"] is None for item in row["seo"])
        and row["redirect_count"] == 0
        and bool(row["categories"])
    )


def survivor_safe(row: dict, currency: str) -> bool:
    if not noindex_shape(row):
        return False
    current = row["current_price_evidence"]
    if row["price"] is None:
        return not current
    return len(current) == 1 and current[0] == {"calculated_price": row["price"], "currency": currency}


def duplicate_safe(row: dict) -> bool:
    return (
        noindex_shape(row)
        and row["price"] is None and row["price_evidence_count"] == 0
        and row["family_canonical_count"] == 0 and row["family_variant_count"] == 0
        and row["verified_published_media_count"] == 0
    )


def main() -> None:
    for path, digest in PINS.items():
        if sha(path) != digest:
            raise SystemExit(f"pinned input drift: {path}")

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    rows = {row["external_id"]: row for row in live["rows"]}
    expected_ids = {value for pair in PAIRS for value in pair[:2]}
    if set(rows) != expected_ids or live["site"] != "microchips-by":
        raise SystemExit("Wave244C live scope drift")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = {row["label"]: row for row in registry["sources"]}
    if set(sources) != {"RBC7_RBC23_RBC31", "APCRBC141"}:
        raise SystemExit("Wave244C source registry drift")
    source_text: dict[str, str] = {}
    for label, source in sources.items():
        snapshot = ROOT / source["snapshot_path"]
        if sha(snapshot) != source["snapshot_sha256"] or source["final_url"] != source["requested_url"]:
            raise SystemExit(f"source snapshot drift: {label}")
        source_text[label] = "\n".join(page.extract_text() or "" for page in PdfReader(snapshot).pages)
    if any(token not in source_text["RBC7_RBC23_RBC31"] for token in ("Product End-of-Life Instructions", "Replacement Battery Cartridges", "RBC7", "RBC23", "RBC31")):
        raise SystemExit("RBC range source lacks exact official model assertions")
    if any(token not in source_text["APCRBC141"] for token in ("Smart-UPS", "APCRBC141", "APC")):
        raise SystemExit("APCRBC141 source lacks exact official model assertion")

    old_urls = set(re.findall(r"https://[^\"\s,]+", OLD_LEDGER.read_text(encoding="utf-8")))
    old_urls.update(re.findall(r"https://[^\"\s,]+", OLD_EXCLUSIONS.read_text(encoding="utf-8")))
    if any(source["final_url"] in old_urls for source in sources.values()):
        raise SystemExit("Wave244C repeated a prior source URL")

    evidence_by_model: dict[str, dict] = {}
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    for _, _, model, _, _, label in PAIRS:
        source = sources[label]
        evidence = {
            "schema_version": 1,
            "checked_at": "2026-07-30",
            "manufacturer": "APC by Schneider Electric",
            "model_core": model,
            "identity_assertion": "Official Schneider Electric documentation names this exact model in the APC Replacement Battery Cartridges range.",
            "source_url": source["final_url"],
            "source_snapshot_path": source["snapshot_path"],
            "source_snapshot_sha256": source["snapshot_sha256"],
            "no_repeat_prior_product_pages": True,
        }
        path = EVIDENCE_DIR / f"{model.lower()}-identity.json"
        write_json(path, evidence)
        evidence_by_model[model] = {"path": path, "sha256": sha(path), "source": source}

    output_rows, manifest_rows = [], []
    for duplicate_id, survivor_id, model, voltage, capacity, _ in PAIRS:
        duplicate, survivor = rows[duplicate_id], rows[survivor_id]
        failures = []
        if not bounded(duplicate["name"], model) or not bounded(survivor["name"], model):
            failures.append("bounded_model_name_mismatch")
        if survivor["manufacturer"] != "APC" or survivor["mpn"].upper() != model.upper():
            failures.append("survivor_identity_mismatch")
        if duplicate["availability"] != survivor["availability"]:
            failures.append("availability_mismatch")
        if not survivor_safe(survivor, live["currency"]):
            failures.append("survivor_safety_guard_failed")
        if not duplicate_safe(duplicate):
            failures.append("duplicate_safety_guard_failed")
        decision = "READY_DRY_RUN" if not failures else "HOLD_FAIL_CLOSED"
        reason = "all collapse guards satisfied" if not failures else ";".join(failures)
        evidence = evidence_by_model[model]
        output_rows.append({
            "duplicate_external_id": duplicate_id, "survivor_external_id": survivor_id, "model_core": model,
            "decision": decision, "reason": reason, "duplicate_price": duplicate["price"] or "",
            "duplicate_price_evidence_count": str(duplicate["price_evidence_count"]),
            "source_url": evidence["source"]["final_url"],
            "source_snapshot_sha256": evidence["source"]["snapshot_sha256"],
        })
        if failures:
            continue
        manifest_rows.append({
            "survivor_external_id": survivor_id, "duplicate_external_id": duplicate_id,
            "survivor_name": survivor["name"], "duplicate_name": duplicate["name"],
            "survivor_path": survivor["urls"][0]["path"], "duplicate_path": duplicate["urls"][0]["path"],
            "model_core": model, "voltage": voltage, "capacity": capacity,
            "availability": survivor["availability"], "category_external_ids": survivor["categories"],
            "duplicate_category_external_ids": duplicate["categories"],
            "manufacturer": "APC", "survivor_mpn": survivor["mpn"],
            "source_url": evidence["source"]["final_url"],
            "source_evidence_path": evidence["path"].relative_to(ROOT).as_posix(),
            "source_evidence_sha256": evidence["sha256"],
            "source_snapshot_path": evidence["source"]["snapshot_path"],
            "source_snapshot_sha256": evidence["source"]["snapshot_sha256"],
        })

    if [row["duplicate_external_id"] for row in manifest_rows] != ["bitrix:23799", "bitrix:20088"]:
        raise SystemExit("fail-closed partition drift")
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(output_rows)
    write_json(MANIFEST, {"schema_version": 1, "site_key": "microchips-by", "purpose": "Wave244C dry-run-only fail-closed APC duplicate collapse", "duplicates": manifest_rows})
    write_json(SUMMARY, {
        "schema_version": 1, "batch": "wave244c_apc_duplicate_collapse", "checked_at": "2026-07-30",
        "requested_pairs": 4, "ready_dry_run": len(manifest_rows), "held_fail_closed": 4 - len(manifest_rows),
        "holds": [{"duplicate_external_id": row["duplicate_external_id"], "reason": row["reason"]} for row in output_rows if row["decision"].startswith("HOLD")],
        "new_primary_sources": registry["sources"],
        "outputs": {"ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha(LEDGER)}, "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha(MANIFEST)}},
        "policy": {"apply": False, "database_changes": 0, "fail_closed": True, "prior_source_urls_reused": 0},
    })
    print(json.dumps({"requested": 4, "ready_dry_run": len(manifest_rows), "held_fail_closed": 4 - len(manifest_rows)}))


if __name__ == "__main__":
    main()
