#!/usr/bin/env python3
"""Build the fail-closed Wave203 payment/POS official-evidence partition."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave203-pos-official-source-evidence.json"
OUTPUT = ROOT / "docs/audits/generated/wave203-pos-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave203-pos-evidence-summary.json"

BRANDS = {
    "VeriFone", "Ingenico", "Pax", "Castles", "Dejavoo", "FirstData",
    "Hypercom", "Newpos", "Sagem", "Sunmi", "Bitel",
}
EXPECTED_ROWS = 42
ALLOWED_PARTITIONS = {"exact_safe", "compatibility_only", "conflict", "no_evidence"}

FIELDNAMES = [
    "batch", "product_external_id", "brand", "name", "model_tokens",
    "partition", "evidence_scope", "source_tier", "source_ids", "source_urls",
    "source_evidence_sha256", "snapshot_paths", "snapshot_sha256s",
    "verified_facts", "unsupported_legacy_claims",
    "conflict_reason", "replacement_manufacturer", "replacement_mpn",
    "manufacturer_mpn_inference", "repeat_handling", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


COMPATIBILITY = {
    **{f"bitrix:{value}": "castles-v3m2-official-product-page" for value in (12201, 12202, 12203)},
    **{f"bitrix:{value}": "dejavoo-z9-official-datasheet" for value in (23983, 23984, 23985)},
    **{f"bitrix:{value}": "newpos-new8110-official-history" for value in (12147, 12331)},
    **{f"bitrix:{value}": "pax-official-terminal-portfolio" for value in (12342, 12343, 12344, 12345, 12346, 12347)},
    "bitrix:12359": "sunmi-p2-t6900-official-spec",
    "bitrix:12284": "ingenico-pi20-03-battery-bulletin",
    "bitrix:12285": "ingenico-pi20-03-battery-bulletin",
    "bitrix:12397": "verifone-se-vx680-webshop",
}

EXACT = {
    "bitrix:12398": {
        "source_id": "verifone-se-vx680-webshop",
        "manufacturer": "Verifone",
        "mpn": "BPK268-001-01-A",
        "facts": "exact_oem_part=BPK268-001-01-A|terminal=VX680|product_type=battery_pack",
        "unsupported": "capacity=1800mAh",
    },
}

CONFLICTS = {
    "bitrix:12286": {
        "source_id": "ingenico-pi20-03-battery-bulletin",
        "facts": "exact_oem_part=F12432566|compatibility=Move/3500;Move/5000|official_capacity=2900mAh",
        "unsupported": "legacy_capacity=3000mAh",
        "reason": "exact OEM part F12432566 is documented as 2900mAh, not the legacy 3000mAh claim",
    },
}


def load_sources() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    if registry.get("schema_version") != 1:
        raise SystemExit("Unsupported official source evidence schema")
    sources = {source["id"]: source for source in registry["sources"]}
    if len(sources) != len(registry["sources"]):
        raise SystemExit("Official source evidence IDs are not unique")
    for source_id, source in sources.items():
        if not str(source.get("url", "")).startswith("https://"):
            raise SystemExit(f"Non-HTTPS official source: {source_id}")
        if not source.get("publisher") or not source.get("pinned_facts"):
            raise SystemExit(f"Incomplete pinned evidence: {source_id}")
    return registry, sources


def validate_snapshot(source: dict[str, object]) -> tuple[bool, str]:
    snapshot_path = str(source.get("snapshot_path", ""))
    expected_sha = str(source.get("snapshot_sha256", ""))
    required_tokens = [str(token) for token in source.get("required_exact_tokens", [])]
    if not snapshot_path or not expected_sha or not required_tokens:
        return False, "source has no pinned local snapshot contract"
    path = ROOT / snapshot_path
    if not path.is_file():
        return False, f"pinned snapshot is missing: {snapshot_path}"
    data = path.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha:
        return False, f"pinned snapshot SHA256 mismatch: expected {expected_sha}, got {actual_sha}"
    text = data.decode("utf-8", errors="replace").casefold()
    missing = [token for token in required_tokens if token.casefold() not in text]
    if missing:
        return False, "pinned snapshot lacks exact tokens: " + ", ".join(missing)
    return True, "snapshot_sha256_and_exact_tokens_verified"


def source_fields(source_ids: list[str], sources: dict[str, dict[str, object]]) -> dict[str, str]:
    selected = [sources[source_id] for source_id in source_ids]
    return {
        "source_ids": ";".join(source_ids),
        "source_urls": ";".join(str(source["url"]) for source in selected),
        "source_evidence_sha256": canonical_sha256(selected),
        "snapshot_paths": ";".join(
            str(source.get("snapshot_path", "")) for source in selected
            if source.get("snapshot_path")
        ),
        "snapshot_sha256s": ";".join(
            str(source.get("snapshot_sha256", "")) for source in selected
            if source.get("snapshot_sha256")
        ),
    }


def find_prior_evidence(candidate_ids: set[str]) -> dict[str, list[str]]:
    """Fail closed if another evidence partition already owns a candidate."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "docs/audits/generated").glob("*evidence*.csv")):
        if path.resolve() == OUTPUT.resolve():
            continue
        # Current-wave sibling partitions are reconciled by the Wave203 union gate.
        # Only earlier waves can make a row "previously processed" here.
        if path.name.startswith("wave203-"):
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    external_id = row.get("product_external_id") or row.get("external_id") or ""
                    if external_id in candidate_ids:
                        found.setdefault(external_id, []).append(path.relative_to(ROOT).as_posix())
        except (OSError, UnicodeDecodeError, csv.Error):
            # Unrelated inaccessible pytest temp directories are not evidence CSV files.
            continue
    return found


