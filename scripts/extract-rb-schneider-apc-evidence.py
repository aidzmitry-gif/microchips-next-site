#!/usr/bin/env python3
"""Extract exact-SKU APC facts from immutable Schneider Product JSON-LD.

Commercial offer data is deliberately ignored: a US page cannot establish RB
price or stock. Image URLs are retained only as non-publishable candidates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

LD_JSON = re.compile(
    r"<script\b[^>]*\btype\s*=\s*(['\"])application/ld\+json\1[^>]*>(.*?)</script>",
    re.I | re.S,
)
CANONICAL = re.compile(
    r"<link\b[^>]*\brel\s*=\s*(['\"])canonical\1[^>]*\bhref\s*=\s*(['\"])(.*?)\2[^>]*>",
    re.I | re.S,
)
VOLTAGE = re.compile(r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*V(?:dc)?\b", re.I)
CAPACITY_AH = re.compile(r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*Ah\b", re.I)
CAPACITY_VAH = re.compile(r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*VAh\b", re.I)
CHARACTERISTIC = re.compile(
    r'characteristicName:"([^"]+)",characteristicValues:\[\{.{0,260}?labelText:"([^"]*)"',
    re.I | re.S,
)


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def exact_sku(value: str, expected: str) -> bool:
    """Compare official SKU identity without erasing meaningful punctuation."""
    return (value or "").strip().casefold() == (expected or "").strip().casefold()


def exact_product_url(value: str, sku: str) -> bool:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").casefold()
    segments = [segment for segment in parsed.path.split("/") if segment]
    try:
        product_index = [segment.casefold() for segment in segments].index("product")
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and (host == "se.com" or host.endswith(".se.com"))
        and parsed.username is None
        and parsed.password is None
        and parsed.port in {None, 443}
        and not parsed.query
        and not parsed.fragment
        and product_index + 1 < len(segments)
        and exact_sku(segments[product_index + 1], sku)
    )


def load(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        return list(reader)


def product_nodes(raw: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for match in LD_JSON.finditer(raw):
        try:
            value = json.loads(html.unescape(match.group(2)).strip())
        except json.JSONDecodeError:
            continue
        nodes = value.get("@graph", []) if isinstance(value, dict) and "@graph" in value else [value]
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, dict):
                continue
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(str(item).casefold() == "product" for item in types):
                result.append(node)
    return result


def unique_number(pattern: re.Pattern[str], text: str) -> str:
    values = {value.replace(",", ".") for value in pattern.findall(text)}
    return next(iter(values)) if len(values) == 1 else ""


def product_type(text: str) -> str:
    lowered = text.casefold()
    if "replacement battery cartridge" in lowered:
        return "replacement_battery_cartridge"
    if "battery module" in lowered or "battery unit" in lowered:
        return "battery_module"
    if "external battery pack" in lowered or "battery pack" in lowered:
        return "external_battery_pack"
    return "battery_product"


def first_official_image(node: dict[str, object]) -> str:
    images = node.get("image", [])
    images = images if isinstance(images, list) else [images]
    for value in images:
        if not isinstance(value, str):
            continue
        parsed = urlsplit(value)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme == "https" and host in {
            "download.schneider-electric.com", "www.se.com", "se.com"
        }:
            return value
    return ""


def characteristics(raw: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for key, value in CHARACTERISTIC.findall(raw):
        key = re.sub(r"\s+", " ", html.unescape(key)).strip().casefold()
        value = html.unescape(value).replace("\\u003Cbr />", "; ").strip()
        if value and value not in result.setdefault(key, []):
            result[key].append(value)
    return result


def build(candidates_path: Path, registry_path: Path, output: Path, summary_path: Path) -> dict[str, object]:
    candidates = load(candidates_path, {"external_id", "model_token", "safe_to_apply"})
    if any(row["safe_to_apply"].strip().casefold() != "false" for row in candidates):
        raise ValueError("candidate rows must remain safe_to_apply=false")
    by_id = {row["external_id"].strip(): row for row in candidates}
    if len(by_id) != len(candidates) or any(not key for key in by_id):
        raise ValueError("candidate external_id must be unique and nonblank")

    registry = load(registry_path, {
        "external_id", "model_token", "final_url", "source_sha256",
        "snapshot_path", "acquisition_status", "safe_to_apply",
    })
    results: list[dict[str, str]] = []
    rejected: Counter[str] = Counter()
    seen: set[str] = set()
    for page in registry:
        external_id = page["external_id"].strip()
        candidate = by_id.get(external_id)
        if candidate is None:
            rejected["not_a_candidate"] += 1
            continue
        if external_id in seen:
            raise ValueError(f"registry repeats external_id {external_id}")
        seen.add(external_id)
        if page["acquisition_status"] != "acquired":
            rejected["acquisition_hold"] += 1
            continue
        sku = candidate["model_token"].strip()
        if not exact_sku(page["model_token"], sku) or not exact_product_url(page["final_url"], sku):
            rejected["identity_or_url_mismatch"] += 1
            continue
        snapshot = Path(page["snapshot_path"])
        if not snapshot.is_file():
            rejected["missing_snapshot"] += 1
            continue
        raw_bytes = snapshot.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != page["source_sha256"].casefold():
            rejected["snapshot_sha256_mismatch"] += 1
            continue
        try:
            raw = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            rejected["non_utf8_snapshot"] += 1
            continue
        canonical_values = [html.unescape(match.group(3)).strip() for match in CANONICAL.finditer(raw)]
        canonical_values = list(dict.fromkeys(canonical_values))
        if len(canonical_values) != 1 or canonical_values[0].rstrip("/") != page["final_url"].rstrip("/"):
            rejected["canonical_mismatch"] += 1
            continue
        nodes = [node for node in product_nodes(raw) if exact_sku(str(node.get("sku", "")), sku)]
        if len(nodes) != 1:
            rejected["missing_or_ambiguous_exact_product_jsonld"] += 1
            continue
        node = nodes[0]
        name = str(node.get("name", "")).strip()
        description = str(node.get("description", "")).strip()
        brand = node.get("brand", {})
        brand_name = str(brand.get("name", "")) if isinstance(brand, dict) else str(brand)
        # Retired but still first-party product pages sometimes omit the long
        # JSON-LD description. Their exact Product SKU + brand + canonical
        # product title remains valid identity/type evidence; no missing facts
        # are inferred from the omission.
        if not name or "apc" not in brand_name.casefold():
            rejected["incomplete_product_jsonld"] += 1
            continue
        page_characteristics = characteristics(raw)
        exact_characteristic_text = " ".join(
            value
            for key in ("battery voltage", "battery capacity")
            for value in page_characteristics.get(key, [])
        )
        fact_text = f"{name} {description} {exact_characteristic_text}"
        voltage = unique_number(VOLTAGE, fact_text)
        capacity_ah = unique_number(CAPACITY_AH, fact_text)
        capacity_vah = unique_number(CAPACITY_VAH, fact_text)
        battery_types = page_characteristics.get("battery type", [])
        lowered = f"{fact_text} {' '.join(battery_types)}".casefold()
        technology = "VRLA lead-acid" if "vrla" in lowered else ("lead-acid" if "lead-acid" in lowered or "lead acid" in lowered else "")
        component_types = page_characteristics.get("product or component type", [])
        classified_type = product_type(" ".join(component_types) + " " + fact_text)
        results.append({
            "external_id": external_id,
            "model_token": sku,
            "source_url": page["final_url"],
            "source_snapshot_path": str(snapshot.resolve()),
            "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "official_product_name": name,
            "official_description": description,
            "product_type": classified_type,
            "technology": technology,
            "voltage_v": voltage,
            "capacity_ah": capacity_ah,
            "capacity_vah": capacity_vah,
            "image_url_candidate": first_official_image(node),
            "image_safe_to_publish": "false",
            "price_or_stock_imported": "false",
            "publisher": "APC by Schneider Electric",
            "evidence_kind": "exact_product_jsonld",
            "safe_to_apply": "false",
        })

    results.sort(key=lambda row: row["external_id"])
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "external_id", "model_token", "source_url", "source_snapshot_path",
        "source_sha256", "official_product_name", "official_description",
        "product_type", "technology", "voltage_v", "capacity_ah",
        "capacity_vah", "image_url_candidate", "image_safe_to_publish",
        "price_or_stock_imported", "publisher", "evidence_kind", "safe_to_apply",
    ]
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    summary = {
        "candidate_path": str(candidates_path),
        "candidate_sha256": hashlib.sha256(candidates_path.read_bytes()).hexdigest(),
        "registry_path": str(registry_path),
        "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "candidate_records": len(candidates),
        "registry_records": len(registry),
        "exact_evidence_records": len(results),
        "technical_fact_records": sum(bool(row["voltage_v"] or row["capacity_ah"] or row["capacity_vah"]) for row in results),
        "image_candidates_not_publishable": sum(bool(row["image_url_candidate"]) for row in results),
        "rejected_counts": dict(sorted(rejected.items())),
        "output_path": str(output),
        "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "price_or_stock_records": 0,
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.candidates, args.registry, args.output, args.summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
