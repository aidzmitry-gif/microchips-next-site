#!/usr/bin/env python3
"""Build the no-repeat Wave243C description/duplicate evidence partition."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
QUEUE = GEN / "rb-enrichment-queue-wave242.csv"
WAVE242 = GEN / "rb-wave242-leoch-marathon-csb-identity-ledger.csv"
WAVE234B = GEN / "rb-wave234b-apc-enersys-identity-ledger.csv"
APC_HOLDS = ROOT / "docs/imports/rb-apc-wave199-existing-identity-holds.csv"
SOURCE_REGISTRY = ROOT / "docs/audits/sources/wave243c-apc/source-registry.json"
LEDGER = GEN / "rb-wave243c-remaining-description-ledger.csv"
SUMMARY = GEN / "rb-wave243c-remaining-description.summary.json"
DUPLICATES = GEN / "rb-wave243c-exact-legacy-duplicates.csv"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave243c-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave243c-2026-07-29.json"

PINS = {
    QUEUE: "8d7f4435b25327d3f6a3b9015d0b535cf64f3aad1342378fc165abc4be1e7867",
    WAVE242: "448cbd79a161abff3e30f6927433ddd9e1e655ec37f942b781177ec8d65794e0",
    WAVE234B: "75c3cfb0cdaaa514a7ef7bb9d7f9539abfc7d494f8d56d6ceb255f38ef39e61c",
    APC_HOLDS: "73ac91d84f8401c7bb6a0225e82eaa7806a9e497a05547e9801d0a5702e430a1",
}
EXPECTED = {"Leoch": 50, "APC": 22, "CSB": 16, "Marathon": 8, "EnerSys": 12}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def brand(name: str) -> str | None:
    for value in EXPECTED:
        if re.search(rf"(?<![A-Za-z]){re.escape(value)}(?![A-Za-z])", name, re.I):
            return value
    return None


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    for path, digest in PINS.items():
        if sha(path) != digest:
            raise SystemExit(f"pinned input drift: {path}")

    queue = [row for row in rows(QUEUE) if row["has_applied_description"] == "false" and brand(row["name"])]
    counts = Counter(brand(row["name"]) for row in queue)
    if dict(counts) != EXPECTED or len(queue) != 108:
        raise SystemExit(f"Wave243C scope drift: {dict(counts)} / {len(queue)}")

    old242 = {row["external_id"]: row for row in rows(WAVE242)}
    old234 = {row["product_external_id"]: row for row in rows(WAVE234B)}
    target_ids = {row["product_external_id"] for row in queue}
    duplicate_rows = {row["external_id"]: row for row in rows(APC_HOLDS) if row["external_id"] in target_ids and "already belongs to canonical product" in row["reason"]}
    expected_duplicates = {"bitrix:20088", "bitrix:23799", "bitrix:23811", "bitrix:23818"}
    if set(duplicate_rows) != expected_duplicates:
        raise SystemExit("exact APC legacy duplicate baseline drift")

    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    source = registry["sources"][0]
    snapshot = ROOT / source["snapshot_path"]
    if source["model"] != "APCRBC109" or sha(snapshot) != source["snapshot_sha256"]:
        raise SystemExit("new APC source registry/snapshot drift")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(snapshot).pages)
    required = ["APCRBC109", "APC Replacement Battery Cartridge #109", "Battery Volt-Amp-Hour Capacity 9", "Battery blocks per string 2"]
    if any(token not in text for token in required):
        raise SystemExit("APCRBC109 snapshot lacks an exact required assertion")

    ledger: list[dict[str, str]] = []
    duplicates: list[dict[str, str]] = []
    identities: list[dict[str, object]] = []
    descriptions: list[dict[str, object]] = []
    for item in queue:
        external_id, name = item["product_external_id"], item["name"]
        maker = brand(name)
        previous = old242.get(external_id) or old234.get(external_id)
        if previous is None:
            raise SystemExit(f"target absent from prior no-repeat ledgers: {external_id}")
        model = previous.get("mpn_candidate") or previous.get("model_token") or ""
        decision, partition, reason = "HOLD", "hold_no_new_exact_primary_evidence", "No new SHA-pinned manufacturer-primary source proves this exact offered identity and description."
        source_url = snapshot_path = snapshot_sha = ""

        if external_id in duplicate_rows:
            decision, partition, reason = "HOLD", "hold_exact_legacy_duplicate", duplicate_rows[external_id]["reason"]
            survivor = re.search(r"canonical product ([^;]+)", reason).group(1)
            duplicates.append({"legacy_external_id": external_id, "model_token": model, "canonical_survivor_external_id": survivor, "decision": "HOLD_NO_APPLY", "reason": reason})
        elif external_id == "bitrix:23844":
            if maker != "APC" or model != "RBC109" or "9Ah" not in name:
                raise SystemExit("APCRBC109 target identity drift")
            decision, partition, reason = "PASS", "pass_new_exact_primary_apcrbc109", ""
            source_url, snapshot_path, snapshot_sha = source["final_url"], source["snapshot_path"], source["snapshot_sha256"]
            identities.append({
                "external_id": external_id, "current_name": name, "manufacturer": "APC", "mpn": "RBC109",
                "source_url": source_url, "source_kind": "official_manufacturer_catalogue", "source_publisher": "Schneider Electric",
                "checked_at": "2026-07-29", "product_type": "replacement battery cartridge",
                "source_snapshot_path": "../audits/sources/wave243c-apc/apcrbc109.pdf", "source_snapshot_sha256": snapshot_sha,
            })
            descriptions.append({
                "external_id": external_id, "identity_scope": "exact", "manufacturer": "APC", "mpn": "RBC109",
                # Keep the verified catalogue identity bounded and end the
                # display name with the canonical MPN required by Laravel.
                "display_name": "Сменный аккумуляторный картридж APC RBC109",
                "technology": "герметичная необслуживаемая свинцово-кислотная батарея с иммобилизованным электролитом",
                "source_url": source_url, "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary",
                "source_publisher": "Schneider Electric", "manufacturer_primary": True, "evidence_scope": "exact_model", "checked_at": "2026-07-29",
                "technical_attributes": {"Тип изделия": "сменный аккумуляторный картридж", "Количество аккумуляторных блоков в цепочке": "2", "Параметр Battery Volt-Amp-Hour Capacity": "9"},
            })
        elif external_id in old242:
            partition = old242[external_id]["partition"]
            reason = "No-repeat carry-forward: " + old242[external_id]["hold_reason"]
        else:
            partition = "hold_prior_" + old234[external_id]["partition"]
            reason = "No-repeat carry-forward: " + old234[external_id]["conflict_reason"]

        ledger.append({
            "external_id": external_id, "name": name, "manufacturer_candidate": maker or "", "model_token": model,
            "decision": decision, "partition": partition, "duplicate_survivor": duplicates[-1]["canonical_survivor_external_id"] if external_id in duplicate_rows else "",
            "source_url": source_url, "source_snapshot_path": snapshot_path, "source_snapshot_sha256": snapshot_sha,
            "reason": reason, "safe_to_stage": "true" if decision == "PASS" else "false",
        })

    if len(ledger) != 108 or len(duplicates) != 4 or len(identities) != 1 or len(descriptions) != 1:
        raise SystemExit("Wave243C output cardinality failure")
    for path, data in ((LEDGER, ledger), (DUPLICATES, duplicates)):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]), lineterminator="\n")
            writer.writeheader(); writer.writerows(data)
    write_json(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "purpose": "Wave243C one new exact APC identity", "products": identities})
    write_json(DESCRIPTIONS, {"schema_version": 1, "purpose": "Wave243C one new exact APC source-backed description", "locale": "ru-BY", "products": descriptions})
    summary = {
        "schema_version": 1, "batch": "wave243c_remaining_descriptions", "checked_at": "2026-07-29",
        "scope": {"rows": len(ledger), "manufacturer_counts": dict(counts)},
        "decision_counts": dict(Counter(row["decision"] for row in ledger)), "partition_counts": dict(sorted(Counter(row["partition"] for row in ledger).items())),
        "legacy_duplicate_count": len(duplicates), "pass_rows": len(descriptions), "hold_rows": len(ledger) - len(descriptions),
        "new_sources": registry["sources"],
        "no_repeat_baselines": [{"path": path.relative_to(ROOT).as_posix(), "sha256": digest} for path, digest in PINS.items()],
        "outputs": {"ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha(LEDGER)}, "duplicates": {"path": DUPLICATES.relative_to(ROOT).as_posix(), "sha256": sha(DUPLICATES)}, "identities": {"path": IDENTITIES.relative_to(ROOT).as_posix(), "sha256": sha(IDENTITIES)}, "descriptions": {"path": DESCRIPTIONS.relative_to(ROOT).as_posix(), "sha256": sha(DESCRIPTIONS)}},
        "policy": {"exact_identity_and_description_only": True, "database_apply": False, "publication_changes": 0, "commercial_changes": 0},
    }
    write_json(SUMMARY, summary)
    print(json.dumps({"rows": len(ledger), "pass": 1, "hold": 107, "exact_legacy_duplicates": 4}))


if __name__ == "__main__":
    main()
