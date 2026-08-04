#!/usr/bin/env python3
"""Build Wave242 strict manufacturer-primary identity and description evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-wave241c-reviewed-identity-skips.csv"
PRIOR = ROOT / "docs/audits/generated/rb-wave233c-leoch-marathon-csb-identity-ledger.csv"
SOURCE_DIR = ROOT / "docs/audits/sources/wave242-leoch-marathon-csb"
LEDGER = ROOT / "docs/audits/generated/rb-wave242-leoch-marathon-csb-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave242-leoch-marathon-csb-identity.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave242-leoch-marathon-csb-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave242-leoch-marathon-csb-2026-07-29.json"
CHECKED_AT = "2026-07-29"

INPUT_PINS = {
    "queue": "674d7284f10282b9f3f970f44478f096678b5bf47386de1a57cb2b85a754393e",
    "prior": "836d44056c27c5ff14326d669bc1110839fc125973424dd08b3d51af24215ca6",
}

SOURCES = {
    "csb": {
        "file": "csb-catalog-2026.pdf",
        "sha256": "79806a16440edc8e4704770ac2da6f76a5f6ab093e55474d3617e1da2fe822a8",
        "url": "https://csb-battery.com/wp-content/uploads/2026/03/CSB-Catalog-2026-Digital-Spread-1.pdf",
        "publisher": "CSB Energy Technology Co., Ltd.",
    },
    "marathon_l": {
        "file": "exide-marathon-l-xl-en.pdf",
        "sha256": "98c101e64d80c9d7990babf72a858d4475ba015b928752318b081de545cc8b62",
        "url": "https://www.exidegroup.com/eu/sites/default/files/2022-03/GNB_Marathon_L-XL_EN.pdf",
        "publisher": "Exide Technologies",
    },
    "marathon_mft": {
        "file": "exide-marathon-m-ft-en.pdf",
        "sha256": "10b33bc2cdd3cbf144c641c37f78c0c8bb71cbbb67492d326f722421d7047d03",
        "url": "https://www.exidegroup.com/ch/sites/default/files/2020-06/GNB_Marathon_M_FT_EN.pdf",
        "publisher": "Exide Technologies",
    },
    "marathon_mft_archive": {
        "file": "exide-marathon-front-terminal-spec-2014.pdf",
        "sha256": "0e4b28310b883296db407af5b97e463b7d8164739c8992bc08198b42ed547b4a",
        "url": "https://www.exidegroup.com/eu/sites/default/files/2017-01/Marathon%20Specifications%20for%20Front%20Terminal%20Batteries.pdf",
        "publisher": "Exide Technologies",
    },
    "marathon_m_archive": {
        "file": "exide-marathon-spec-2016.pdf",
        "sha256": "1d145ba8b5d910476df1fe3d2f2eb053a555e488837027e404aaf47d858e377a",
        "url": "https://www.exidegroup.com/eu/sites/default/files/2017-12/Section%2022.60%202016-09_0.pdf",
        "publisher": "Exide Technologies",
    },
    "leoch": {
        "file": "leoch-vrla-agm-2026.pdf",
        "sha256": "fcb5e7941e5a5a8a27303ddc15be2fe9216761ac0528c8af467aad1ca6e80a43",
        "url": "https://download.leoch.com/Network%20Power%20Battery/Leoch%20VRLA-AGM%20Series%20Product%20Brochure%20LB-VRLA-AGM-PB-EN-V4.5-202601.pdf",
        "publisher": "Leoch International Technology Limited",
    },
}

# Exact model rows from the pinned catalogue tables. Capacity is the first
# catalogue nominal Ah figure; alternate_capacity is retained when the offered
# title follows another documented rate.
CSB = {
    "GP645": (6, 4.5, None, 3, "GP", True), "GP6120": (6, 12, None, 3, "GP", True),
    "GP1272": (12, 7.2, None, 3, "GP", True), "GP12120": (12, 12, None, 3, "GP", True),
    "GP12170": (12, 17, None, 3, "GP", False), "GP12200": (12, 20, None, 3, "GP", False),
    "GP12260": (12, 26, None, 3, "GP", False), "GP12340": (12, 34, None, 3, "GP", False),
    "GP12400": (12, 40, None, 3, "GP", False), "GP12650": (12, 65, None, 3, "GP", False),
    "GP121000": (12, 100, None, 3, "GP", False), "GPL121000": (12, 100, None, 4, "GPL", False),
    "GPL12260": (12, 26, None, 4, "GPL", False), "GPL12520": (12, 52, None, 4, "GPL", False),
    "GPL12750": (12, 75, None, 4, "GPL", False), "GPL12880": (12, 88, None, 4, "GPL", False),
}

MARATHON_L = {
    "L2V220": (2, 220, 240), "L2V270": (2, 270, 294), "L2V320": (2, 320, 350),
    "L2V375": (2, 375, 410), "L2V425": (2, 425, 464), "L2V470": (2, 470, 514),
    "L2V520": (2, 520, 564), "L2V575": (2, 575, 624), "L6V110": (6, 112, 122),
    "L12V24": (12, 23.5, 26), "L12V32": (12, 31.5, 34),
    "XL12V50": (12, 50.4, 57.6), "XL12V70": (12, 66.6, 74),
}

MARATHON_MFT = {
    "M6V200FT": (6, 200, 200), "M12V35FT": (12, 35, 35),
    "M12V50FT": (12, 47, 48), "M12V60FT": (12, 59, 59),
    "M12V90FT": (12, 86, 86), "M12V105FT": (12, 100, 104),
    "M12V125FT": (12, 121, 125), "M12V155FT": (12, 155, 158),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def base_model(mpn: str) -> tuple[str, bool]:
    v0 = bool(re.search(r"(?:^|\s)V0$", mpn, re.I))
    base = re.sub(r"(?:\s+)?V0$", "", mpn, flags=re.I).strip()
    return re.sub(r"\s+", "", base), v0


def title_capacity(name: str) -> float:
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)Ah", name, re.I)
    if not match:
        raise RuntimeError(f"offered capacity absent: {name}")
    return float(match.group(1).replace(",", "."))


def close_capacity(offered: float, values: tuple[float, ...]) -> bool:
    return any(abs(offered - value) / max(value, 1) <= 0.05 for value in values)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def description(row: dict[str, str], manufacturer: str, mpn: str, source: dict[str, str],
                voltage: float, capacity: float, capacity_basis: str, series: str,
                evidence_scope: str) -> dict[str, object]:
    number = lambda value: f"{value:g}".replace(".", ",")
    return {
        "external_id": row["external_id"], "identity_scope": "exact", "manufacturer": manufacturer,
        "mpn": mpn, "display_name": row["name"], "technology": "AGM", "source_url": source["url"],
        "technical_attributes": {
            "Серия": series, "Технология": "AGM", "Номинальное напряжение": f"{number(voltage)} В",
            f"Номинальная ёмкость ({capacity_basis})": f"{number(capacity)} А·ч",
        },
        "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary",
        "source_publisher": source["publisher"], "manufacturer_primary": True,
        "evidence_scope": "exact_model", "checked_at": CHECKED_AT,
    }


def main() -> None:
    if sha256(QUEUE) != INPUT_PINS["queue"] or sha256(PRIOR) != INPUT_PINS["prior"]:
        raise SystemExit("Wave241c/Wave233c frozen input drifted")
    evidence_pages = {"csb": (2, 3), "marathon_l": (3,), "marathon_mft": (3,), "leoch": (0,)}
    texts: dict[str, str] = {}
    for key, source in SOURCES.items():
        path = SOURCE_DIR / source["file"]
        if sha256(path) != source["sha256"]:
            raise SystemExit(f"source drifted: {source['file']}")
        reader = PdfReader(path)
        texts[key] = "\n".join(reader.pages[index].extract_text() or "" for index in evidence_pages.get(key, ()))
    if "Figures are also valid for UL 94-V0 version" not in texts["marathon_l"]:
        raise SystemExit("Marathon L V0 variant statement absent")
    if "valid for UL 94-V0 version" not in texts["marathon_mft"]:
        raise SystemExit("Marathon M-FT V0 variant statement absent")
    if "LB-VRLA-AGM-PB-EN-V4.5-202601" not in texts["leoch"]:
        raise SystemExit("Leoch publication marker absent")

    with PRIOR.open(encoding="utf-8-sig", newline="") as stream:
        prior = list(csv.DictReader(stream))
    prior_by_id = {row["external_id"]: row for row in prior}
    with QUEUE.open(encoding="utf-8-sig", newline="") as stream:
        queued = [row for row in csv.DictReader(stream) if row["product_external_id"] in prior_by_id]
    if len(queued) != 131 or Counter(prior_by_id[row["product_external_id"]]["manufacturer_candidate"] for row in queued) != {"Leoch": 50, "Marathon": 49, "CSB": 32}:
        raise SystemExit("Wave242 frozen 131-row scope drifted")
    for row in queued:
        previous = prior_by_id[row["product_external_id"]]
        if row["name"] != previous["name"] or row["manufacturer"] or row["mpn"]:
            raise SystemExit(f"queue identity state drifted: {row['product_external_id']}")

    collisions = Counter((row["manufacturer_candidate"], row["normalized_mpn"]) for row in prior)
    ledger: list[dict[str, str]] = []
    identities: list[dict[str, str]] = []
    descriptions: list[dict[str, object]] = []
    for queued_row in queued:
        old = prior_by_id[queued_row["product_external_id"]]
        row = {"external_id": old["external_id"], "name": old["name"]}
        manufacturer, mpn = old["manufacturer_candidate"], old["mpn_candidate"]
        offered_capacity = title_capacity(old["name"])
        decision, partition, reason = "HOLD", "hold_no_new_exact_primary_source", "new pinned manufacturer catalogue does not prove the exact offered model"
        source_key = ""
        source_page = ""
        voltage = capacity = None
        capacity_basis = series = evidence_scope = ""
        terminal_check = "not_applicable"
        suffix_check = "not_applicable"

        if collisions[(manufacturer, old["normalized_mpn"])] > 1:
            partition, reason = "hold_normalized_mpn_collision", "normalized manufacturer+MPN collision remains unresolved"
        elif manufacturer == "CSB":
            suffix_f2 = bool(re.search(r"\sF2$", mpn, re.I))
            model = re.sub(r"\sF2$", "", mpn, flags=re.I)
            fact = CSB.get(model)
            if fact:
                voltage, capacity, _, source_page, series, allows_f2 = fact
                terminal_check = "F2 documented in model table" if suffix_f2 and allows_f2 else ("not_requested" if not suffix_f2 else "F2 not tied to model")
                if suffix_f2 and not allows_f2:
                    partition, reason = "hold_terminal_suffix_not_proven", "official table does not tie F2 to this exact model"
                elif close_capacity(offered_capacity, (capacity,)):
                    decision, partition, reason = "PASS", "pass_exact_primary_model_capacity_voltage", ""
                    source_key, capacity_basis, evidence_scope = "csb", "catalogue nominal rate", "exact_model_and_terminal_variant" if suffix_f2 else "exact_model"
                else:
                    partition, reason = "hold_offered_capacity_conflict", f"offered {offered_capacity:g}Ah differs from official {capacity:g}Ah"
            elif "FR" in mpn.upper() or "F2" in mpn.upper():
                partition, reason = "hold_exact_suffix_not_proven", "base family may occur, but the offered FR/F2FR suffix is not proved by the new table"
            elif re.match(r"(?:HR|HRL)", mpn, re.I):
                partition, reason = "hold_ah_capacity_not_proven", "official HR/HRL table rates the exact model in watts and does not prove the offered Ah capacity"
            elif mpn.startswith("TPL"):
                partition, reason = "hold_exact_model_not_in_current_catalogue", "current official TPL table lists a different exact SKU"
        elif manufacturer == "Marathon":
            model, is_v0 = base_model(mpn)
            suffix_check = "documented UL 94-V0 variant" if is_v0 else "base type"
            fact = MARATHON_L.get(model)
            if fact:
                voltage, capacity, alternate = fact
                if close_capacity(offered_capacity, (capacity, alternate)):
                    decision, partition, reason = "PASS", "pass_exact_primary_model_capacity_voltage_v0" if is_v0 else "pass_exact_primary_model_capacity_voltage", ""
                    source_key, source_page, capacity_basis, series = "marathon_l", "4", "C10, 1.80 V/cell, 20 °C", "Marathon L/XL"
                    evidence_scope = "exact_model_plus_documented_v0_variant" if is_v0 else "exact_model"
                else:
                    partition, reason = "hold_offered_capacity_conflict", f"offered {offered_capacity:g}Ah differs from official {capacity:g}/{alternate:g}Ah"
            else:
                fact = MARATHON_MFT.get(model)
                if fact:
                    voltage, capacity, alternate = fact
                    if close_capacity(offered_capacity, (capacity, alternate)):
                        decision, partition, reason = "PASS", "pass_exact_primary_model_capacity_voltage_v0" if is_v0 else "pass_exact_primary_model_capacity_voltage", ""
                        source_key, source_page, capacity_basis, series = "marathon_mft", "4", "C10, 1.80 V/cell, 20 °C", "Marathon M-FT"
                        evidence_scope = "exact_model_plus_documented_v0_variant" if is_v0 else "exact_model"
                    else:
                        partition, reason = "hold_offered_capacity_conflict", f"offered {offered_capacity:g}Ah differs from official {capacity:g}/{alternate:g}Ah"
                elif model == "M12V180FT":
                    source_key, partition, reason = "marathon_mft_archive", "hold_v0_suffix_not_proven_by_exact_source", "archive proves M12V180FT, but not the offered V0 variant in the same exact source"
                elif model in {"M12V40", "M12V40F", "M12V70", "M12V90", "M12V90F"}:
                    source_key, partition, reason = "marathon_m_archive", "hold_capacity_or_v0_variant_not_proven", "archive proves the base M(F) family but not a strict nominal-capacity plus offered-V0 record"

        source = SOURCES[source_key] if source_key else None
        if decision == "PASS":
            assert source and voltage is not None and capacity is not None
            base, _ = base_model(mpn)
            search_model = re.sub(r"\sF2$", "", mpn, flags=re.I) if manufacturer == "CSB" else base
            if not re.search(rf"(?<![A-Z0-9]){re.escape(search_model)}(?![A-Z0-9])", texts[source_key], re.I):
                raise SystemExit(f"exact model token absent: {manufacturer} {mpn}")
            snapshot = "docs/audits/sources/wave242-leoch-marathon-csb/" + source["file"]
            identities.append({
                "external_id": old["external_id"], "current_name": old["name"], "manufacturer": manufacturer,
                "mpn": mpn, "source_url": source["url"], "source_kind": "official_manufacturer_catalogue",
                "source_publisher": source["publisher"], "checked_at": CHECKED_AT,
                "product_type": "stationary VRLA AGM battery", "source_snapshot_path": "../audits/" + snapshot.removeprefix("docs/audits/"),
                "source_snapshot_sha256": source["sha256"],
            })
            descriptions.append(description(row, manufacturer, mpn, source, voltage, capacity, capacity_basis, series, evidence_scope))

        ledger.append({
            "external_id": old["external_id"], "name": old["name"], "manufacturer_candidate": manufacturer,
            "mpn_candidate": mpn, "normalized_mpn": old["normalized_mpn"], "offered_capacity_ah": f"{offered_capacity:g}",
            "decision": decision, "partition": partition, "source_url": source["url"] if source else "",
            "source_snapshot_path": ("docs/audits/sources/wave242-leoch-marathon-csb/" + source["file"]) if source else "",
            "source_snapshot_sha256": source["sha256"] if source else "", "source_page": source_page,
            "voltage_check": f"official {voltage:g}V" if voltage is not None else "not_proven",
            "capacity_check": f"official {capacity:g}Ah; offered {offered_capacity:g}Ah" if capacity is not None else "not_proven",
            "terminal_check": terminal_check, "suffix_check": suffix_check, "hold_reason": reason,
            "safe_to_apply": "true" if decision == "PASS" else "false",
        })

    if len(ledger) != 131 or len(identities) != len(descriptions):
        raise SystemExit("Wave242 output cardinality failure")
    if len({row["external_id"] for row in identities}) != len(identities):
        raise SystemExit("identity manifest repeats an external ID")
    if len({(row["manufacturer"], normalized(row["mpn"])) for row in identities}) != len(identities):
        raise SystemExit("identity manifest repeats a normalized manufacturer+MPN")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)
    write_json(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "purpose": "Wave242 strict manufacturer-primary identities", "products": identities})
    write_json(DESCRIPTIONS, {"schema_version": 1, "purpose": "Wave242 strict manufacturer-primary source-backed descriptions", "locale": "ru-BY", "products": descriptions})
    counts = Counter(row["decision"] for row in ledger)
    partitions = Counter(row["partition"] for row in ledger)
    write_json(SUMMARY, {
        "schema_version": 1, "batch": "wave242_leoch_marathon_csb", "checked_at": CHECKED_AT,
        "scope": {"rows": len(ledger), "manufacturer_counts": dict(sorted(Counter(row["manufacturer_candidate"] for row in ledger).items()))},
        "no_repeat": {"baseline": PRIOR.relative_to(ROOT).as_posix(), "baseline_sha256": INPUT_PINS["prior"], "rule": "only newly pinned official manufacturer catalogues/specifications were evaluated"},
        "sources": [{"path": (SOURCE_DIR / value["file"]).relative_to(ROOT).as_posix(), **value} for value in SOURCES.values()],
        "decision_counts": dict(sorted(counts.items())), "partition_counts": dict(sorted(partitions.items())),
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "identity_manifest": {"path": IDENTITIES.relative_to(ROOT).as_posix(), "sha256": sha256(IDENTITIES), "rows": len(identities)},
        "description_manifest": {"path": DESCRIPTIONS.relative_to(ROOT).as_posix(), "sha256": sha256(DESCRIPTIONS), "rows": len(descriptions)},
        "policy": {"exact_primary_source_required": True, "offered_suffix_checked": True, "voltage_and_capacity_checked": True,
                   "normalized_mpn_collision_checked": True, "database_mutations": 0, "apply_commands_run": 0},
    })
    print(json.dumps({"rows": len(ledger), "pass": counts["PASS"], "hold": counts["HOLD"], "partitions": dict(sorted(partitions.items()))}))


if __name__ == "__main__":
    main()
