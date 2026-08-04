import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "build-tekcell-model-core-description-manifest.py"
SPEC = importlib.util.spec_from_file_location("build_tekcell_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def source_row(name: str, external_id: str = "КА-TEST") -> dict[str, str]:
    return {
        "product_external_id": external_id,
        "name": name,
        "category_external_id": "seo:primary-cells",
    }


def test_exact_model_tokens_stay_distinct():
    assert MODULE.model_core("SB AA02 TC (Tekcell)") == "SB-AA02"
    assert MODULE.model_core("SB-AA11 3P (Tekcell)") == "SB-AA11"
    assert MODULE.model_core("SB A01 AX (Tekcell)") == "SB-A01"
    assert MODULE.model_core("SB-C02 TC (Tekcell)") == "SB-C02"
    assert MODULE.model_core("SB D02 TC (Tekcell)") == "SB-D02"
    assert MODULE.model_core("SB AA TC (Tekcell)") is None
    assert MODULE.model_core("SB CO2 TC (Tekcell)") is None
    assert MODULE.model_core("SB-AA02P (Tekcell)") is None
    assert MODULE.model_core("SW D03 TC (Tekcell)") is None


def test_ambiguous_typo_and_missing_suffix_have_explicit_reasons():
    assert "cannot_be_silently_normalized" in MODULE.blocked_reason("SB CO2 TC (Tekcell)")
    assert MODULE.blocked_reason("SB AA TC (Tekcell)") == "ambiguous_SB-AA_without_02_or_11"


def test_execution_signals_are_retained_but_not_promoted_to_facts():
    row = MODULE.product_row(
        source_row("SB AA02 TC 2PF (Tekcell) с разъемом JST-PHR-2"),
        "SB-AA02",
    )
    assert row["identity_scope"] == "model_core"
    assert row["unverified_execution_signals"] == ["TC", "2PF", "JST", "PHR-2", "connector"]
    serialized = json.dumps(row["technical_attributes"], ensure_ascii=False).lower()
    assert "характеристики относятся только к базовой ячейке" in serialized
    for forbidden in ("jst", "phr-2", "mu-2f", "ehr-2", "bsl-2"):
        assert forbidden not in serialized
    assert set(row["technical_attributes"]) == MODULE.ALLOWED_ATTRIBUTE_KEYS


def test_model_specs_are_not_cross_assigned():
    capacities = {model: MODULE.MODELS[model]["capacity"] for model in MODULE.MODELS}
    assert capacities == {
        "SB-AA02": "1,2 А·ч",
        "SB-AA11": "2,5 А·ч",
        "SB-A01": "3,6 А·ч",
        "SB-C02": "8,5 А·ч",
        "SB-D02": "19 А·ч",
    }
    assert len(set(capacities.values())) == 5


def test_chemistry_claim_has_a_separate_official_supporting_source():
    row = MODULE.product_row(source_row("SB AA11 TC (Tekcell)"), "SB-AA11")
    assert row["source_url"].startswith("https://www.vitzrocell.com/")
    assert row["supporting_source_urls"] == [MODULE.CHEMISTRY_SOURCE_URL]
    assert MODULE.CHEMISTRY_SOURCE_URL.startswith("https://www.vitzrocell.com/catalog/")


def test_payload_separates_safe_and_blocked_rows():
    payload = MODULE.build_payload(
        [
            source_row("SB-AA02-2P 1S (Tekcell)", "КА-1"),
            source_row("SB CO2 TC (Tekcell) с разъемом CNR", "КА-2"),
            source_row("SB AA TC (Tekcell)", "КА-3"),
            source_row("CR17450 TC (Tekcell)", "КА-4"),
            source_row("FANSO ER14505H", "КА-5"),
        ],
        expected=1,
    )
    assert [row["external_id"] for row in payload["products"]] == ["КА-1"]
    assert [row["external_id"] for row in payload["blocked_rows"]] == ["КА-2", "КА-3", "КА-4"]
    assert payload["products"][0]["unverified_execution_signals"] == ["2P", "1S"]


def test_guards_category_duplicate_ids_and_expected_count():
    wrong_category = source_row("SB AA02 TC (Tekcell)")
    wrong_category["category_external_id"] = "seo:batteries-ups"
    with pytest.raises(RuntimeError, match="escaped primary-cells"):
        MODULE.build_payload([wrong_category], expected=1)

    with pytest.raises(RuntimeError, match="duplicate external IDs"):
        MODULE.build_payload(
            [
                source_row("SB AA02 TC (Tekcell)", "КА-DUP"),
                source_row("SB AA11 TC (Tekcell)", "КА-DUP"),
            ],
            expected=2,
        )

    with pytest.raises(RuntimeError, match="Expected 2 safe TEKCELL rows, got 1"):
        MODULE.build_payload([source_row("SB AA02 TC (Tekcell)")], expected=2)


def test_serializes_unescaped_utf8_without_bom():
    payload = MODULE.build_payload([source_row("SB AA02 TC (Tekcell)")], expected=1)
    raw = MODULE.serialize_payload(payload)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert "Первичный".encode("utf-8") in raw
    assert b"\\u041f" not in raw
    assert json.loads(raw.decode("utf-8"))["products"][0]["manufacturer"] == "TEKCELL / Vitzrocell"
