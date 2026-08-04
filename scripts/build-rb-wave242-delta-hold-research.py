#!/usr/bin/env python3
"""Offline fail-closed Wave242 audit of the 136 reviewed Delta HOLD rows."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
CHECKED_AT = "2026-07-29"
INPUT = ROOT / "docs/audits/generated/rb-wave241c-reviewed-identity-skips.csv"
PRIOR_LEDGER = ROOT / "docs/audits/generated/rb-wave233a-delta-identity-ledger.csv"
PRIOR_REPORT = ROOT / "docs/audits/2026-07-29-rb-wave233a-delta-identities.md"
SOURCE_REGISTRY = ROOT / "docs/audits/sources/wave242-delta/registry.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave242-delta-hold-research-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave242-delta-hold-research.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave242-delta-2026-07-29.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave242-delta-2026-07-29.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave242-delta-hold-research.md"
LARAVEL_DRY_RUN = ROOT / "docs/audits/generated/rb-wave242-delta-description-laravel-dry-run.json"
EXPECTED_PINS = {
    INPUT: "674d7284f10282b9f3f970f44478f096678b5bf47386de1a57cb2b85a754393e",
    PRIOR_LEDGER: "f26dc345f1ce565fb02323b10be5b4a1fedda7de17ac8ea3b847aff181ab7482",
    PRIOR_REPORT: "a9880a0e7c81f58f506a365b2b65babf09db868b0b1355fcf25598db46bf25df",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def canonical_model(value: str) -> str:
    value = re.sub(r"^delta\s+", "", value.strip(), flags=re.I)
    value = re.sub(r"^xpert\s+", "", value, flags=re.I)
    value = re.sub(r"\s+xpert$", "", value, flags=re.I)
    value = re.sub(r"мм", "", value, flags=re.I)
    return normalized(value)


def title_capacity(title: str) -> Decimal:
    match = re.search(r"\(AGM,\s*([0-9]+(?:[.,][0-9]+)?)\s*Ah\)", title, flags=re.I)
    if not match:
        raise ValueError(f"capacity absent from title: {title}")
    return Decimal(match.group(1).replace(",", "."))


def inferred_title_voltage(model: str) -> Decimal | None:
    core = re.sub(r"^XPERT\s+", "", model, flags=re.I)
    explicit = re.search(r"(?:^|\s)(12|6|4)-", core)
    if explicit:
        return Decimal(explicit.group(1))
    compact = re.search(r"^(?:DTM?|CT|CGD)\s*(12|6|4)\d", core, flags=re.I)
    return Decimal(compact.group(1)) if compact else None


def offered_rows(snapshot: Path) -> list[dict[str, object]]:
    soup = BeautifulSoup(snapshot.read_bytes(), "html.parser")
    text = html.unescape(" ".join(soup.stripped_strings))
    text = re.sub(r"\s+", " ", text)
    label = r"Напряжение\s*,?\s*В\s*[:—-]?\s*"
    capacity = r"Емкость\s*,?\s*Ач\s*[:—-]?\s*"
    pattern = re.compile(
        rf"(?:DELTA|Delta)\s+(.{{2,45}}?)\s+{label}([0-9]+(?:[.,][0-9]+)?)\s+{capacity}([0-9]+(?:[.,][0-9]+)?)",
        flags=re.I,
    )
    offers = []
    for match in pattern.finditer(text):
        model = match.group(1).strip(" :-")
        try:
            voltage = Decimal(match.group(2).replace(",", "."))
            amp_hours = Decimal(match.group(3).replace(",", "."))
        except InvalidOperation:
            continue
        offers.append({"display_model": model, "model_key": canonical_model(model),
                       "voltage": voltage, "capacity": amp_hours})
    # The official CT series cards omit a separate voltage label.  Their exact
    # offered model begins with CT 12..., so the voltage is still explicit in
    # the manufacturer model designation and can be checked fail-closed.
    card_pattern = re.compile(
        rf"(?:DELTA|Delta)\s+(CT\s+.{{1,24}}?)\s+{capacity}([0-9]+(?:[.,][0-9]+)?)",
        flags=re.I,
    )
    for match in card_pattern.finditer(text):
        model = match.group(1).strip(" :-")
        voltage = inferred_title_voltage(model)
        if voltage is None:
            continue
        amp_hours = Decimal(match.group(2).replace(",", "."))
        candidate = {"display_model": model, "model_key": canonical_model(model),
                     "voltage": voltage, "capacity": amp_hours}
        if candidate not in offers:
            offers.append(candidate)
    return offers


def json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def build() -> dict[str, object]:
    for path, expected in EXPECTED_PINS.items():
        if sha(path) != expected:
            raise SystemExit(f"pinned input changed: {path.relative_to(ROOT)}")

    prior = read_csv(PRIOR_LEDGER)
    prior_holds = {row["external_id"]: row for row in prior if row["decision"] == "HOLD"}
    reviewed = {row["product_external_id"]: row for row in read_csv(INPUT)}
    if len(prior_holds) != 136 or set(prior_holds) - set(reviewed):
        raise SystemExit("Wave242 scope must be the 136 reviewed Wave233a Delta HOLD rows")
    for external_id, old in prior_holds.items():
        if reviewed[external_id]["name"] != old["current_name"]:
            raise SystemExit(f"title drift for {external_id}")

    source_payload = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    old_hashes = {row["source_snapshot_sha256"] for row in prior if row["source_snapshot_sha256"]}
    old_urls = {row["source_url"] for row in prior if row["source_url"]}
    sources: dict[str, dict[str, object]] = {}
    for source in source_payload["sources"]:
        url = source["source_url"]
        path = ROOT / source["snapshot_path"]
        if not url.startswith(("https://delta-batt.com/", "https://www.delta-batt.com/",
                               "https://kz.delta-batt.com/", "https://www.kz.delta-batt.com/")):
            raise SystemExit(f"non-official source: {url}")
        if sha(path) != source["snapshot_sha256"]:
            raise SystemExit(f"source SHA mismatch: {path}")
        if source["snapshot_sha256"] in old_hashes or url in old_urls:
            raise SystemExit(f"Wave233a source repeated: {url}")
        snapshot_text = BeautifulSoup(path.read_bytes(), "html.parser").get_text(" ", strip=True)
        source_technology = "AGM" if re.search(r"(?<![A-Z])AGM(?![A-Z])", snapshot_text, flags=re.I) else ""
        sources[source["source_id"]] = {
            **source, "path": path, "offers": offered_rows(path), "technology": source_technology,
        }

    offer_index: dict[str, list[tuple[dict[str, object], dict[str, object]]]] = defaultdict(list)
    for source in sources.values():
        for offer in source["offers"]:
            offer_index[str(offer["model_key"])].append((source, offer))

    ledger = []
    identity_products = []
    description_products = []
    for external_id, prior_row in sorted(prior_holds.items()):
        title = prior_row["current_name"]
        mpn = prior_row["mpn"]
        model_key = canonical_model(mpn)
        candidates = offer_index.get(model_key, [])
        title_ah = title_capacity(title)
        title_v = inferred_title_voltage(mpn)
        reasons = []
        if prior_row["canonical_conflict_external_ids"]:
            reasons.append("LIVE_DUPLICATE_OWNERSHIP_CONFLICT")
        if not candidates:
            reasons.append("NO_NEW_OFFICIAL_EXACT_OFFERED_MODEL")
        specs = {(offer["voltage"], offer["capacity"]) for _, offer in candidates}
        if len(specs) > 1:
            reasons.append("OFFICIAL_SOURCE_SPEC_AMBIGUITY")
        selected = sorted(candidates, key=lambda item: (item[0]["source_id"], item[1]["display_model"]))[0] if candidates else None
        source = selected[0] if selected else None
        offer = selected[1] if selected else None
        if offer and offer["capacity"] != title_ah:
            reasons.append("TITLE_CAPACITY_CONFLICT")
        if offer and title_v is not None and offer["voltage"] != title_v:
            reasons.append("TITLE_VOLTAGE_CONFLICT")
        decision = "PASS" if not reasons else "HOLD"
        description_reasons = list(reasons)
        if source and not source["technology"]:
            description_reasons.append("NO_SOURCE_SUPPORTED_TECHNOLOGY")
        description_decision = "PASS" if not description_reasons else "HOLD"
        row = {
            "external_id": external_id,
            "current_name": title,
            "manufacturer": "Delta",
            "mpn": mpn,
            "mpn_normalized": model_key,
            "title_capacity_ah": str(title_ah),
            "title_voltage_v": str(title_v) if title_v is not None else "",
            "source_offered_model": str(offer["display_model"]) if offer else "",
            "source_capacity_ah": str(offer["capacity"]) if offer else "",
            "source_voltage_v": str(offer["voltage"]) if offer else "",
            "source_technology": str(source["technology"]) if source else "",
            "source_url": str(source["source_url"]) if source else "",
            "source_snapshot_path": str(source["snapshot_path"]) if source else "",
            "source_snapshot_sha256": str(source["snapshot_sha256"]) if source else "",
            "live_duplicate_owner_external_ids": prior_row["canonical_conflict_external_ids"],
            "decision": decision,
            "hold_reason": "|".join(reasons),
            "description_decision": description_decision,
            "description_hold_reason": "|".join(description_reasons),
        }
        ledger.append(row)
        if decision == "PASS":
            identity_products.append({
                "external_id": external_id, "current_name": title, "manufacturer": "Delta", "mpn": mpn,
                "source_url": source["source_url"], "source_kind": "official_manufacturer_catalogue",
                "source_publisher": source["source_publisher"], "checked_at": CHECKED_AT,
                "product_type": "stationary sealed rechargeable battery",
                "source_snapshot_path": "../audits/" + str(source["snapshot_path"]).removeprefix("docs/audits/"),
                "source_snapshot_sha256": source["snapshot_sha256"],
            })
        if description_decision == "PASS":
            description_products.append({
                "external_id": external_id, "identity_scope": "model_core", "manufacturer": "Delta", "model_core": mpn,
                "technology": source["technology"],
                "source_url": source["source_url"],
                "technical_attributes": {"Модель": mpn, "Напряжение, В": str(offer["voltage"]),
                                         "Емкость, Ач": str(offer["capacity"])},
                "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary",
                "source_publisher": source["source_publisher"], "manufacturer_primary": True,
                "evidence_scope": "model_core", "checked_at": CHECKED_AT,
            })

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)
    json_write(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "products": identity_products})
    json_write(DESCRIPTIONS, {
        "schema_version": 1,
        "purpose": "Source-backed description drafts for reviewed Wave242 Delta model-core evidence",
        "locale": "ru-BY",
        "products": description_products,
    })
    dry_run = json.loads(LARAVEL_DRY_RUN.read_text(encoding="utf-8"))
    if (dry_run.get("manifest_sha256") != sha(DESCRIPTIONS)
            or dry_run.get("records") != len(description_products)
            or dry_run.get("exit_code") != 0
            or dry_run.get("apply_flag_used") is not False
            or dry_run.get("persisted_description_drafts") != 0):
        raise SystemExit("Wave242 Laravel dry-run evidence does not match the final description manifest")
    counts = Counter(row["decision"] for row in ledger)
    hold_reasons = Counter(reason for row in ledger for reason in row["hold_reason"].split("|") if reason)
    description_counts = Counter(row["description_decision"] for row in ledger)
    description_hold_reasons = Counter(
        reason for row in ledger for reason in row["description_hold_reason"].split("|") if reason
    )
    summary = {
        "schema_version": 1, "wave": "wave242_delta_hold_research", "checked_at": CHECKED_AT,
        "coverage": {"scope": 136, "pass": counts["PASS"], "hold": counts["HOLD"]},
        "hold_reasons": dict(sorted(hold_reasons.items())),
        "description_coverage": {
            "scope": 136, "pass": description_counts["PASS"], "hold": description_counts["HOLD"],
        },
        "description_hold_reasons": dict(sorted(description_hold_reasons.items())),
        "pins": {path.relative_to(ROOT).as_posix(): expected for path, expected in EXPECTED_PINS.items()},
        "new_source_registry": {"path": SOURCE_REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha(SOURCE_REGISTRY),
                                "sources": len(sources)},
        "no_repeat_wave233a": {"prior_rows": len(prior), "prior_source_hash_overlap": 0, "prior_source_url_overlap": 0},
        "manifests": {"identities": len(identity_products), "descriptions": len(description_products)},
        "laravel_dry_run": {
            "path": LARAVEL_DRY_RUN.relative_to(ROOT).as_posix(),
            "sha256": sha(LARAVEL_DRY_RUN),
            "exit_code": 0,
            "apply_flag_used": False,
            "persisted_description_drafts": 0,
        },
        "safety": {"builder_network_calls": 0, "builder_database_operations": 0,
                   "repository_database_mutations": 0, "apply_performed": False,
                   "price_or_stock_changes": 0, "media_changes": 0},
    }
    json_write(SUMMARY, summary)
    REPORT.write_text(
        "# Wave242 Delta HOLD research\n\n"
        f"All 136 blank-manufacturer Delta HOLD rows were processed as one fail-closed batch. "
        f"Identity result: **PASS {counts['PASS']}, HOLD {counts['HOLD']}**. "
        f"Stageable description result: **PASS {description_counts['PASS']}, HOLD {description_counts['HOLD']}**.\n\n"
        "Wave233a ledger/report were pinned before research. Its saved URLs and snapshot hashes were excluded; "
        f"the Wave242 evidence packet contains {len(sources)} newly downloaded official Delta series/catalogue pages.\n\n"
        "A row passes only when a new snapshot contains one exact offered model with matching title capacity and "
        "inferred title voltage, and the pinned same-day duplicate-ownership slice has no owner. Any missing model, "
        "spec conflict, ambiguity, or duplicate owner remains HOLD.\n\n"
        "## HOLD reasons\n\n" + "".join(f"- `{reason}`: {count}\n" for reason, count in sorted(hold_reasons.items())) +
        "\n## Description HOLD reasons\n\n" +
        "".join(f"- `{reason}`: {count}\n" for reason, count in sorted(description_hold_reasons.items())) +
        "\n## Laravel dry-run\n\nThe real `content:stage-source-backed-description-drafts` command accepted all "
        f"{len(description_products)} rows in an isolated RefreshDatabase fixture with exact Bitrix staging lineage. "
        "The transaction was rolled back: zero description drafts persisted and `--apply` was not used.\n\n"
        "## Safety\n\nThe builder is offline. No apply, media, price, stock, or publication action was performed.\n",
        encoding="utf-8", newline="\n",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