def classify(candidate: dict[str, str], sources: dict[str, dict[str, object]]) -> dict[str, str]:
    external_id = candidate["product_external_id"]
    model_tokens = candidate["model_tokens_unverified"]
    row = {
        "batch": "wave203_pos_official_evidence",
        "product_external_id": external_id,
        "brand": candidate["brand_or_series"],
        "name": candidate["name"],
        "model_tokens": model_tokens,
        "partition": "no_evidence",
        "evidence_scope": "none_for_exact_offered_pack",
        "source_tier": "none",
        "source_ids": "",
        "source_urls": "",
        "source_evidence_sha256": "",
        "snapshot_paths": "",
        "snapshot_sha256s": "",
        "verified_facts": "",
        "unsupported_legacy_claims": f"unverified_model_or_part_tokens={model_tokens}",
        "conflict_reason": "no primary manufacturer/service/accessory source tied the offered replacement pack to an exact part",
        "replacement_manufacturer": "",
        "replacement_mpn": "",
        "manufacturer_mpn_inference": "none",
        "repeat_handling": "new_review",
        "safe_to_apply": "false",
    }

    exact = EXACT.get(external_id)
    if exact:
        source_id = str(exact["source_id"])
        snapshot_valid, snapshot_reason = validate_snapshot(sources[source_id])
        if not snapshot_valid:
            row.update(
                evidence_scope="exact_source_snapshot_invalid_hold",
                source_tier="manufacturer_primary_unreproducible",
                verified_facts="",
                unsupported_legacy_claims=(
                    f"candidate_exact_part={exact['mpn']}|{exact['unsupported']}"
                ),
                conflict_reason=snapshot_reason,
                repeat_handling="source_snapshot_invalid",
                **source_fields([source_id], sources),
            )
            return row
        row.update(
            partition="exact_safe",
            evidence_scope="exact_oem_accessory_part_identity",
            source_tier="manufacturer_primary_pinned",
            verified_facts=str(exact["facts"]),
            unsupported_legacy_claims=str(exact["unsupported"]),
            conflict_reason="",
            replacement_manufacturer=str(exact["manufacturer"]),
            replacement_mpn=str(exact["mpn"]),
            manufacturer_mpn_inference="explicit_official_exact_part_only",
            repeat_handling="new_exact_source",
            safe_to_apply="true",
            **source_fields([source_id], sources),
        )
        return row

    conflict = CONFLICTS.get(external_id)
    if conflict:
        source_id = str(conflict["source_id"])
        row.update(
            partition="conflict",
            evidence_scope="exact_oem_part_conflicts_with_legacy_capacity",
            source_tier="manufacturer_primary_pinned",
            verified_facts=str(conflict["facts"]),
            unsupported_legacy_claims=str(conflict["unsupported"]),
            conflict_reason=str(conflict["reason"]),
            **source_fields([source_id], sources),
        )
        return row

    source_id = COMPATIBILITY.get(external_id)
    if source_id:
        facts = ";".join(str(value) for value in sources[source_id]["pinned_facts"])
        row.update(
            partition="compatibility_only",
            evidence_scope="official_device_or_terminal_battery_context_only",
            source_tier="manufacturer_primary_pinned",
            verified_facts=facts,
            conflict_reason="official source does not identify the offered replacement pack",
            **source_fields([source_id], sources),
        )
    return row


