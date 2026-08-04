import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "build-fanso-model-core-description-manifest.py"
SPEC = importlib.util.spec_from_file_location("build_fanso_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def source_row(name: str, external_id: str = "КА-TEST") -> dict[str, str]:
    return {
        "product_external_id": external_id,
        "name": name,
        "category_external_id": "seo:primary-cells",
    }


def test_matches_only_exact_h_or_m_model_tokens():
    assert MODULE.model_core("ER14505H/S FANSO") == "ER14505H"
    assert MODULE.model_core("ER18505H-LD/-EHR-02 FANSO") == "ER18505H"
    assert MODULE.model_core("ER34615M/S FANSO") == "ER34615M"
    assert MODULE.model_core("ER14505 FANSO") is None
    assert MODULE.model_core("ER14505HT FANSO") is None
    assert MODULE.model_core("CR14250H FANSO") is None


def test_blocks_pack_or_assembly_even_with_exact_cell_token():
    assert MODULE.model_core("2*ER18505M FANSO с выводами") is None
    assert MODULE.model_core("ER18505M FANSO комплект") is None
    assert MODULE.model_core("ER18505M FANSO battery pack") is None


def test_product_row_is_model_core_and_has_no_assembly_facts():
    row = MODULE.product_row(source_row("ER14505H-LD/-PHR-02 FANSO"), "ER14505H")
    assert row["identity_scope"] == "model_core"
    assert "mpn" not in row
    assert row["model_core"] == "ER14505H"
    serialized = json.dumps(row["technical_attributes"], ensure_ascii=False).lower()
    for forbidden in ("jst", "phr", "ehr", "xhp", "2pf", "3pf", "4pf", "китай"):
        assert forbidden not in serialized
    assert "разъём" in row["technical_attributes"]["Ограничение источника"].lower()
    assert set(row["technical_attributes"]) == MODULE.ALLOWED_ATTRIBUTE_KEYS


def test_attribute_whitelist_rejects_country_or_connector_fact():
    invalid = {key: "value" for key in MODULE.ALLOWED_ATTRIBUTE_KEYS}
    invalid["Страна происхождения"] = "Китай"
    with pytest.raises(RuntimeError, match="unexpected"):
        MODULE.validate_attributes(invalid)


def test_payload_separates_safe_and_blocked_rows():
    payload = MODULE.build_payload(
        [
            source_row("ER14250H/3PF FANSO", "КА-1"),
            source_row("ER14250 2PF FANSO", "КА-2"),
            source_row("CR14250H FANSO", "КА-3"),
            source_row("TEKCELL SB-AA11", "КА-4"),
        ],
        expected=1,
    )
    assert [row["external_id"] for row in payload["products"]] == ["КА-1"]
    assert [row["external_id"] for row in payload["blocked_rows"]] == ["КА-2", "КА-3"]


def test_guards_category_duplicate_ids_and_expected_count():
    wrong_category = source_row("ER14250H FANSO")
    wrong_category["category_external_id"] = "seo:batteries-ups"
    with pytest.raises(RuntimeError, match="escaped primary-cells"):
        MODULE.build_payload([wrong_category], expected=1)

    with pytest.raises(RuntimeError, match="duplicate external IDs"):
        MODULE.build_payload(
            [
                source_row("ER14250H FANSO", "КА-DUP"),
                source_row("ER14505H FANSO", "КА-DUP"),
            ],
            expected=2,
        )

    with pytest.raises(RuntimeError, match="Expected 2 safe FANSO rows, got 1"):
        MODULE.build_payload([source_row("ER14250H FANSO")], expected=2)


def test_serializes_unescaped_utf8_without_bom():
    payload = MODULE.build_payload([source_row("ER14250H FANSO")], expected=1)
    raw = MODULE.serialize_payload(payload)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert "Первичный".encode("utf-8") in raw
    assert b"\\u041f" not in raw
    assert json.loads(raw.decode("utf-8"))["products"][0]["manufacturer"] == "FANSO"
