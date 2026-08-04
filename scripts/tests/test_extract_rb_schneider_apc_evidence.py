from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "extract-rb-schneider-apc-evidence.py"
SPEC = importlib.util.spec_from_file_location("apc_extract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def temp() -> Path:
    root = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-apc-extract-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def fixture(root: Path, *, canonical: str | None = None, sku: str = "RBC7") -> tuple[Path, Path]:
    url = f"https://www.se.com/us/en/product/{sku}/exact-product/"
    canonical = canonical or url
    product = {
        "@context": "https://schema.org/", "@type": "Product", "sku": sku,
        "brand": {"@type": "Brand", "name": "APC Brand"},
        "name": "APC Replacement Battery Cartridge, 24V 17Ah lead-acid battery",
        "description": f"The 24V 17Ah VRLA {sku} battery is fully assembled.",
        "image": ["https://download.schneider-electric.com/files?image=RBC7"],
        "offers": {"price": "999", "availability": "https://schema.org/InStock"},
    }
    raw = (f'<link rel="canonical" href="{canonical}"><script type="application/ld+json">'
           + json.dumps(product) + "</script>").encode()
    snapshot = root / "page.html"; snapshot.write_bytes(raw)
    candidates = root / "candidates.csv"
    write_csv(candidates, ["external_id", "model_token", "safe_to_apply"], [
        {"external_id": "bitrix:1", "model_token": sku, "safe_to_apply": "false"}
    ])
    registry = root / "registry.csv"
    write_csv(registry, ["external_id", "model_token", "final_url", "source_sha256", "snapshot_path", "acquisition_status", "safe_to_apply"], [{
        "external_id": "bitrix:1", "model_token": sku, "final_url": url,
        "source_sha256": hashlib.sha256(raw).hexdigest(), "snapshot_path": str(snapshot),
        "acquisition_status": "acquired", "safe_to_apply": "false",
    }])
    return candidates, registry


def test_extracts_exact_jsonld_facts_but_not_offer_or_publishable_image() -> None:
    root = temp()
    try:
        candidates, registry = fixture(root)
        summary = MODULE.build(candidates, registry, root / "out.csv", root / "summary.json")
        rows = list(csv.DictReader((root / "out.csv").open(encoding="utf-8-sig")))
        assert summary["exact_evidence_records"] == 1
        assert rows[0]["model_token"] == "RBC7"
        assert rows[0]["voltage_v"] == "24" and rows[0]["capacity_ah"] == "17"
        assert rows[0]["technology"] == "VRLA lead-acid"
        assert rows[0]["image_safe_to_publish"] == "false"
        assert rows[0]["price_or_stock_imported"] == "false"
        assert "999" not in json.dumps(rows[0]) and "InStock" not in json.dumps(rows[0])
    finally:
        shutil.rmtree(root)


def test_holds_wrong_canonical_or_wrong_jsonld_sku() -> None:
    root = temp()
    try:
        candidates, registry = fixture(root, canonical="https://www.se.com/us/en/product/RBC8/wrong/")
        summary = MODULE.build(candidates, registry, root / "out.csv", root / "summary.json")
        assert summary["exact_evidence_records"] == 0
        assert summary["rejected_counts"] == {"canonical_mismatch": 1}
    finally:
        shutil.rmtree(root)


def test_ambiguous_numbers_are_not_silently_selected() -> None:
    root = temp()
    try:
        candidates, registry = fixture(root)
        path = Path(next(csv.DictReader(registry.open(encoding="utf-8-sig")))["snapshot_path"])
        raw = path.read_text(encoding="utf-8").replace("fully assembled", "also references 12V 7Ah; fully assembled")
        path.write_text(raw, encoding="utf-8")
        rows = list(csv.DictReader(registry.open(encoding="utf-8-sig")))
        rows[0]["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        write_csv(registry, list(rows[0]), rows)
        MODULE.build(candidates, registry, root / "out.csv", root / "summary.json")
        result = next(csv.DictReader((root / "out.csv").open(encoding="utf-8-sig")))
        assert result["voltage_v"] == "" and result["capacity_ah"] == ""
    finally:
        shutil.rmtree(root)


def test_exact_retired_product_without_description_keeps_title_only() -> None:
    root = temp()
    try:
        candidates, registry = fixture(root)
        path = Path(next(csv.DictReader(registry.open(encoding="utf-8-sig")))["snapshot_path"])
        raw = path.read_text(encoding="utf-8").replace(
            '"description": "The 24V 17Ah VRLA RBC7 battery is fully assembled.",',
            '"description": "",',
        )
        path.write_text(raw, encoding="utf-8")
        rows = list(csv.DictReader(registry.open(encoding="utf-8-sig")))
        rows[0]["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        write_csv(registry, list(rows[0]), rows)
        summary = MODULE.build(candidates, registry, root / "out.csv", root / "summary.json")
        result = next(csv.DictReader((root / "out.csv").open(encoding="utf-8-sig")))
        assert summary["exact_evidence_records"] == 1
        assert result["official_description"] == ""
        assert result["voltage_v"] == "24" and result["capacity_ah"] == "17"
    finally:
        shutil.rmtree(root)


def test_uses_exact_main_product_characteristics_when_title_has_no_facts() -> None:
    root = temp()
    try:
        candidates, registry = fixture(root)
        path = Path(next(csv.DictReader(registry.open(encoding="utf-8-sig")))["snapshot_path"])
        raw = path.read_text(encoding="utf-8")
        raw = raw.replace("24V 17Ah lead-acid", "battery")
        raw = raw.replace("The 24V 17Ah VRLA RBC7 battery is fully assembled.", "The RBC7 battery is fully assembled.")
        raw += ('characteristicName:"battery type",characteristicValues:[{labelText:"Lead-Acid battery"}]}'
                'characteristicName:"Battery Voltage",characteristicValues:[{labelText:"48 V"}]}'
                'characteristicName:"Battery Capacity",characteristicValues:[{labelText:"9 Ah"}]}')
        path.write_text(raw, encoding="utf-8")
        rows = list(csv.DictReader(registry.open(encoding="utf-8-sig")))
        rows[0]["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        write_csv(registry, list(rows[0]), rows)
        MODULE.build(candidates, registry, root / "out.csv", root / "summary.json")
        result = next(csv.DictReader((root / "out.csv").open(encoding="utf-8-sig")))
        assert result["technology"] == "lead-acid"
        assert result["voltage_v"] == "48" and result["capacity_ah"] == "9"
    finally:
        shutil.rmtree(root)


def test_sku_punctuation_is_part_of_exact_identity() -> None:
    root = temp()
    try:
        candidates, registry = fixture(root, sku="RBC-7")
        rows = list(csv.DictReader(registry.open(encoding="utf-8-sig")))
        rows[0]["final_url"] = "https://www.se.com/us/en/product/RBC7/wrong-identity/"
        write_csv(registry, list(rows[0]), rows)
        summary = MODULE.build(candidates, registry, root / "out.csv", root / "summary.json")
        assert summary["exact_evidence_records"] == 0
        assert summary["rejected_counts"] == {"identity_or_url_mismatch": 1}
    finally:
        shutil.rmtree(root)


def test_classifies_battery_unit_and_pack_from_official_title_even_with_component_type() -> None:
    assert MODULE.product_type("Battery casing APC Smart-UPS Extended Run Battery Pack") == "external_battery_pack"
    assert MODULE.product_type("APC Symmetra Battery Unit") == "battery_module"
