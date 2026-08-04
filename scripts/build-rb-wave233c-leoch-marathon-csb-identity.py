#!/usr/bin/env python3
"""Build the fail-closed Wave233-C identity review for Leoch, Marathon and CSB.

This is intentionally an identity-only review.  A manufacturer/model parsed
from the legacy title is a candidate, never proof.  A row may be promoted only
when an already-saved, SHA-pinned first-party source contains that *exact*
model (including construction/terminal suffixes) and has no normalized
manufacturer+MPN or SKU collision.  The currently saved sources do not meet
that bar for any of the 131 in-scope records, so the apply manifest is
deliberately empty.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-wave233-identity-media-gaps.csv"
WAVE206 = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv"
WAVE145 = ROOT / "docs/imports/rb-bitrix-identity-review-decisions-wave145-2026-07-28.json"
CSB_PDF = ROOT / "docs/audits/sources/wave206-fiamm-bb-csb/csb-hrl12390w-ra240531.pdf"
CSB_REGISTRIES = [
    ROOT / "docs/imports/rb-manufacturer-series-csb-wave176-source.json",
    ROOT / "docs/imports/rb-manufacturer-series-csb-wave177-source.json",
    ROOT / "docs/imports/rb-manufacturer-series-csb-wave178-source.json",
    ROOT / "docs/imports/rb-manufacturer-series-csb-wave180-source.json",
    ROOT / "docs/imports/rb-manufacturer-series-csb-wave185-source.json",
]
LEOCH_REGISTRIES = [
    ROOT / "docs/imports/rb-manufacturer-series-leoch-wave188-source.json",
    ROOT / "docs/imports/rb-manufacturer-series-leoch-lpf-wave190-source.json",
    ROOT / "docs/imports/rb-manufacturer-series-leoch-lpl2-wave192-source.json",
]
OUTPUT = ROOT / "docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave233c-leoch-marathon-csb-2026-07-29.json"

CHECKED_AT = "2026-07-29"
EXPECTED = {"CSB": 32, "Leoch": 50, "Marathon": 49}
FIELDS = [
    "batch", "external_id", "name", "manufacturer_candidate", "mpn_candidate",
    "normalized_mpn", "source_sku", "normalized_sku", "partition",
    "source_tier", "source_path", "source_sha256", "source_url",
    "source_assertion", "collision_external_ids", "collision_reason",
    "hold_reason", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value).upper())


def parse_title(name: str) -> tuple[str, str]:
    match = re.search(r"\b(Leoch|Marathon|CSB)\s+([^()]+?)\s*(?:\(|$)", name, re.I)
    if not match:
        raise SystemExit(f"Cannot derive brand/model from title: {name}")
    return match.group(1).title() if match.group(1).lower() != "csb" else "CSB", match.group(2).strip()


def load_models(registry_paths: list[Path]) -> dict[str, set[str]]:
    """Return exact compact models declared in the saved manufacturer registries."""
    models: dict[str, set[str]] = defaultdict(set)
    for path in registry_paths:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for series in data.get("series", []):
            maker = series.get("manufacturer", "")
            for model in series.get("models", []):
                models[maker].add(compact(model))
    return models


def main() -> None:
    required = [INPUT, WAVE206, WAVE145, CSB_PDF, *CSB_REGISTRIES, *LEOCH_REGISTRIES]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"Required saved evidence is missing: {missing}")

    selected = []
    for row in read_csv(INPUT):
        if row["manufacturer"].strip():
            continue
        if not re.search(r"\b(?:Leoch|Marathon|CSB)\b", row["name"], re.I):
            continue
        maker, mpn = parse_title(row["name"])
        selected.append({**row, "manufacturer_candidate": maker, "mpn_candidate": mpn})
    counts = Counter(row["manufacturer_candidate"] for row in selected)
    if counts != Counter(EXPECTED) or len(selected) != 131:
        raise SystemExit(f"Wave233-C input drift: rows={len(selected)}, counts={dict(counts)}")
    ids = [row["external_id"] for row in selected]
    if len(ids) != len(set(ids)):
        raise SystemExit("Wave233-C input has duplicate external IDs")
    if any(row["sku"].strip() for row in selected):
        raise SystemExit("Wave233-C expected blank source SKUs; input changed")

    # Validate the saved CSB evidence remains exactly the documented suffix hold.
    evidence_1418 = next((row for row in read_csv(WAVE206) if row["product_external_id"] == "bitrix:1418"), None)
    if not evidence_1418 or evidence_1418["safe_to_apply"] != "false" or "not the offered FR-suffixed" not in evidence_1418["hold_reason"]:
        raise SystemExit("Wave206 CSB HRL12390W FR suffix hold is missing or changed")
    if evidence_1418["snapshot_sha256"].lower() != sha256(CSB_PDF):
        raise SystemExit("Pinned CSB HRL12390W PDF hash changed")

    registries = load_models(CSB_REGISTRIES + LEOCH_REGISTRIES)
    # The four references below are retained only as audit context.  They are
    # URL assertions in an old decision document, not locally saved official
    # snapshots, and therefore cannot become PASS evidence in this wave.
    wave145 = json.loads(WAVE145.read_text(encoding="utf-8-sig"))
    unpinned_decisions = {
        "bitrix:1796": "HR1221W F2",
        "bitrix:2777": "GP12120 F2",
        "bitrix:3027": "GP12400",
        "bitrix:3258": "HRL1234W F2FR",
    }
    found_decisions = {item.get("legacy_element_id"): item for item in wave145.get("decisions", [])}
    if not all(found_decisions.get(external_id.split(":", 1)[1], {}).get("decision") == "same_identity" for external_id in unpinned_decisions):
        raise SystemExit("Wave145 CSB context decisions drifted")

    normalized_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in selected:
        normalized_groups[(row["manufacturer_candidate"], compact(row["mpn_candidate"]))].append(row["external_id"])

    ledger = []
    for row in selected:
        maker, mpn = row["manufacturer_candidate"], row["mpn_candidate"]
        normalized_mpn = compact(mpn)
        peers = sorted(external_id for external_id in normalized_groups[(maker, normalized_mpn)] if external_id != row["external_id"])
        source_tier = source_path = source_hash = source_url = assertion = ""
        partition = "hold_no_pinned_exact_source"
        hold = "No saved SHA-pinned first-party source proves this exact offered manufacturer+MPN."

        if row["external_id"] == "bitrix:1418":
            partition = "hold_exact_suffix_conflict"
            source_tier = "manufacturer_primary"
            source_path = CSB_PDF.relative_to(ROOT).as_posix()
            source_hash = sha256(CSB_PDF)
            source_url = evidence_1418["source_url"]
            assertion = "Pinned official PDF proves HRL12390W only; offered MPN retains FR suffix."
            hold = "Exact suffix conflict: source model HRL12390W does not prove offered HRL12390W FR."
        elif row["external_id"] in unpinned_decisions:
            partition = "hold_unpinned_historical_assertion"
            assertion = "Prior local review cites an official URL but stores no immutable official snapshot."
            hold = "Historical URL assertion is not SHA-pinned local primary evidence; exact identity remains HOLD."
        elif normalized_mpn in registries.get(maker, set()):
            # Kept fail-closed even if a model appears in a generated registry:
            # this wave has no immutable original snapshot attached to that row.
            partition = "hold_registry_without_pinned_primary_snapshot"
            hold = "Generated manufacturer registry is not an immutable saved primary snapshot for this offered row."

        collision_reason = "normalized_manufacturer_mpn_collision" if peers else ""
        if peers:
            partition = "hold_normalized_mpn_collision"
            hold = (hold + " Normalized manufacturer+MPN also appears on another in-scope row; "
                    "do not assign identity before duplicate adjudication.")
        ledger.append({
            "batch": "wave233c_leoch_marathon_csb", "external_id": row["external_id"], "name": row["name"],
            "manufacturer_candidate": maker, "mpn_candidate": mpn, "normalized_mpn": normalized_mpn,
            "source_sku": row["sku"], "normalized_sku": compact(row["sku"]), "partition": partition,
            "source_tier": source_tier, "source_path": source_path, "source_sha256": source_hash,
            "source_url": source_url, "source_assertion": assertion,
            "collision_external_ids": "|".join(peers), "collision_reason": collision_reason,
            "hold_reason": hold, "safe_to_apply": "false",
        })

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)

    manifest = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "review_batch": "wave233c_leoch_marathon_csb",
        "checked_at": CHECKED_AT,
        "products": [],
        "note": "No PASS rows: every candidate requires an immutable, exact first-party source and collision clearance.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    partitions = Counter(row["partition"] for row in ledger)
    source_inventory = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in [CSB_PDF, *CSB_REGISTRIES, *LEOCH_REGISTRIES]]
    summary = {
        "schema_version": 1,
        "batch": "wave233c_leoch_marathon_csb",
        "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(selected), "manufacturer_counts": dict(sorted(counts.items()))},
        "source_inventory": source_inventory,
        "exact_primary_pass_rows": 0,
        "unpinned_historical_decision_rows": sorted(unpinned_decisions),
        "normalized_mpn_collisions": [{"manufacturer": maker, "normalized_mpn": mpn, "external_ids": ids} for (maker, mpn), ids in sorted(normalized_groups.items()) if len(ids) > 1],
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(ledger), "partition_counts": dict(sorted(partitions.items()))},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": 0},
        "policy": {"exact_primary_source_required": True, "normalized_mpn_and_sku_checked": True, "database_mutations": 0, "media_mutations": 0, "commercial_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "partitions": dict(sorted(partitions.items())), "pass_rows": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
