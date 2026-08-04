#!/usr/bin/env python3
"""Build the offline Wave243B FIAMM/Panasonic duplicate gate and manifests."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave242.csv"
SOURCE_DIR = ROOT / "docs/audits/sources/wave243b-fiamm-panasonic"
CANONICAL = SOURCE_DIR / "canonical-products-snapshot.csv"
ACQUISITION = SOURCE_DIR / "acquisition.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave243b-fiamm-panasonic-description-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave243b-fiamm-panasonic-description.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave243b-fiamm-panasonic-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave243b-fiamm-panasonic-2026-07-29.json"

CHECKED_AT = "2026-07-29"
PINS = {
    QUEUE: "8d7f4435b25327d3f6a3b9015d0b535cf64f3aad1342378fc165abc4be1e7867",
    CANONICAL: "cd60393c567d6ee20d13a4540c38bffb0d584769e6bf9ee6713930e47c146662",
    ACQUISITION: "8776efb14a126b7c6a8202e8aa9a69a49b26ea18897ee23b4eb857a5de7700f3",
}

EXACT_EVIDENCE = {
    "FG27004": ("fiamm-fg27004.pdf", "exact_individual_datasheet", {"voltage": "12 В", "capacity": "70 А·ч", "series": "FG"}),
    "FG2A007": ("fiamm-fg2a007.pdf", "exact_individual_datasheet", {"voltage": "12 В", "capacity": "100 А·ч", "series": "FG"}),
    "LC-P0612P": ("panasonic-lc-p0612p.pdf", "exact_individual_datasheet", {"voltage": "6 В", "capacity": "12 А·ч", "series": "LC-P"}),
    "LC-R0612P": ("panasonic-lc-r0612p.pdf", "exact_individual_datasheet", {"voltage": "6 В", "capacity": "12 А·ч", "series": "LC-R"}),
    "LC-R0612P1": ("panasonic-lc-r0612p.pdf", "exact_datasheet_membership", {"voltage": "6 В", "capacity": "12 А·ч", "series": "LC-R"}),
    "LC-R063R4P": ("panasonic-lc-r063r4p.pdf", "exact_individual_datasheet", {"voltage": "6 В", "capacity": "3,4 А·ч", "series": "LC-R"}),
    "LC-R067R2P": ("panasonic-lc-r067r2p.pdf", "exact_individual_datasheet", {"voltage": "6 В", "capacity": "7,2 А·ч", "series": "LC-R"}),
    "LC-R067R2P1": ("panasonic-lc-r067r2p.pdf", "exact_datasheet_membership", {"voltage": "6 В", "capacity": "7,2 А·ч", "series": "LC-R"}),
}

CATALOGUE_MEMBERS = {
    "LC-R122R2PG": "LC-R122R2PG",
    "LC-R123R4PG": "LC-R123R4PG",
    "LC-R127R2PG": "LC-R127R2PG/PG1",
    "LC-RA1212PG": "LC-RA1212PG/PG1",
    "LC-RA1212PG1": "LC-RA1212PG/PG1",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_model(row: dict[str, str]) -> tuple[str, str]:
    name = row["name"]
    for label, manufacturer in (("Fiamm ", "Fiamm"), ("Panasonic ", "Panasonic")):
        if label in name:
            return manufacturer, name.split(label, 1)[1].split(" (", 1)[0].strip()
    raise RuntimeError(f"Cannot extract Wave243B model from {name!r}")


def load_pdf_texts(inventory: list[dict[str, object]]) -> dict[str, str]:
    result = {}
    for source in inventory:
        path = ROOT / str(source["path"])
        if sha256(path) != source["sha256"]:
            raise RuntimeError(f"Source SHA mismatch: {path}")
        with pdfplumber.open(path) as document:
            result[path.name] = "\n".join(page.extract_text() or "" for page in document.pages)
    return result


def assert_no_repeat(inventory: list[dict[str, object]]) -> None:
    current = {str(row["sha256"]) for row in inventory}
    prior = {}
    for path in (ROOT / "docs/audits/sources").rglob("*.pdf"):
        if SOURCE_DIR in path.parents:
            continue
        prior.setdefault(sha256(path), []).append(path)
    repeated = current & set(prior)
    if repeated:
        raise RuntimeError(f"Wave243B source SHA already used: {[(value, prior[value]) for value in repeated]}")


def assert_no_repeat_urls(inventory: list[dict[str, object]]) -> None:
    urls = {str(row["source_url"]) for row in inventory}
    collisions: dict[str, list[str]] = {}
    for base in (ROOT / "docs/audits", ROOT / "docs/imports"):
        for path in base.rglob("*"):
            if not path.is_file() or "wave243b" in path.as_posix().lower():
                continue
            if path.suffix.lower() not in {".json", ".csv", ".md", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for url in urls:
                if url in text:
                    collisions.setdefault(url, []).append(path.relative_to(ROOT).as_posix())
    if collisions:
        raise RuntimeError(f"Wave243B source URL already used: {collisions}")


def exact_hits(text: str, model: str) -> int:
    return len(re.findall(rf"(?<![A-Z0-9]){re.escape(model)}(?![A-Z0-9])", text.upper()))


def main() -> int:
    for path, expected in PINS.items():
        if sha256(path) != expected:
            raise RuntimeError(f"Input SHA mismatch for {path}")

    inventory = json.loads(ACQUISITION.read_text(encoding="utf-8"))
    sources = {Path(str(row["path"])).name: row for row in inventory}
    assert len(sources) == 7
    assert len({str(row["source_url"]) for row in inventory}) == 7
    assert all("fiamm.co/" in str(row["source_url"]) or "industrial.panasonic.com/" in str(row["source_url"]) for row in inventory)
    assert_no_repeat(inventory)
    assert_no_repeat_urls(inventory)
    pdf_texts = load_pdf_texts(inventory)

    with QUEUE.open(encoding="utf-8-sig", newline="") as stream:
        queue = [
            row for row in csv.DictReader(stream)
            if row["has_applied_description"] == "false"
            and ("fiamm" in row["name"].lower() or "panasonic" in row["name"].lower())
        ]
    if len(queue) != 88:
        raise RuntimeError(f"Frozen Wave243B scope changed: {len(queue)} != 88")
    if Counter(extract_model(row)[0] for row in queue) != {"Fiamm": 56, "Panasonic": 32}:
        raise RuntimeError("Frozen Wave243B manufacturer partition changed")
    if any(row["identity_fields_present"] != "0" for row in queue):
        raise RuntimeError("Wave243B expects blank Bitrix identity fields")

    with CANONICAL.open(encoding="utf-8-sig", newline="") as stream:
        canonical = list(csv.DictReader(stream))

    identities = []
    descriptions = []
    ledger = []
    for row in queue:
        manufacturer, model = extract_model(row)
        model_norm = normalize(model)
        duplicates = [
            candidate for candidate in canonical
            if normalize(candidate["mpn"]) == model_norm
            or (not candidate["mpn"] and normalize(candidate["name"]).endswith(model_norm))
        ]
        evidence = EXACT_EVIDENCE.get(model)
        if evidence is None and model in CATALOGUE_MEMBERS:
            evidence = (
                "panasonic-vrla-recognized-models.pdf",
                "exact_catalogue_membership",
                {"series": "LC-RA" if model.startswith("LC-RA") else "LC-R"},
            )

        decision = "HOLD"
        partition = "hold_no_new_exact_manufacturer_primary_evidence"
        source = None
        membership_hits = 0
        facts: dict[str, str] = {}
        evidence_kind = ""
        if duplicates:
            partition = "hold_legacy_canonical_duplicate"
        elif evidence is not None:
            filename, evidence_kind, facts = evidence
            source = sources[filename]
            text = pdf_texts[filename]
            membership_hits = exact_hits(text, model)
            if evidence_kind == "exact_catalogue_membership":
                membership_hits = text.upper().count(CATALOGUE_MEMBERS[model])
            if membership_hits < 1:
                raise RuntimeError(f"Exact membership missing for {model} in {filename}")
            decision = "PASS"
            partition = evidence_kind

        duplicate_ids = "|".join(item["external_id"] for item in duplicates)
        ledger.append(
            {
                "external_id": row["product_external_id"],
                "manufacturer_candidate": manufacturer,
                "mpn_candidate": model,
                "normalized_mpn": model_norm,
                "decision": decision,
                "partition": partition,
                "legacy_duplicate_external_ids": duplicate_ids,
                "source_url": "" if source is None else str(source["source_url"]),
                "source_snapshot_path": "" if source is None else str(source["path"]),
                "source_snapshot_sha256": "" if source is None else str(source["sha256"]),
                "evidence_kind": evidence_kind,
                "exact_membership_hits": str(membership_hits),
            }
        )
        if decision != "PASS":
            continue

        snapshot_path = "../audits/" + str(source["path"]).split("docs/audits/", 1)[1]
        identity = {
            "external_id": row["product_external_id"],
            "current_name": row["name"],
            "manufacturer": manufacturer,
            "mpn": model,
            "source_url": source["source_url"],
            "source_kind": "official_manufacturer_catalogue",
            "source_publisher": "FIAMM Energy Technology S.p.A." if manufacturer == "Fiamm" else "Panasonic Corporation",
            "checked_at": CHECKED_AT,
            "product_type": "stationary VRLA AGM battery",
            "source_snapshot_path": snapshot_path,
            "source_snapshot_sha256": source["sha256"],
        }
        identities.append(identity)

        attributes = {"Технология": "VRLA AGM", "Серия": facts["series"]}
        if "voltage" in facts:
            attributes["Номинальное напряжение"] = facts["voltage"]
            attributes["Номинальная ёмкость (20 ч)"] = facts["capacity"]
        descriptions.append(
            {
                "external_id": row["product_external_id"],
                "identity_scope": "exact",
                "manufacturer": manufacturer,
                "mpn": model,
                # The exact-identity contract requires the refreshed display
                # name to end with the proven MPN. Technology remains in the
                # structured attributes instead of being appended here.
                "display_name": f"Аккумулятор {manufacturer} {model}",
                "technology": "VRLA AGM",
                "source_url": source["source_url"],
                "technical_attributes": attributes,
                "source_kind": "official_manufacturer_catalogue",
                "source_tier": "manufacturer_primary",
                "source_publisher": identity["source_publisher"],
                "manufacturer_primary": True,
                "evidence_scope": "exact_model",
                "checked_at": CHECKED_AT,
            }
        )

    decision_counts = Counter(row["decision"] for row in ledger)
    partition_counts = Counter(row["partition"] for row in ledger)
    if decision_counts != {"HOLD": 75, "PASS": 13}:
        raise RuntimeError(f"Unexpected Wave243B decisions: {decision_counts}")
    if partition_counts["hold_legacy_canonical_duplicate"] != 4:
        raise RuntimeError(f"Unexpected legacy duplicate count: {partition_counts}")

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ledger[0]))
        writer.writeheader()
        writer.writerows(ledger)
    write_json(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "purpose": "Wave243B strict FIAMM/Panasonic identities after legacy duplicate gate", "products": identities})
    write_json(DESCRIPTIONS, {"schema_version": 1, "purpose": "Wave243B exact FIAMM/Panasonic manufacturer-primary descriptions", "locale": "ru-BY", "products": descriptions})
    write_json(
        SUMMARY,
        {
            "schema_version": 1,
            "wave": "wave243b-fiamm-panasonic-descriptions",
            "checked_at": CHECKED_AT,
            "frozen_scope_count": 88,
            "manufacturer_counts": {"Fiamm": 56, "Panasonic": 32},
            "decision_counts": dict(sorted(decision_counts.items())),
            "partition_counts": dict(sorted(partition_counts.items())),
            "identity_manifest": {"path": IDENTITIES.relative_to(ROOT).as_posix(), "sha256": sha256(IDENTITIES)},
            "description_manifest": {"path": DESCRIPTIONS.relative_to(ROOT).as_posix(), "sha256": sha256(DESCRIPTIONS)},
            "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER)},
            "source_inventory": inventory,
            "source_policy": {"new_urls": 7, "new_sha256": 7, "prior_snapshot_hash_collisions": 0, "manufacturer_primary_only": True},
            "policy": {"database_calls": 0, "network_calls": 0, "database_mutations": 0, "legacy_duplicate_gate_precedes_evidence_gate": True},
        },
    )
    print(f"Built Wave243B: PASS={decision_counts['PASS']}, HOLD={decision_counts['HOLD']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
