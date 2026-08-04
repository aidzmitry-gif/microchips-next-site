#!/usr/bin/env python3
"""Build Wave213-A's fail-closed medical replacement-battery triage.

The legacy title identifies a *device* and sometimes a battery-pack part
number.  It does not establish that a particular replacement pack is an OEM
sellable battery.  Consequently this builder never promotes a title-only
match: all 274 records remain held until SHA-pinned first-party evidence
proves the exact battery pack.  The PostgreSQL query is read-only.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-b2b-next-source-batch-wave212.csv"
PROCESSED = GEN / "rb-b2b-processed-register-wave212.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
OUTPUT = GEN / "wave213a-medical-replacement-triage.csv"
SUMMARY = GEN / "wave213a-medical-replacement-triage.summary.json"
LIVE = GEN / "wave213a-medical-replacement-live-identity-collisions.json"
APPLY0 = GEN / "wave213a-medical-replacement-laravel-apply0.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave213a-medical-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-wave213a-medical-replacement-triage.md"

INPUT_SHA256 = "b251d7a6d28ca4b6c1b51f3bfec3bae840e8e688a11d6515409a905602e608a1"
TARGET_ROWS = 274
CHECKED_AT = "2026-07-29"

FIELDS = [
    "product_external_id", "name", "category_external_id", "device_oem", "device_model",
    "device_family", "battery_pack_form", "battery_pack_oem_part_number", "voltage_v",
    "capacity_mah", "normalized_device_variant_key", "in_wave_variant_group_size",
    "in_wave_variant_external_ids", "full_registry_exact_name_collision_count",
    "full_registry_exact_name_registry_ids", "full_registry_device_pack_collision_count",
    "full_registry_device_pack_registry_ids", "live_db_collision_count",
    "live_db_collision_external_ids", "source_route", "source_evidence_requirement",
    "hold_reason", "safe_to_apply",
]

# Longest names first prevents ``GE`` swallowing ``GE Healthcare``.  These are
# device OEM labels, not asserted battery-pack manufacturers.
OEM_NAMES = sorted((
    "Covidien Kendall", "Fukuda Denshi", "GE Healthcare", "Hellige", "HillRom",
    "Medical Econet", "Nihon Kohden", "Philips Respironics", "Physio-Control",
    "Spectra Precision", "Thermo Scientific", "Welch-Allyn", "Welch Allyn",
    "CU Medical", "Dentsply Maillefer", "Diversified Medical", "Eppendorf",
    "Fresenius", "Grason", "Huntleigh", "Karl Storz", "Mindray", "Nellcor",
    "Otometrics", "Puritan Bennett", "ResMed", "Schiller", "SonoSite", "Terumo",
    "Verathon", "WEINMANN", "ZOLL", "Contec", "Cortex", "Cosmed", "Creative",
    "Datascope", "Datex", "DIXION", "Dongjiang", "Drager", "EDAN", "Eschenbach",
    "Finnpipette", "Fukuda", "General", "GE", "Hamilton", "Heine", "Hitachi",
    "Honda", "Horron", "Huaxi", "iHealth", "Innomed", "Invivo", "Iris", "JMS",
    "Jumper", "Kenz", "LikoGuard", "Maquet", "Marquette", "Masimo", "Medcaptain",
    "Medela", "Mediaid", "Medsonic", "Medtronic", "Mekics", "Metrax", "Microtac",
    "Million", "Natus", "Neusoft", "Newport", "Nikkiso", "Nonin", "Nova", "Ohmeda",
    "Omron", "Optomed", "OSEN", "Palco", "Philips", "Pixium", "Q Core", "Rainin",
    "Reichert", "Righton", "Shenke", "Siemens", "Smiths", "Soehnle", "Solaris",
    "SpectraScan", "Spring", "Suzuken", "Theradome", "Trismed", "Vocera", "Zimmer",
    "Zondan", "SaverOne", "Sonnenschein", "Toitu", "VocaSTIM",
), key=len, reverse=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").upper()
    # The legacy export contains occasional visually equivalent Cyrillic
    # letters.  ProductIdentity is deliberately ASCII-normalized too.
    value = value.translate(str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX"))
    return re.sub(r"[^A-Z0-9]+", "", value)


def title_after_for(name: str) -> str:
    # Two legacy grammars occur: ``Аккумулятор для …`` and
    # ``Батарея дефибриллятора для …``.  The preposition is the boundary;
    # words before it describe the battery, not the device OEM.
    match = re.search(r"\sдля\s+(.+)$", name, re.I)
    return match.group(1).strip() if match else ""


def title_device_and_tail(name: str) -> tuple[str, str, str]:
    body = title_after_for(name)
    for oem in OEM_NAMES:
        if body.casefold().startswith(oem.casefold()):
            tail = body[len(oem):].strip()
            return oem, tail, body
    token, _, tail = body.partition(" ")
    return token, tail.strip(), body


def technical_values(text: str) -> tuple[str, str]:
    capacity = re.search(r"\b(\d+(?:[.,]\d+)?)\s*mAh\b", text, re.I)
    voltage = re.search(r"\b(\d+(?:[.,]\d+)?)\s*V\b", text, re.I)
    return (voltage.group(1).replace(",", ".") if voltage else "", capacity.group(1).replace(",", ".") if capacity else "")


def pack_part_number(name: str) -> str:
    """Return only an explicit non-specification parenthesized pack code."""
    for group in re.findall(r"\(([^()]*)\)", name):
        value = group.strip()
        if re.search(r"\b(?:mAh|V)\b", value, re.I):
            continue
        if re.search(r"[A-Za-zА-Яа-я]", value) and re.search(r"\d", value):
            return value
    return ""


def device_model(tail: str) -> str:
    # Strip technical tail only; preserve the exact device family/model list.
    text = re.sub(r"\s*\([^()]*?(?:mAh|V)[^()]*\)", "", tail, flags=re.I)
    text = re.sub(r"\s+\d+(?:[.,]\d+)?\s*mAh\b.*$", "", text, flags=re.I)
    return text.strip(" ,")


def pack_form(part_number: str, voltage: str, capacity: str) -> str:
    if re.search(r"\b\d+S\d+P\b", part_number, re.I):
        return "lithium_battery_pack_series_parallel"
    if part_number:
        return "replacement_battery_pack_with_oem_part_number"
    if voltage and capacity:
        return "replacement_battery_pack_voltage_capacity_declared"
    if capacity:
        return "replacement_battery_pack_capacity_declared"
    return "replacement_battery_pack_technical_data_missing"


def family(model: str) -> str:
    text = model.casefold()
    rules = (
        (r"defi|defibr|aed|heartstart|lifepak|forerunner|primedic", "defibrillator"),
        (r"ventil|carina|oxylog|trilogy|elisee|stellar|servo|v60|cough", "ventilator_respiratory"),
        (r"ecg|ekg|cardio|cardisuny|cardipia|pagewriter|mac\b", "electrocardiograph"),
        (r"infusion|injectomat|feeding pump|applix|sapphire|te-", "infusion_or_feeding_pump"),
        (r"ultraschall|echograph|ultrasound|logiq|vscan|cx50|cx30", "ultrasound_imaging"),
        (r"oximeter|oxymetre|pulse|trusat|pox", "pulse_oximeter"),
        (r"monitor|intellivue|accutorr|ben[e]?view|dash|vista|viridia|connex|vital signs|im\d|ipm", "patient_monitor"),
        (r"pipet|easypet|multipette|xplorer|finnpipette|rainin", "laboratory_pipette"),
        (r"lift|lifter|leve malade|viking", "patient_lift"),
        (r"dental|propex|smartlite|x-smart", "dental_instrument"),
        (r"tonometer|retinomax|ophthalmo|smartscope", "ophthalmic_or_optical_device"),
    )
    return next((value for pattern, value in rules if re.search(pattern, text, re.I)), "medical_device_other")


def device_pack_key(oem: str, model: str, part: str, voltage: str, capacity: str) -> str:
    # Keep declared technical values even with a pack code: the legacy export
    # contains same-code 2600/3400 mAh alternatives.  Those are a device
    # variant group, not an exact duplicate/collision assertion.
    pack = "|".join((normalize(part), normalize(voltage), normalize(capacity))) if part else f"{normalize(voltage)}V{normalize(capacity)}MAH"
    return "|".join((normalize(oem), normalize(model), pack))


def live_products() -> list[dict[str, str]]:
    php = (
        "$r=app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer',"
        "'sku_normalized','mpn_normalized','status')->orderBy('external_id')->get();"
        "echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )
    encoded = base64.b64encode(php.encode()).decode()
    command = ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));" ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode or not result.stdout.strip().startswith("["):
        raise SystemExit(f"read-only live PostgreSQL query failed: {result.stderr.strip() or result.stdout.strip()}")
    products = json.loads(result.stdout)
    if len({str(row["external_id"]) for row in products}) != len(products):
        raise SystemExit("live PostgreSQL repeats external IDs")
    return products


def main() -> None:
    if sha256(INPUT) != INPUT_SHA256:
        raise SystemExit("Wave213-A input pin drift: regenerate and deliberately re-pin before triage")
    source, processed, registry = read_csv(INPUT), read_csv(PROCESSED), read_csv(REGISTRY)
    selected = [row for row in source if row["manufacturer_cluster"] == "unresolved_replacement"]
    ids = [row["product_external_id"] for row in selected]
    if len(selected) != TARGET_ROWS or len(ids) != len(set(ids)):
        raise SystemExit("Wave213-A must select exactly 274 unique unresolved_replacement records")
    if any(row["category_external_id"] != "seo:replacement-medical" for row in selected):
        raise SystemExit("Wave213-A medical B2B category invariant failed")
    processed_ids = {row["product_external_id"] for row in processed}
    overlap = sorted(set(ids) & processed_ids)
    if overlap:
        raise SystemExit(f"Wave213-A processed-register overlap: {overlap[:5]}")

    prepared: list[dict[str, str]] = []
    for row in selected:
        oem, tail, _ = title_device_and_tail(row["name"])
        voltage, capacity = technical_values(row["name"])
        part = pack_part_number(row["name"])
        model = device_model(tail)
        if not oem or not model:
            raise SystemExit(f"unparseable exact device OEM/model: {row['product_external_id']}")
        key = device_pack_key(oem, model, part, voltage, capacity)
        device_key = f"{normalize(oem)}|{normalize(model)}"
        prepared.append({**row, "device_oem": oem, "device_model": model, "voltage": voltage, "capacity": capacity, "part": part, "key": key, "device_key": device_key})

    group_members: dict[str, list[str]] = defaultdict(list)
    for row in prepared:
        group_members[row["device_key"]].append(row["product_external_id"])
    registry_metadata = []
    registry_names: dict[str, set[str]] = defaultdict(set)
    for row in registry:
        registry_names[normalize(row.get("name", ""))].add(row["registry_id"])
        try:
            oem, tail, _ = title_device_and_tail(row.get("name", ""))
            voltage, capacity = technical_values(row.get("name", ""))
            part = pack_part_number(row.get("name", ""))
            model = device_model(tail)
            if oem and model:
                registry_metadata.append((row["registry_id"], device_pack_key(oem, model, part, voltage, capacity)))
        except (KeyError, TypeError):
            continue

    live = live_products()
    live_by_id = {str(row["external_id"]): row for row in live}
    missing = sorted(set(ids) - set(live_by_id))
    if missing:
        raise SystemExit(f"Wave213-A candidates missing from live PostgreSQL: {missing[:5]}")
    live_keys: dict[str, list[str]] = defaultdict(list)
    live_names: dict[str, list[str]] = defaultdict(list)
    for product in live:
        oem, tail, _ = title_device_and_tail(str(product.get("name") or ""))
        if not oem or not tail:
            continue
        voltage, capacity = technical_values(str(product.get("name") or ""))
        part = pack_part_number(str(product.get("name") or ""))
        model = device_model(tail)
        if model:
            live_keys[device_pack_key(oem, model, part, voltage, capacity)].append(str(product["external_id"]))
            live_names[normalize(str(product.get("name") or ""))].append(str(product["external_id"]))

    output: list[dict[str, str]] = []
    live_collision_payload = []
    for row in prepared:
        in_wave = sorted(group_members[row["device_key"]])
        exact_registry = sorted(registry_names[normalize(row["name"])] - {row["product_external_id"]})
        device_registry = sorted({registry_id for registry_id, key in registry_metadata if key == row["key"] and registry_id != row["product_external_id"]})
        live_peers = sorted(set(live_keys.get(row["key"], []) + live_names.get(normalize(row["name"]), [])) - {row["product_external_id"]})
        if live_peers:
            live_collision_payload.append({"candidate_external_id": row["product_external_id"], "conflicting_external_ids": live_peers})
        source_route = "battery_pack_oem_exact_part_number_then_device_oem_accessory_manual" if row["part"] else "device_oem_manual_or_service_document_then_battery_pack_label"
        requirement = "SHA-pinned first-party source must name the exact sellable battery pack and the device compatibility; device compatibility alone is insufficient."
        holds = ["medical_b2b_retained", "exact_sellable_battery_pack_not_yet_proven", "live_db_read_only_apply0"]
        if len(in_wave) > 1:
            holds.append("in_wave_device_variant_group")
        if exact_registry or device_registry:
            holds.append("full_registry_collision_candidate")
        if live_peers:
            holds.append("live_db_collision_candidate")
        output.append({
            "product_external_id": row["product_external_id"], "name": row["name"], "category_external_id": row["category_external_id"],
            "device_oem": row["device_oem"], "device_model": row["device_model"], "device_family": family(row["device_model"]),
            "battery_pack_form": pack_form(row["part"], row["voltage"], row["capacity"]), "battery_pack_oem_part_number": row["part"],
            "voltage_v": row["voltage"], "capacity_mah": row["capacity"], "normalized_device_variant_key": row["key"],
            "in_wave_variant_group_size": str(len(in_wave)), "in_wave_variant_external_ids": "|".join(in_wave),
            "full_registry_exact_name_collision_count": str(len(exact_registry)), "full_registry_exact_name_registry_ids": "|".join(exact_registry),
            "full_registry_device_pack_collision_count": str(len(device_registry)), "full_registry_device_pack_registry_ids": "|".join(device_registry),
            "live_db_collision_count": str(len(live_peers)), "live_db_collision_external_ids": "|".join(live_peers),
            "source_route": source_route, "source_evidence_requirement": requirement,
            "hold_reason": "|".join(holds), "safe_to_apply": "false",
        })

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(output)
    live_payload = {
        "schema_version": 1, "checked_at": CHECKED_AT, "mode": "read_only", "query_exit_code": 0,
        "database": "current Docker PostgreSQL", "candidate_rows_checked": len(output),
        "candidate_external_ids": ids, "query_rule": "same normalized full title or same parsed device OEM/model plus pack part number or voltage/capacity",
        "collisions": live_collision_payload, "database_mutations": 0, "apply_records": 0,
    }
    LIVE.write_text(json.dumps(live_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # The command rejects an empty manifest.  Keeping the empty result explicit
    # is safer than manufacturing an MPN from a device compatibility title.
    manifest = {"schema_version": 1, "site_key": "microchips-by", "products": [], "policy": "No exact-safe records: first-party source must prove the sellable battery pack, not device compatibility alone."}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apply0 = {
        "schema_version": 1, "mode": "not_invoked_empty_exact_safe_manifest", "records": 0,
        "database_mutations": 0, "commercial_fields_changed": 0, "publication_fields_changed": 0,
        "reason": "catalog:apply-verified-oem-identities rejects an empty manifest; no source-proven sellable pack is eligible.",
    }
    APPLY0.write_text(json.dumps(apply0, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    families = Counter(row["device_family"] for row in output)
    routes = Counter(row["source_route"] for row in output)
    summary = {
        "schema_version": 1, "wave": "wave213a_medical_replacement", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(source)},
        "target": {"rows": len(output), "unique_external_ids": len(set(ids)), "manufacturer_cluster": "unresolved_replacement", "medical_b2b_rows": len(output)},
        "processed_register": {"path": PROCESSED.relative_to(ROOT).as_posix(), "rows": len(processed), "overlap_rows": len(overlap)},
        "device_extraction": {"device_oems": len({row['device_oem'] for row in output}), "device_families": dict(sorted(families.items())), "rows_with_explicit_pack_oem_part_number": sum(bool(row['battery_pack_oem_part_number']) for row in output)},
        "in_wave_variant_groups": {"groups_with_variants": sum(len(value) > 1 for value in group_members.values()), "rows_in_variant_groups": sum(len(value) for value in group_members.values() if len(value) > 1)},
        "full_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "rows": len(registry), "exact_name_collision_rows": sum(row['full_registry_exact_name_collision_count'] != '0' for row in output), "device_pack_collision_rows": sum(row['full_registry_device_pack_collision_count'] != '0' for row in output)},
        "live_db": {"path": LIVE.relative_to(ROOT).as_posix(), "rows_checked": len(output), "collision_rows": len(live_collision_payload), "database_mutations": 0, "apply_records": 0},
        "apply0_receipt": {"path": APPLY0.relative_to(ROOT).as_posix(), "sha256": sha256(APPLY0), "records": 0, "database_mutations": 0},
        "source_routes": dict(sorted(routes.items())),
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": 0, "exact_safe_only": True},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)},
        "automatic_web_requests": 0, "database_queries": 1, "database_mutations": 0, "safe_to_apply_records": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave213-A medical replacement-battery triage\n\n"
        "Wave213-A deterministically processes all 274 `unresolved_replacement` rows from Wave212. All remain in the B2B medical replacement category; none is treated as automotive or electronic-component scope. The triage extracts a device OEM/model, device family, battery-pack form, explicit pack part number where present, voltage and capacity declared by the legacy title.\n\n"
        "It reports device-family variant groups plus exact-name and parsed device/pack collision candidates in the full canonical registry and current PostgreSQL. PostgreSQL is read only and `apply_records=0`. No web request was made.\n\n"
        "The exact-safe manifest is deliberately empty. A medical-device manual that merely says a pack is compatible cannot establish a product identity. Promotion requires a SHA-pinned first-party device OEM accessory/service manual or battery-pack OEM source that explicitly proves the exact sellable pack and its device compatibility.\n",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(output), "families": len(families), "live_collision_rows": len(live_collision_payload), "safe_to_apply": 0, "db_apply": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