def main() -> None:
    registry, sources = load_sources()
    with INPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        candidates = [
            row for row in csv.DictReader(handle)
            if row["recommended_wave"] == "wave203"
            and row["repeat_handling"] == "new"
            and row["brand_or_series"] in BRANDS
        ]

    if len(candidates) != EXPECTED_ROWS:
        raise SystemExit(f"Expected {EXPECTED_ROWS} POS candidates, found {len(candidates)}")
    candidate_ids = {row["product_external_id"] for row in candidates}
    if len(candidate_ids) != EXPECTED_ROWS:
        raise SystemExit("Wave203 POS candidate IDs are not unique")
    if (set(EXACT) | set(CONFLICTS) | set(COMPATIBILITY)) - candidate_ids:
        raise SystemExit("A curated decision references a non-candidate external ID")
    prior_evidence = find_prior_evidence(candidate_ids)
    if prior_evidence:
        raise SystemExit(
            "Wave203 POS candidates already exist in prior evidence: "
            + json.dumps(prior_evidence, ensure_ascii=False, sort_keys=True)
        )

    rows = [classify(candidate, sources) for candidate in candidates]
    if {row["partition"] for row in rows} - ALLOWED_PARTITIONS:
        raise SystemExit("Unsupported evidence partition")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["partition"] for row in rows)
    safe_rows = [row for row in rows if row["safe_to_apply"] == "true"]
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": "wave203_pos_official_evidence",
        "created_at": "2026-07-29",
        "input": {
            "path": INPUT.relative_to(ROOT).as_posix(),
            "sha256": sha256(INPUT),
            "candidate_rows": len(candidates),
        },
        "pinned_evidence_registry": {
            "path": REGISTRY.relative_to(ROOT).as_posix(),
            "sha256": sha256(REGISTRY),
            "source_rows": len(registry["sources"]),
        },
        "output": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "sha256": sha256(OUTPUT),
            "rows": len(rows),
        },
        "partition_counts": dict(sorted(counts.items())),
        "safe_to_apply": {
            "rows": len(safe_rows),
            "external_ids": sorted(row["product_external_id"] for row in safe_rows),
        },
        "previously_processed": {"rows": 0, "external_ids": []},
        "policy": {
            "primary_sources_only": True,
            "device_compatibility_never_sets_replacement_identity": True,
            "unsupported_capacity_voltage_or_part_claims_not_promoted": True,
            "database_mutations": 0,
        },
        "official_sources": [
            {
                "id": source["id"],
                "publisher": source["publisher"],
                "url": source["url"],
                "evidence_sha256": canonical_sha256(source),
                "snapshot_path": source.get("snapshot_path", ""),
                "snapshot_sha256": source.get("snapshot_sha256", ""),
                "snapshot_validation": (
                    validate_snapshot(source)[1]
                    if source.get("snapshot_path")
                    else "not_required_for_non_exact_source"
                ),
            }
            for source in registry["sources"]
        ],
        "notes": [
            "The 42 input rows are explicitly wave203/new; no prior evidence artifact contained these external IDs.",
            "Only Verifone BPK268-001-01-A has pinned exact official accessory identity and is safe for a later guarded identity apply.",
            "Ingenico F12432566 is held because the legacy 3000mAh claim conflicts with the official 2900mAh specification.",
        ],
    }
    SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
