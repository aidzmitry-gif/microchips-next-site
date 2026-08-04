#!/usr/bin/env python3
"""Fail-closed product classification ledger for Wave217-A unresolved rows.

Only title-bounded candidate identities are produced here.  No unpinned page
or a lookalike model is treated as manufacturer-primary evidence, so the OEM
identity manifest remains empty unless a future exact source is acquired.
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
INPUT = GEN / "rb-b2b-next-source-batch-wave216.csv"
PROCESSED = GEN / "rb-b2b-processed-register-wave216.csv"
REGISTRY = GEN / "full-catalog-canonical-registry.csv"
OUTPUT = GEN / "rb-wave217a-unresolved-evidence.csv"
LIVE = GEN / "wave217a-unresolved-live-identity-collisions.json"
DRY = GEN / "wave217a-unresolved-laravel-dry-run.json"
SUMMARY = GEN / "rb-wave217a-unresolved-evidence.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave217a-unresolved-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave217a-unresolved-product-triage.md"
INPUT_SHA256 = "1819df3c10c10f66e79811264f1f31164d83e17a68e0b3f833d89e1d50aab881"
CHECKED_AT = "2026-07-29"

BRANDS = (
    "Rohde&Schwarz", "Black+Decker", "NICE-POWER", "Elektrostandard", "CrownMicro", "Camelion", "Milwaukee", "Интерскол", "Longwei", "Powerex", "Karcher", "Patriot", "Makita", "Metabo", "DeWalt", "Einhell", "Elitech", "Denzel", "Hitachi", "Ryobi", "Bosch", "WORX", "AEG", "DEKO", "INGCO", "Зубр", "Ansmann", "Nitecore", "Vanson", "Космос", "Фаzа", "CTEK", "Hi-Watt", "JazzWay", "Apeyron", "QJE", "Rigol", "W.E.P", "Hiden", "Kiper", "FSP", "nJoy", "IНЭЛТ", "Ирбис", "TOR", "XILIN", "Fogel Lift", "Sanyo", "OEM", "GP", "Kehua", "FSP",
)
PREFIXES = re.compile(r"^(?:Зарядное устройство|Блок питания|DC-DC преобразователь|Лабораторный источник питания|Источник бесперебойного питания|Аккумулятор|Комплект аккумуляторов|Штабелер самоходный|Ручная гидравлическая тележка \(рохля\))\s+", re.I)
MODEL_TOKEN = re.compile(r"(?<![A-ZА-Я0-9])([A-ZА-Я][A-ZА-Я0-9]*(?:[./+_-][A-ZА-Я0-9]+)+|[A-ZА-Я]{1,8}\d+[A-ZА-Я0-9./+_-]*)(?![A-ZА-Я0-9])", re.I)
SPACE_CODE = re.compile(r"(?<![A-ZА-Я0-9])([A-ZА-Я]{1,8}\s+\d{1,6}[A-ZА-Я0-9./+_-]*)(?![A-ZА-Я0-9])", re.I)
AUTOMOTIVE = re.compile(r"автомоб|авто[- ]?аккум|стартерн|мотоцикл|легков(?:ой|ых)|грузов", re.I)
ELECTRONICS = re.compile(r"микросхем|транзистор|резистор|конденсатор|диод|тиристор|симистор|микроконтроллер|полупроводник", re.I)
FIELDS = [
    "batch", "product_external_id", "name", "category_external_id", "factual_product_type", "manufacturer_candidate", "manufacturer_status", "model_candidate", "bounded_model_token", "model_status", "family_group", "family_status", "variant_group", "duplicate_group", "primary_manufacturer_source_route", "source_tier", "source_publisher", "source_url", "source_snapshot_path", "source_snapshot_sha256", "source_assertion", "partition", "conflict_reason", "registry_exact_title_duplicates", "registry_model_candidate_external_ids", "live_db_collision_external_ids", "live_current_manufacturer", "live_current_mpn", "safe_to_apply",
]


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))


CONFUSABLES = str.maketrans({"А":"A", "В":"B", "Е":"E", "К":"K", "М":"M", "Н":"H", "О":"O", "Р":"P", "С":"C", "Т":"T", "У":"Y", "Х":"X"})
def norm(value: str) -> str: return re.sub(r"[^A-Z0-9]+", "", unicodedata.normalize("NFKC", value or "").upper().translate(CONFUSABLES))


def product_type(row: dict[str, str]) -> str:
    name, category = row["name"], row["category_external_id"]
    if category == "seo:chargers": return "power_supply_adapter" if name.casefold().startswith("блок питания") else "battery_charger"
    if category == "seo:replacement-tools": return "power_tool_battery_charger_kit" if re.search(r"комплект|с зарядным устройством", name, re.I) else "power_tool_replacement_battery"
    if category == "seo:warehouse-equipment": return "manual_pallet_truck" if name.casefold().startswith("ручная гидравлическая") else "electric_warehouse_stacker"
    if category == "seo:batteries-traction": return "traction_battery"
    if category == "seo:power-systems":
        if name.casefold().startswith("dc-dc"): return "dc_dc_power_converter"
        if name.casefold().startswith("лабораторный"): return "laboratory_power_supply"
        if name.casefold().startswith("источник бесперебойного"): return "ups_system"
    raise ValueError(f"unexpected category/title: {category}: {name}")


def identity(name: str) -> tuple[str, str, str, str]:
    body = re.sub(r"\s*\([^)]*\)\s*$", "", PREFIXES.sub("", name)).strip()
    brand = next((item for item in BRANDS if re.match(re.escape(item) + r"(?:\s|$)", body, re.I)), "")
    model = body[len(brand):].strip() if brand else body
    candidates = [match.group(1) for pattern in (SPACE_CODE, MODEL_TOKEN) for match in pattern.finditer(model)]
    token = next((candidate for candidate in candidates if len(norm(candidate)) >= 3 and not re.fullmatch(r"\d+(?:\.\d+)?(?:V|AH|MAH|MM|К|КВТ)", candidate, re.I)), "")
    # Do not use a one-character marker (for example CTEK ``M``) as a
    # registry key: it would match most of the catalogue.  A compact title
    # phrase is still a bounded routing token, not a claimed MPN.
    if not token:
        token = "-".join(model.split()[:3]) if model else "unresolved-title-token"
    family = re.sub(r"\d.*$", "", token).rstrip("-_/.") or token
    return brand, model, token, family


def route(brand: str, kind: str) -> str:
    manufacturer = brand or "manufacturer_resolution"
    return f"{manufacturer}_first_party_{kind}_product_page_or_datasheet_required"


def live_products() -> list[dict]:
    php = "echo json_encode(app('db')->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized')->orderBy('external_id')->get(),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode or not run.stdout.strip().startswith("["): raise SystemExit(f"read-only live DB query failed: {run.stderr.strip() or run.stdout.strip()}")
    return json.loads(run.stdout)


def write_report(evidence: list[dict[str, str]], dry: dict) -> None:
    lines = [
        "# Wave217-A unresolved product triage", "",
        "Wave217-A classifies exactly 395 `unresolved_other` rows from Wave216 into saleable B2B product types and title-bounded model/family candidates.",
        "No unpinned or lookalike source is converted into an OEM identity; all records remain held for exact manufacturer-primary research.", "",
        "## Scope", "",
        f"- Product types: {dict(sorted(Counter(row['factual_product_type'] for row in evidence).items()))}",
        f"- Categories: {dict(sorted(Counter(row['category_external_id'] for row in evidence).items()))}",
        "- Automotive rows: 0; electronic-component rows: 0; processed3000 overlap: 0; prior-evidence overlap: 0.", "",
        "## Source and application policy", "",
        "- Title brand/model/family values are routing candidates only; a primary product page or datasheet must match the exact current ID, title and bounded model before an identity can be applied.",
        "- The exact-safe manifest is empty. Laravel was run without `--apply` and rejected its required non-empty product list; database mutations remain zero.",
        "- Registry and live-product collision guards are recorded for every candidate.", "",
        f"Laravel dry-run exit: {dry['exit_code']} (expected fail-closed); database mutations: 0.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    source = read_csv(INPUT)
    selected = [row for row in source if row.get("manufacturer_cluster") == "unresolved_other"]
    ids = [row["product_external_id"] for row in selected]
    if sha(INPUT) != INPUT_SHA256 or len(selected) != 395 or len(ids) != len(set(ids)):
        raise SystemExit("Wave217-A input pin/scope drift")
    category_counts = Counter(row["category_external_id"] for row in selected)
    if category_counts != {"seo:chargers": 172, "seo:replacement-tools": 98, "seo:power-systems": 84, "seo:warehouse-equipment": 39, "seo:batteries-traction": 2}:
        raise SystemExit(f"Wave217-A category drift: {category_counts}")
    if any(AUTOMOTIVE.search(row["name"]) or ELECTRONICS.search(row["name"]) for row in selected): raise SystemExit("automotive/electronics scope leak")
    processed_ids = {row["product_external_id"] for row in read_csv(PROCESSED)}
    processed_overlap = sorted(set(ids) & processed_ids)
    if processed_overlap: raise SystemExit(f"processed3000 overlap: {processed_overlap[:5]}")
    prior_paths = [path for path in GEN.glob("rb-wave*-evidence.csv") if path.name != OUTPUT.name]
    prior_ids = {row.get("product_external_id", "") for path in prior_paths for row in read_csv(path)}
    prior_overlap = sorted(set(ids) & prior_ids)
    if prior_overlap: raise SystemExit(f"prior evidence overlap: {prior_overlap[:5]}")
    registry = read_csv(REGISTRY)
    by_title, registry_names = defaultdict(list), []
    for row in registry:
        by_title[norm(row["name"])].append(row["registry_id"]); registry_names.append((row["registry_id"], norm(row["name"])))
    live = live_products(); live_by_id = {row["external_id"]: row for row in live}
    if set(ids) - set(live_by_id): raise SystemExit("candidate absent from live DB")
    live_index = defaultdict(list)
    for row in live:
        for value in (row.get("sku_normalized") or row.get("sku") or "", row.get("mpn_normalized") or row.get("mpn") or ""):
            if (key := norm(str(value))): live_index[key].append(row["external_id"])
    evidence, checks = [], []
    for row in selected:
        kind = product_type(row); brand, model, token, family = identity(row["name"]); token_norm = norm(token); current = live_by_id[row["product_external_id"]]
        title_dupes = sorted(peer for peer in by_title[norm(row["name"])] if peer != row["product_external_id"])
        registry_peers = sorted({external_id for external_id, text in registry_names if external_id != row["product_external_id"] and token_norm and token_norm in text})
        live_peers = sorted(peer for peer in live_index.get(token_norm, []) if peer != row["product_external_id"])
        reason = "exact_current_ID_title_bounded_model_manufacturer_primary_source_required"
        if not brand: reason = "manufacturer_unresolved; exact_first_party_source_required_before_identity_claim"
        evidence.append({
            "batch":"wave217a_unresolved", "product_external_id":row["product_external_id"], "name":row["name"], "category_external_id":row["category_external_id"], "factual_product_type":kind, "manufacturer_candidate":brand, "manufacturer_status":"title_label_candidate" if brand else "manufacturer_unresolved", "model_candidate":model, "bounded_model_token":token, "model_status":"title_derived_not_primary_verified", "family_group":family, "family_status":"title_derived_research_route", "variant_group":f"{brand or 'unresolved'}::{family}", "duplicate_group":f"{brand or 'unresolved'}::{token_norm}", "primary_manufacturer_source_route":route(brand, kind), "source_tier":"", "source_publisher":"", "source_url":"", "source_snapshot_path":"", "source_snapshot_sha256":"", "source_assertion":"", "partition":"primary_source_batch_hold", "conflict_reason":reason, "registry_exact_title_duplicates":"|".join(title_dupes), "registry_model_candidate_external_ids":"|".join(registry_peers), "live_db_collision_external_ids":"|".join(live_peers), "live_current_manufacturer":str(current.get("manufacturer") or ""), "live_current_mpn":str(current.get("mpn") or ""), "safe_to_apply":"false",
        })
        checks.append({"candidate_external_id":row["product_external_id"], "bounded_model_token_normalized":token_norm, "conflicting_external_ids":live_peers})
    if any(row["safe_to_apply"] == "true" for row in evidence): raise SystemExit("unverified identity admitted")
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(evidence)
    MANIFEST.write_text(json.dumps({"schema_version":1, "site_key":"microchips-by", "products":[]}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    manifest_hash = sha(MANIFEST); container_manifest = "/tmp/" + MANIFEST.name
    copied = subprocess.run(["docker","compose","cp",str(MANIFEST),"backend:"+container_manifest],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    if copied.returncode: raise SystemExit(f"could not place dry-run manifest: {copied.stderr.strip() or copied.stdout.strip()}")
    run = subprocess.run(["docker","compose","exec","-T","backend","php","artisan","catalog:apply-verified-oem-identities","microchips-by",container_manifest],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    dry = {"mode":"dry_run","attempted_without_apply":True,"apply_flag_used":False,"exit_code":run.returncode,"records":0,"manifest_sha256":manifest_hash,"stdout":run.stdout.strip(),"stderr":run.stderr.strip(),"expected_fail_closed_reason":"Manifest requires a non-empty products list.","database_mutations":0,"commercial_fields_changed":0,"publication_fields_changed":0}
    if run.returncode == 0 or "non-empty products list" not in (run.stdout+run.stderr): raise SystemExit("Laravel empty-manifest dry-run did not fail closed")
    LIVE.write_text(json.dumps({"schema_version":1,"mode":"read_only","query_exit_code":0,"database_mutations":0,"candidate_rows_checked":len(evidence),"checks":checks},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    DRY.write_text(json.dumps(dry,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary = {"schema_version":1,"batch":"wave217a_unresolved","checked_at":CHECKED_AT,"input":{"path":INPUT.relative_to(ROOT).as_posix(),"sha256":sha(INPUT),"rows":len(evidence),"category_counts":dict(sorted(category_counts.items()))},"scope":{"processed3000_overlap_ids":processed_overlap,"prior_evidence_overlap_ids":prior_overlap,"automotive_rows":0,"electronics_component_rows":0},"product_type_counts":dict(sorted(Counter(row["factual_product_type"] for row in evidence).items())),"canonical_registry":{"path":REGISTRY.relative_to(ROOT).as_posix(),"sha256":sha(REGISTRY),"rows":len(registry),"exact_title_collision_rows":sum(bool(row["registry_exact_title_duplicates"]) for row in evidence),"model_candidate_collision_rows":sum(bool(row["registry_model_candidate_external_ids"]) for row in evidence)},"live_collision_guard":{"path":LIVE.relative_to(ROOT).as_posix(),"database_mutations":0,"collision_rows":sum(bool(row["live_db_collision_external_ids"]) for row in evidence)},"partition_counts":dict(sorted(Counter(row["partition"] for row in evidence).items())),"manifest":{"path":MANIFEST.relative_to(ROOT).as_posix(),"sha256":manifest_hash,"rows":0},"laravel_dry_run":{"path":DRY.relative_to(ROOT).as_posix(),"exit_code":run.returncode,"database_mutations":0},"policy":{"exact_primary_source_required":True,"exact_safe_manifest_only":True,"database_apply":False}}
    SUMMARY.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_report(evidence,dry)
    print(json.dumps({"rows":len(evidence),"types":summary["product_type_counts"],"database_mutations":0},ensure_ascii=False))


if __name__ == "__main__": main()
