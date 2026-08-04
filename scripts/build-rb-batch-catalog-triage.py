#!/usr/bin/env python3
"""Build a fail-closed batch triage for the current RB enrichment queue.

The script never mutates the database and never promotes extracted identity to
canonical product fields.  Its job is to collapse repetitive research into
model clusters and to produce auditable candidate manifests.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "APC": ("APC by Schneider Electric", "Schneider Electric APC", "APC"),
    "B.B. Battery": ("B.B. Battery", "BB Battery"),
    "BAE": ("BAE Batterien", "BAE"),
    "CSB": ("CSB Battery", "CSB"),
    "Delta": ("Delta Battery", "Delta"),
    "Energizer": ("Energizer",),
    "Fanso": ("Fanso",),
    "Fiamm": ("Fiamm",),
    "Hiden": ("Hiden Control", "Hiden"),
    "Hoppecke": ("Hoppecke",),
    "Kijo": ("Kijo",),
    "Leoch": ("Leoch",),
    "LiitoKala": ("LiitoKala",),
    "Panasonic": ("Panasonic",),
    "PKCELL": ("PKCELL",),
    "Robiton": ("Robiton",),
    "Saft": ("Saft",),
    "Sonnenschein": ("Sonnenschein",),
    "Tekcell": ("Tekcell",),
    "Ventura": ("Ventura",),
    "Xeno": ("Xeno",),
}

OUT_OF_SCOPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("electronic_component", re.compile(r"\b(?:резистор|конденсатор|транзистор|микросхем[аы]|диод|тиристор|оптопар[аы]|стабилитрон)\b", re.I)),
    ("electronic_module", re.compile(r"\b(?:трансивер|дисплей|индикатор|датчик|микроконтроллер|модуль\s+(?:bluetooth|wi-?fi|gps))\b", re.I)),
    ("installation_part", re.compile(r"\b(?:разъ[её]м|клеммник|предохранитель|держатель\s+предохранителя|кабельный\s+наконечник)\b", re.I)),
    ("non_product_material", re.compile(r"\b(?:смазка|герметик|клей|припой|флюс)\b", re.I)),
)

# A connector, lead or terminal can be part of a battery assembly. Those
# variants are commercially meaningful and must not be rejected merely because
# the name also contains an installation-part word.
POWER_SOURCE_PATTERN = re.compile(
    r"\b(?:аккумулятор|акб|батаре(?:я|йка|и)|элемент\s+питания|CR\d{4,5}|ER\d{4,5}|LS\s*\d{4,5})\b",
    re.I,
)

TECH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("LiFePO4", re.compile(r"\b(?:lifepo4|lfp)\b", re.I)),
    ("Li-ion", re.compile(r"\bli[ -]?ion\b", re.I)),
    ("LiPo", re.compile(r"\blipo\b", re.I)),
    ("NiMH", re.compile(r"\bnimh\b", re.I)),
    ("NiCd", re.compile(r"\bnicd\b", re.I)),
    ("LTO", re.compile(r"\blto\b", re.I)),
    ("OPzS", re.compile(r"\bopzs\b", re.I)),
    ("OPzV", re.compile(r"\bopzv\b", re.I)),
    ("AGM", re.compile(r"\bagm\b", re.I)),
    ("GEL", re.compile(r"\bgel\b", re.I)),
    ("VRLA", re.compile(r"\bvrla\b", re.I)),
)

MODEL_STOPWORDS = {
    "AGM", "GEL", "VRLA", "LFP", "LIFEPO4", "LION", "LIPO", "NIMH", "NICD",
    "OPZS", "OPZV", "UPS", "ИБП", "АКБ", "BATTERY", "BATTERIEN", "CONTROL",
}

GENERIC_MODEL_WORDS = re.compile(
    r"(?:КОМПЛЕКТ|ПИТАНИЯ|УСТРОЙСТВО|АККУМУЛЯТОР|БАТАРЕЙК|БАТАРЕЯ|ЭЛЕМЕНТ|ЛИТИЕВ)",
    re.I,
)

VARIANT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("connector_jst", re.compile(r"\bJST(?:-[A-Z0-9]+)?\b", re.I)),
    ("connector_molex", re.compile(r"\bMOLEX(?:\s+[A-Z0-9-]+)?\b", re.I)),
    ("connector_ehr", re.compile(r"\bEHR-?\d+\b", re.I)),
    ("connector_phr", re.compile(r"\bPHR-?\d+\b", re.I)),
    ("connector_xhp", re.compile(r"\bXHP-?\d+\b", re.I)),
    ("connector_sm", re.compile(r"\bSM-?\d+P\b", re.I)),
    ("terminal_pf", re.compile(r"\b\dPF\b", re.I)),
    ("terminal_cnr", re.compile(r"\bCNR\b", re.I)),
    ("terminal_cna", re.compile(r"\bCNA\b", re.I)),
    ("terminal_fle", re.compile(r"\bFLE\b", re.I)),
    ("terminal_solder", re.compile(r"(?:под\s+пайку|вывод\w*|провод\w*|коннектор\w*|разъ[её]м\w*)", re.I)),
    ("feature_display", re.compile(r"\bдиспле\w*\b", re.I)),
    ("suffix_pro", re.compile(r"\bPRO\b", re.I)),
    ("suffix_c3", re.compile(r"\bC3\b", re.I)),
)

ORIGIN_PATTERN = re.compile(
    r"\b(Китай|Франци[яи]|Сингапур|Литв[аы]|Россия|Гонконг|Соединенн\w+\s+Королевств\w+|Азербайджан)\b",
    re.I,
)


@dataclass(frozen=True)
class IdentityCandidate:
    manufacturer: str
    model_raw: str
    model_key: str
    source: str


def nfkc(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip()


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", nfkc(value))


def model_key(value: str) -> str:
    """Normalize harmless separators but preserve suffix characters and plus."""
    value = nfkc(value).upper().replace("Ё", "Е")
    return re.sub(r"[\s._/\\-]+", "", value)


def detect_brand(name: str, explicit: str = "") -> tuple[str, str]:
    explicit_norm = compact(explicit)
    if explicit_norm:
        for canonical, aliases in BRAND_ALIASES.items():
            if explicit_norm.casefold() in {alias.casefold() for alias in aliases}:
                return canonical, "explicit_field"
        return explicit_norm, "explicit_field_unmapped"

    haystack = compact(name)
    matches: list[tuple[int, str]] = []
    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", haystack, re.I):
                matches.append((len(alias), canonical))
    if not matches:
        return "", "missing"
    matches.sort(reverse=True)
    return matches[0][1], "name_alias"


def is_model_token(value: str) -> bool:
    key = model_key(value)
    if len(key) < 4 or key in MODEL_STOPWORDS:
        return False
    if not any(ch.isalpha() for ch in key) or not any(ch.isdigit() for ch in key):
        return False
    if re.fullmatch(r"\d+(?:[.,]\d+)?(?:V|В|AH|MAH|W|KW|ВА|ВТ)", key, re.I):
        return False
    return True


def extract_model_from_name(name: str, manufacturer: str) -> str:
    value = compact(name)
    aliases = BRAND_ALIASES.get(manufacturer, (manufacturer,))
    for alias in sorted(aliases, key=len, reverse=True):
        value = re.sub(rf"(?<![\w]){re.escape(alias)}(?![\w])", " ", value, flags=re.I)

    # Keep meaningful punctuation and suffixes.  Adjacent alpha + numeric
    # tokens cover forms such as "BPS 26-12" without inferring from units.
    tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:[+./-][A-Za-zА-Яа-яЁё0-9]+)*", value)
    candidates: list[tuple[str, int]] = []
    for index, token in enumerate(tokens):
        if is_model_token(token):
            candidates.append((token, index))
            continue
        if token.isalpha() and index + 1 < len(tokens):
            joined = f"{token} {tokens[index + 1]}"
            if is_model_token(joined) and re.search(r"\d", tokens[index + 1]):
                candidates.append((joined, index))
    if not candidates:
        return ""
    candidates.sort(
        key=lambda item: (
            0 if GENERIC_MODEL_WORDS.search(item[0]) else 1,
            1 if re.search(r"[A-Za-z]", item[0]) else 0,
            1 if re.match(r"^[A-Za-zА-Яа-яЁё]{1,5}[ -]?\d", item[0]) else 0,
            -item[1],
            len(model_key(item[0])),
        ),
        reverse=True,
    )
    return candidates[0][0]


def extract_identity(row: dict[str, str]) -> IdentityCandidate | None:
    manufacturer, brand_source = detect_brand(row.get("name", ""), row.get("manufacturer", ""))
    if not manufacturer:
        return None
    explicit_mpn = compact(row.get("mpn", ""))
    if explicit_mpn and is_model_token(explicit_mpn):
        return IdentityCandidate(manufacturer, explicit_mpn, model_key(explicit_mpn), f"mpn_field+{brand_source}")
    extracted = extract_model_from_name(row.get("name", ""), manufacturer)
    if not extracted:
        return None
    return IdentityCandidate(manufacturer, extracted, model_key(extracted), f"name_candidate+{brand_source}")


def explicit_facts(name: str) -> dict[str, str]:
    value = compact(name)
    voltages = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:V|В)(?![A-Za-zА-Яа-я])", value, re.I)
    capacities = re.findall(r"(?<!\d)(\d+(?:[.,]\d+)?)\s*(?:mAh|мА[·.]?ч|Ah|А[·.]?ч)(?![A-Za-zА-Яа-я])", value, re.I)
    technologies = [label for label, pattern in TECH_PATTERNS if pattern.search(value)]
    return {
        "voltage_candidates": "|".join(item.replace(",", ".") for item in voltages),
        "capacity_candidates": "|".join(item.replace(",", ".") for item in capacities),
        "technology_candidates": "|".join(technologies),
        "variant_candidates": "|".join(sorted({label for label, pattern in VARIANT_PATTERNS if pattern.search(value)})),
        "package_count_candidates": "|".join(re.findall(r"(?<!\d)(\d+)\s*(?:шт|pcs)(?!\w)", value, re.I)),
        "origin_candidates": "|".join(sorted({match.casefold() for match in ORIGIN_PATTERN.findall(value)})),
    }


def out_of_scope_reason(name: str) -> str:
    for reason, pattern in OUT_OF_SCOPE_PATTERNS:
        if pattern.search(name):
            if reason == "installation_part" and POWER_SOURCE_PATTERN.search(name):
                continue
            return reason
    return ""


def bool_value(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def survivor_rank(row: dict[str, str]) -> tuple[int, int, int, int, str]:
    return (
        1 if row.get("identity_source", "").startswith("mpn_field") else 0,
        1 if bool_value(row.get("has_applied_description", "")) else 0,
        1 if bool_value(row.get("is_published", "")) else 0,
        int(row.get("identity_fields_present", "0") or 0),
        # Reversed later only as a stable final tiebreaker.
        row.get("product_external_id", ""),
    )


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_known_hold_cluster_ids(path: Path | None) -> set[str]:
    """Load explicit prior hold decisions without guessing their meaning.

    A malformed registry must stop the run before candidate files are written.
    This is deliberately stricter than silently treating an unknown decision as
    a hold: otherwise a typo could hide a cluster from the research queue.
    """
    if path is None:
        return set()
    if not path.is_file():
        raise ValueError(f"Prior decision registry does not exist: {path}")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        required = {"cluster_id", "decision"}
        missing = required - set(fieldnames)
        if missing:
            raise ValueError(
                "Prior decision registry is missing required column(s): "
                + ", ".join(sorted(missing))
            )

        known_holds: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            cluster_id = (row.get("cluster_id") or "").strip()
            decision = (row.get("decision") or "").strip().casefold()
            if not cluster_id or ":" not in cluster_id:
                raise ValueError(
                    f"Prior decision registry has malformed cluster_id at line {line_number}"
                )
            if not decision:
                raise ValueError(
                    f"Prior decision registry has a missing decision at line {line_number}"
                )
            if decision != "hold":
                raise ValueError(
                    f"Prior decision registry has unsupported decision '{decision}' at line {line_number}"
                )
            if cluster_id in known_holds:
                raise ValueError(
                    f"Prior decision registry duplicates cluster_id '{cluster_id}' at line {line_number}"
                )
            known_holds.add(cluster_id)
    return known_holds


def build(
    queue_path: Path,
    out_dir: Path,
    prefix: str,
    prior_decisions_path: Path | None = None,
) -> dict[str, object]:
    known_hold_cluster_ids = load_known_hold_cluster_ids(prior_decisions_path)
    with queue_path.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    triage_rows: list[dict[str, object]] = []
    identity_groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    category_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for source in source_rows:
        external_id = source.get("product_external_id", "").strip()
        if not external_id:
            raise ValueError("Queue contains a row without product_external_id")
        category_counts[source.get("category_external_id", "")] += 1
        reason = out_of_scope_reason(source.get("name", ""))
        identity = extract_identity(source)
        facts = explicit_facts(source.get("name", ""))
        if reason:
            status = "out_of_scope_candidate"
        elif identity and identity.source.startswith("mpn_field"):
            status = "identity_present_research_cluster"
        elif identity:
            status = "identity_candidate_needs_primary_source"
        else:
            status = "hold_missing_identity"

        row: dict[str, object] = {
            **source,
            "triage_status": status,
            "triage_reason": reason or ("" if identity else "manufacturer_or_stable_model_missing"),
            "manufacturer_candidate": identity.manufacturer if identity else "",
            "model_candidate": identity.model_raw if identity else "",
            "model_key": identity.model_key if identity else "",
            "identity_source": identity.source if identity else "",
            **facts,
            "safe_to_apply": "false",
        }
        status_counts[status] += 1
        triage_rows.append(row)
        if identity and not reason:
            identity_groups[(identity.manufacturer.casefold(), identity.model_key)].append(row)

    research_rows: list[dict[str, object]] = []
    suppressed_known_hold_clusters: set[str] = set()
    known_hold_member_rows: list[dict[str, object]] = []
    known_hold_member_external_ids: set[str] = set()
    known_hold_cluster_member_records = 0
    missing_identity_hold_records = 0
    duplicate_rows: list[dict[str, object]] = []

    def add_known_hold_member(
        member: dict[str, object],
        *,
        cluster_id: str,
        hold_source: str,
        hold_reason: str,
    ) -> None:
        external_id = str(member["product_external_id"])
        if external_id in known_hold_member_external_ids:
            raise ValueError(
                "A current research member belongs to more than one known hold source: "
                + external_id
            )
        known_hold_member_external_ids.add(external_id)
        known_hold_member_rows.append({
            "product_external_id": external_id,
            "cluster_id": cluster_id,
            "manufacturer_candidate": member["manufacturer_candidate"],
            "model_candidate": member["model_candidate"],
            "decision": "hold",
            "hold_source": hold_source,
            "hold_reason": hold_reason,
            "safe_to_apply": "false",
        })

    # A row without a manufacturer or stable model cannot enter primary-source
    # research at all. Keep it auditable as a hold instead of repeatedly
    # presenting it to the research queue.
    for member in triage_rows:
        if (
            member["triage_status"] == "hold_missing_identity"
            and member["triage_reason"] == "manufacturer_or_stable_model_missing"
        ):
            add_known_hold_member(
                member,
                cluster_id="",
                hold_source="missing_identity",
                hold_reason="manufacturer_or_stable_model_missing",
            )
            missing_identity_hold_records += 1
    for (manufacturer_key, normalized_model), members in sorted(identity_groups.items()):
        ordered = sorted(members, key=survivor_rank, reverse=True)
        survivor = ordered[0]
        cluster_id = f"{manufacturer_key}:{normalized_model}"
        research_members = [item for item in ordered if not bool_value(str(item.get("has_applied_description", "")))]
        if research_members and cluster_id not in known_hold_cluster_ids:
            research_representative = research_members[0]
            research_rows.append({
                "cluster_id": cluster_id,
                "manufacturer_candidate": research_representative["manufacturer_candidate"],
                "model_candidate": research_representative["model_candidate"],
                "member_count": len(research_members),
                "member_external_ids": "|".join(sorted(str(item["product_external_id"]) for item in research_members)),
                "representative_name": research_representative["name"],
                "identity_source": research_representative["identity_source"],
                "research_gate": "official_manufacturer_source_required",
                "safe_to_apply": "false",
            })
        elif research_members and cluster_id in known_hold_cluster_ids:
            suppressed_known_hold_clusters.add(cluster_id)
            for member in research_members:
                add_known_hold_member(
                    member,
                    cluster_id=cluster_id,
                    hold_source="prior_decision_cluster",
                    hold_reason="prior_registry_decision",
                )
                known_hold_cluster_member_records += 1
        if len(members) > 1:
            for duplicate in ordered[1:]:
                facts_match = all(
                    duplicate.get(field, "") == survivor.get(field, "") or not duplicate.get(field, "") or not survivor.get(field, "")
                    for field in ("voltage_candidates", "capacity_candidates", "technology_candidates")
                )
                variant_facts_match = all(
                    duplicate.get(field, "") == survivor.get(field, "")
                    for field in ("variant_candidates", "package_count_candidates", "origin_candidates")
                )
                exact_candidate = (
                    facts_match
                    and variant_facts_match
                    and str(survivor.get("identity_source", "")).startswith("mpn_field")
                    and str(duplicate.get("identity_source", "")).startswith("mpn_field")
                )
                duplicate_rows.append({
                    "cluster_id": cluster_id,
                    "survivor_external_id": survivor["product_external_id"],
                    "survivor_name": survivor["name"],
                    "duplicate_external_id": duplicate["product_external_id"],
                    "duplicate_name": duplicate["name"],
                    "explicit_facts_compatible": str(facts_match).lower(),
                    "variant_facts_compatible": str(variant_facts_match).lower(),
                    "decision": "exact_duplicate_candidate_needs_source" if exact_candidate else "variant_or_fact_conflict_hold",
                    "safe_to_apply": "false",
                })

    base_fields = list(source_rows[0].keys()) if source_rows else []
    extra_fields = [
        "triage_status", "triage_reason", "manufacturer_candidate", "model_candidate", "model_key",
        "identity_source", "voltage_candidates", "capacity_candidates", "technology_candidates",
        "variant_candidates", "package_count_candidates", "origin_candidates", "safe_to_apply",
    ]
    write_csv(out_dir / f"{prefix}-all.csv", triage_rows, base_fields + extra_fields)
    write_csv(out_dir / f"{prefix}-research-clusters.csv", research_rows, [
        "cluster_id", "manufacturer_candidate", "model_candidate", "member_count", "member_external_ids",
        "representative_name", "identity_source", "research_gate", "safe_to_apply",
    ])
    write_csv(out_dir / f"{prefix}-known-hold-members.csv", known_hold_member_rows, [
        "product_external_id", "cluster_id", "manufacturer_candidate", "model_candidate", "decision",
        "hold_source", "hold_reason", "safe_to_apply",
    ])
    write_csv(out_dir / f"{prefix}-duplicate-candidates.csv", duplicate_rows, [
        "cluster_id", "survivor_external_id", "survivor_name", "duplicate_external_id", "duplicate_name",
        "explicit_facts_compatible", "variant_facts_compatible", "decision", "safe_to_apply",
    ])
    out_scope = [row for row in triage_rows if row["triage_status"] == "out_of_scope_candidate"]
    write_csv(out_dir / f"{prefix}-out-of-scope-candidates.csv", out_scope, base_fields + extra_fields)

    summary: dict[str, object] = {
        "source": str(queue_path),
        "total_rows": len(source_rows),
        "unique_external_ids": len({row.get("product_external_id", "") for row in source_rows}),
        "status_counts": dict(sorted(status_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "unique_research_clusters": len(research_rows),
        "known_hold_clusters": len(suppressed_known_hold_clusters),
        "known_hold_cluster_member_records": known_hold_cluster_member_records,
        "missing_identity_hold_records": missing_identity_hold_records,
        "known_hold_member_records": len(known_hold_member_rows),
        "prior_decision_registry_known_holds": len(known_hold_cluster_ids),
        "prior_decision_registry": str(prior_decisions_path) if prior_decisions_path else None,
        "duplicate_candidate_pairs": len(duplicate_rows),
        "exact_duplicate_candidate_pairs": sum(row["decision"] == "exact_duplicate_candidate_needs_source" for row in duplicate_rows),
        "variant_or_fact_conflict_pairs": sum(row["decision"] == "variant_or_fact_conflict_hold" for row in duplicate_rows),
        "out_of_scope_candidates": len(out_scope),
        "automatic_database_mutations": 0,
        "safety_invariant": "candidate manifests only; official source and full-catalog gates remain required",
    }
    (out_dir / f"{prefix}-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--prefix", default="rb-batch-catalog-triage")
    parser.add_argument(
        "--prior-decisions",
        type=Path,
        help="CSV with exact cluster_id and decision=hold rows; suppresses only research candidates.",
    )
    args = parser.parse_args()
    summary = build(args.queue, args.out_dir, args.prefix, args.prior_decisions)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
