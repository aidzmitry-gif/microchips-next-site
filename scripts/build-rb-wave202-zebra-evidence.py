#!/usr/bin/env python3
"""Build the conservative Wave 202 Zebra legacy battery evidence partition."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/wave201-industrial-batch-candidates.csv"
OUTPUT = ROOT / "docs/audits/generated/wave202-zebra-legacy-mobile-computers-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave202-zebra-legacy-mobile-computers-evidence-summary.json"
PRIOR_MANIFEST = ROOT / "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json"

BATCH = "zebra_legacy_mobile_computers"
WHERE_USED_URL = (
    "https://www.zebra.com/content/dam/zebra_dam/en/guide/corporate/"
    "bts-guide-batteries-where-used-hyperlinks-en-us.pdf"
)
MC9000_GUIDE_URL = (
    "https://www.zebra.com/content/dam/support-dam/en/documentation/unrestricted/"
    "guide/product/mc9090-ce-mc9000-k-s-product-reference-guide-en-us.pdf"
)
MC67_GUIDE_URL = (
    "https://www.zebra.com/content/dam/support-dam/en/documentation/unrestricted/"
    "guide/product/mc67-android-v444-ug-en.pdf"
)
MC30_REGULATORY_URL = "https://fcc.report/FCC-ID/H9P2121160/488206.pdf"
MC94_REGULATORY_URL = (
    "https://www.zebra.com/content/dam/support-dam/en/documentation/unrestricted/"
    "guide/regulatory/mc9401-rg-en.pdf"
)
ZEBRA_COMPLIANCE_URL = (
    "https://www.zebra.com/ap/en/about-zebra/company-information/compliance/"
    "declarations-of-conformity.html"
)

FIELDNAMES = [
    "batch",
    "product_external_id",
    "name",
    "model_tokens",
    "explicit_legacy_part_tokens",
    "partition",
    "evidence_scope",
    "source_tier",
    "source_urls",
    "verified_facts",
    "unsupported_legacy_claims",
    "conflict_reason",
    "replacement_manufacturer",
    "replacement_mpn",
    "manufacturer_mpn_inference",
    "prior_manifest_refs",
    "repeat_handling",
    "current_state_check",
    "safe_to_apply",
]

PART_TOKEN_RE = re.compile(
    r"(?ix)\b("
    r"BTRY[-A-Z0-9]+|BTRYMC30LA|"
    r"BT[-A-Z0-9]+|"
    r"P\d[\d-]+|"
    r"(?:82|21|55|KT|CC)-\d[\d-]+|"
    r"GP75AAAH3AMXZ"
    r")\b"
)
MODEL_RE = re.compile(
    r"(?ix)\b("
    r"LS4278|LS3478|LS3578|LI4278|DS3478|DS3578|DS6878|"
    r"CS3070|CS33|CS4070|"
    r"MC9500|MC9590|MC9596|MC9000|MC9090|MC9190|"
    r"MC9300|MC93|MC3300|MC3200|MC32N0|"
    r"MC3190|MC3100|MC3090|MC3070|MC3000|MC30X0|"
    r"MC2180|MC21XX|MC21|MC18|MC17A|MC17T|MC17|"
    r"MC1000|MC55A0|MC5590|MC5574|MC55|MC65|MC67|"
    r"MC5040|MC50|MC45|MC40C|MC40|MC36|MC70|MC75|"
    r"TC75X|TC70X|TC75|TC70|TC57|TC56|TC55AH|TC55|TC52|TC51|TC2X|"
    r"WT41N0|WT4090|WT4070|WT4000|WT60A0|WT6000|"
    r"RS6000|RS507|RS50|"
    r"QLN420|QLN320|QLN220|QL320|QL220|ZQ510|ZQ300|"
    r"RW320|RW220|EM220II|EM220|IMZ320|MZ420L|"
    r"EC55|EC50|EC30|ES405|ES400|ES85|"
    r"VC80|VC5090|SB1|MPM100|WA3006|WA3026|"
    r"PDT8000|PDT-8037|PDT|PPT|SPT|P360|CAMEO\s*[23]|SMB\s*K3/470"
    r")\b"
)
CAPACITY_RE = re.compile(r"(?i)\b(\d{2,5})\s*m(?:a|а)h\b|\b(\d{2,5})\s*м(?:а|a)ч\b")
VOLTAGE_RE = re.compile(r"(?i)\b(\d+(?:[.,]\s*\d+)?)\s*[vвb]\b")


EXACT_SAFE = {
    "bitrix:12162": {
        "mpn": "BTRY-MC55EAB02",
        "url": MC67_GUIDE_URL,
        "facts": "exact_oem_part=BTRY-MC55EAB02|compatibility=MC65;MC67|capacity=3600mAh",
        "unsupported": "legacy_title_also_claims_MC55",
        "prior": "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json",
    },
    "bitrix:12315": {
        "mpn": "82-97300-02",
        "url": WHERE_USED_URL,
        "facts": "exact_oem_part=82-97300-02|compatibility=CS4070",
        "unsupported": "capacity=950mAh",
        "prior": "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json",
    },
    "bitrix:12327": {
        "mpn": "BT-000318-01",
        "url": WHERE_USED_URL,
        "facts": "exact_oem_part=BT-000318-01|compatibility=TC70X;TC75X",
        "unsupported": "legacy_token=BT-000318_without_revision|capacity=4550mAh",
        "prior": "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json",
    },
    "bitrix:12409": {
        "mpn": "P1002512",
        "url": ZEBRA_COMPLIANCE_URL,
        "facts": "exact_oem_part=P1002512|compatibility=EM220",
        "unsupported": "capacity=1000mAh|compatibility=EM220II",
        "prior": "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json",
    },
    "bitrix:12418": {
        "mpn": "BT-000314-01",
        "url": WHERE_USED_URL,
        "facts": "exact_oem_part=BT-000314-01|compatibility=TC56;TC57",
        "unsupported": "capacity=4200mAh|compatibility=TC51;TC52",
        "prior": "docs/imports/rb-source-backed-description-drafts-b2b-terminals-wave174-2026-07-29.json",
    },
}

SUPERSEDED_EXACT_SOURCE = {
    "bitrix:12122": {
        "mpn": "P1083277-002",
        "url": WHERE_USED_URL,
        "superseded_revision": "2026-06-23",
        "historical_claim": "exact_oem_part=P1083277-002|compatibility=ZQ310;ZQ320",
        "unsupported": "umbrella_name=ZQ300|capacity=2200mAh|voltage=7.2V",
    },
}

CONTRADICTORY_PARTS = {
    "21-62606-01": "same legacy part token carries 2200mAh, 2600mAh and 3400mAh claims",
    "BTRYMC30LA": "same legacy part token carries 2740mAh and 4800mAh claims",
    "BTRY-ES40EAB00": "same legacy part token carries 1500mAh and 3000mAh claims",
    "BTRY-MC32-52MA-01": "official registry separates MC32 and MC33 pack families; legacy rows also mix 2600mAh and 5200mAh",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_tokens(pattern: re.Pattern[str], value: str) -> list[str]:
    return sorted({match.group(0).upper().replace("\xa0", " ") for match in pattern.finditer(value)})


def capacities(name: str) -> list[str]:
    values = []
    for match in CAPACITY_RE.finditer(name):
        value = match.group(1) or match.group(2)
        if value:
            values.append(f"{value}mAh")
    return sorted(set(values))


def voltages(name: str) -> list[str]:
    values = []
    for match in VOLTAGE_RE.finditer(name):
        raw = re.sub(r"\s+", "", match.group(1)).replace(",", ".")
        values.append(f"{raw}V")
    return sorted(set(values))


def family_evidence(name_upper: str) -> tuple[str, str]:
    if re.search(r"\bMC(?:9000|9090|9190)\b", name_upper):
        return MC9000_GUIDE_URL, "device_compatibility=MC9000_family; removable_main_battery_documented"
    if re.search(r"\bMC(?:3000|3070|3090|30X0|3100|3190)\b", name_upper):
        return (
            f"{WHERE_USED_URL}|{MC30_REGULATORY_URL}",
            "device_compatibility=MC30xx_or_MC31xx; multiple_distinct_pack_families_documented",
        )
    if re.search(r"\bMC(?:3200|32N0|3300)\b", name_upper):
        return WHERE_USED_URL, "device_compatibility=MC32_or_MC33; official_registry_separates_pack_families"
    if re.search(r"\bMC(?:55|55A0|5590|5574|65|67)\b", name_upper):
        return MC67_GUIDE_URL, "device_compatibility=MC55_MC65_MC67_family_only"
    if re.search(r"\b(?:TC51|TC52|TC56|TC57)\b", name_upper):
        return WHERE_USED_URL, "device_compatibility=TC5X_family_only"
    if re.search(r"\b(?:TC70|TC75)\b", name_upper):
        return WHERE_USED_URL, "device_compatibility=TC7X_family_only"
    if re.search(r"\b(?:MC93|MC9300)\b", name_upper):
        return (
            f"{WHERE_USED_URL}|{MC94_REGULATORY_URL}",
            "device_lineage=MC93_MC94; official_registry_distinguishes_current_pack_models",
        )
    if re.search(r"\b(?:WT4000|WT4070|WT4090|WT41N0|WT6000|WT60A0|RS6000)\b", name_upper):
        return WHERE_USED_URL, "device_compatibility=WT_or_RS_wearable_family_only"
    if re.search(r"\b(?:EC30|EC50|EC55|MC18|MC21|MC2180|MC21XX|TC2X|VC80)\b", name_upper):
        return WHERE_USED_URL, "device_family_exists_in_official_battery_registry; exact_offered_pack_not_proven"
    if re.search(r"\b(?:ZQ300|ZQ510|QLN220|QLN320|QLN420|QL220|QL320)\b", name_upper):
        return WHERE_USED_URL, "printer_family_battery_context_only; exact_offered_pack_not_proven"
    return "", ""


def classify(candidate: dict[str, str]) -> dict[str, str]:
    external_id = candidate["product_external_id"]
    name = candidate["name"]
    name_upper = name.upper().replace("\xa0", " ")
    part_tokens = unique_tokens(PART_TOKEN_RE, name)
    model_tokens = unique_tokens(MODEL_RE, name)
    capacity_claims = capacities(name)
    voltage_claims = voltages(name)

    row = {
        "batch": BATCH,
        "product_external_id": external_id,
        "name": name,
        "model_tokens": ";".join(model_tokens),
        "explicit_legacy_part_tokens": ";".join(part_tokens),
        "partition": "",
        "evidence_scope": "",
        "source_tier": "",
        "source_urls": "",
        "verified_facts": "",
        "unsupported_legacy_claims": "",
        "conflict_reason": "",
        "replacement_manufacturer": "",
        "replacement_mpn": "",
        "manufacturer_mpn_inference": "none",
        "prior_manifest_refs": "",
        "repeat_handling": "new_review",
        "current_state_check": "not_required_for_read_only_partition",
        "safe_to_apply": "false",
    }

    superseded = SUPERSEDED_EXACT_SOURCE.get(external_id)
    if superseded:
        row.update(
            partition="no_evidence",
            evidence_scope="no_current_exact_source_source_superseded",
            source_tier="manufacturer_primary_superseded",
            source_urls=superseded["url"],
            verified_facts="",
            unsupported_legacy_claims=(
                f"historical_unreproducible_claim={superseded['historical_claim']}|"
                f"{superseded['unsupported']}"
            ),
            conflict_reason=(
                "source_superseded: current official PDF revision "
                f"{superseded['superseded_revision']} no longer lists "
                f"{superseded['mpn']}; no immutable official snapshot is stored"
            ),
            repeat_handling="source_superseded",
            current_state_check="application_blocked_pending_reproducible_primary_source",
        )
        return row

    exact = EXACT_SAFE.get(external_id)
    if exact:
        previously_processed = bool(exact["prior"])
        row.update(
            partition="exact_safe",
            evidence_scope="exact_oem_replacement_part_identity",
            source_tier="manufacturer_primary",
            source_urls=exact["url"],
            verified_facts=exact["facts"],
            unsupported_legacy_claims=exact["unsupported"],
            replacement_manufacturer="Zebra",
            replacement_mpn=exact["mpn"],
            manufacturer_mpn_inference="explicit_official_exact_part_only",
            prior_manifest_refs=exact["prior"],
            repeat_handling="previously_processed" if previously_processed else "new_exact_source",
            current_state_check=(
                "not_rechecked_previously_processed"
                if previously_processed
                else "published=true|readiness_class=legacy_text_only|applied_description=false|historical_registry=do_not_publish_before_exact_source"
            ),
            safe_to_apply="false" if previously_processed else "true",
        )
        return row

    conflict_reasons = []
    for token in part_tokens:
        compact = token.replace(" ", "")
        if compact in CONTRADICTORY_PARTS:
            conflict_reasons.append(CONTRADICTORY_PARTS[compact])
        elif token in CONTRADICTORY_PARTS:
            conflict_reasons.append(CONTRADICTORY_PARTS[token])

    has_mc30 = bool(re.search(r"\bMC(?:3000|3070|3090|30X0)\b", name_upper))
    has_mc31 = bool(re.search(r"\bMC(?:3100|3190)\b", name_upper))
    if has_mc30 and has_mc31:
        conflict_reasons.append("legacy title combines MC30xx and MC31xx pack families")

    has_mc32 = bool(re.search(r"\bMC(?:3200|32N0)\b", name_upper))
    has_mc33 = bool(re.search(r"\bMC3300\b", name_upper))
    if has_mc32 and has_mc33:
        conflict_reasons.append("legacy title combines MC32 and MC33 pack families")

    if "BT-000370" in part_tokens:
        conflict_reasons.append(
            "legacy BT-000370 claim is 6600mAh while official Zebra regulatory evidence identifies BT-000370 as 7000mAh"
        )
    if "BT000262A01" in {token.replace("-", "") for token in part_tokens}:
        conflict_reasons.append(
            "legacy BT000262A01 token does not match the official WT6X part revision BT-000262-50"
        )

    source_urls, family_facts = family_evidence(name_upper)
    legacy_claims = []
    if capacity_claims:
        legacy_claims.append("capacity=" + ";".join(capacity_claims))
    if voltage_claims:
        legacy_claims.append("voltage=" + ";".join(voltage_claims))
    if part_tokens:
        legacy_claims.append("unverified_part_tokens=" + ";".join(part_tokens))

    if conflict_reasons:
        row.update(
            partition="conflict",
            evidence_scope="conflict_or_overbroad_compatibility",
            source_tier=(
                "manufacturer_primary_plus_legacy_conflict"
                if source_urls
                else "legacy_cross_record_conflict"
            ),
            source_urls=source_urls,
            verified_facts=family_facts or "cross_record_same_token_conflict_only",
            unsupported_legacy_claims="|".join(legacy_claims),
            conflict_reason="|".join(sorted(set(conflict_reasons))),
        )
        return row

    if source_urls:
        row.update(
            partition="compatibility_only",
            evidence_scope="oem_device_compatibility_only",
            source_tier="manufacturer_primary",
            source_urls=source_urls,
            verified_facts=family_facts,
            unsupported_legacy_claims="|".join(legacy_claims) or "replacement_pack_identity",
        )
        return row

    row.update(
        partition="no_evidence",
        evidence_scope="none_for_exact_offered_pack",
        source_tier="none",
        unsupported_legacy_claims="|".join(legacy_claims) or "replacement_pack_identity",
        conflict_reason="no accessible primary source tied the offered replacement pack to an exact OEM part",
    )
    return row


def main() -> None:
    with INPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        candidates = [row for row in csv.DictReader(handle) if row["batch"] == BATCH]

    if len(candidates) != 151:
        raise SystemExit(f"Expected 151 {BATCH} candidates, found {len(candidates)}")
    if len({row["product_external_id"] for row in candidates}) != 151:
        raise SystemExit("Candidate external IDs are not unique")

    prior_data = json.loads(PRIOR_MANIFEST.read_text(encoding="utf-8-sig"))
    prior_ids = {
        product["external_id"]
        for product in prior_data["products"]
        if product.get("external_id") in EXACT_SAFE
    }
    expected_prior = {external_id for external_id, evidence in EXACT_SAFE.items() if evidence["prior"]}
    if prior_ids != expected_prior:
        raise SystemExit(
            f"Prior manifest reuse mismatch: expected {sorted(expected_prior)}, got {sorted(prior_ids)}"
        )

    rows = [classify(candidate) for candidate in candidates]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["partition"] for row in rows)
    summary = {
        "schema_version": 1,
        "site": "microchips-by",
        "batch": BATCH,
        "created_at": "2026-07-29",
        "input": {
            "path": INPUT.relative_to(ROOT).as_posix(),
            "sha256": sha256(INPUT),
            "candidate_rows": len(candidates),
        },
        "output": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "sha256": sha256(OUTPUT),
            "rows": len(rows),
        },
        "partition_counts": dict(sorted(counts.items())),
        "policy": {
            "oem_documents_prove_device_compatibility_only_by_default": True,
            "replacement_manufacturer_or_mpn_requires_explicit_exact_official_part": True,
            "unsupported_legacy_capacity_or_voltage_is_not_promoted": True,
            "database_mutations": 0,
        },
        "prior_manifest_reuse": {
            "path": PRIOR_MANIFEST.relative_to(ROOT).as_posix(),
            "external_ids": sorted(expected_prior),
            "rows": len(expected_prior),
        },
        "new_exact_source_rows": sorted(
            row["product_external_id"]
            for row in rows
            if row["partition"] == "exact_safe" and row["repeat_handling"] == "new_exact_source"
        ),
        "source_superseded_rows": sorted(
            row["product_external_id"]
            for row in rows
            if row["repeat_handling"] == "source_superseded"
        ),
        "safe_to_apply": {
            "rows": sum(row["safe_to_apply"] == "true" for row in rows),
            "external_ids": sorted(
                row["product_external_id"]
                for row in rows
                if row["safe_to_apply"] == "true"
            ),
        },
        "official_sources": [
            {
                "url": WHERE_USED_URL,
                "scope": "Exact Zebra battery P/N and product-line mappings only where explicitly listed.",
            },
            {
                "url": MC9000_GUIDE_URL,
                "scope": "MC9000 device battery context only; no offered replacement-pack identity inference.",
            },
            {
                "url": MC67_GUIDE_URL,
                "scope": "MC65/MC67 compatibility and exact BTRY-MC55EAB02 evidence already reused from Wave174.",
            },
            {
                "url": MC30_REGULATORY_URL,
                "scope": "MC30xx configuration and capacity-variant boundary; not replacement manufacturer evidence.",
            },
            {
                "url": MC94_REGULATORY_URL,
                "scope": "BT-000370 3.6V/7000mAh regulatory fact; used to flag the 6600mAh conflict.",
            },
        ],
        "notes": [
            "Five exact identities reuse the prior Wave174 manifest, are marked previously_processed and are not safe to reapply.",
            "P1083277-002 is blocked: the current official PDF revision 2026-06-23 no longer lists it, and no immutable official snapshot is stored.",
            "All compatibility_only, conflict and no_evidence rows intentionally leave replacement manufacturer and MPN blank.",
        ],
    }
    SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
