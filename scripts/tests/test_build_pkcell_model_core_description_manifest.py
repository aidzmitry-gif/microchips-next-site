import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "build-pkcell-model-core-description-manifest.py"
SPEC = importlib.util.spec_from_file_location("build_pkcell_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def source_row(name: str, external_id: str = "КА-TEST") -> dict[str, str]:
    return {
        "product_external_id": external_id,
        "name": name,
        "category_external_id": "seo:primary-cells",
    }


def test_nimh_aa_and_aaa_model_cores_do_not_collapse():
    assert MODULE.model_core("Ni-MH PKCELL AAA/R03 1000mAh") == "R03"
    assert MODULE.model_core("Ni-MH PKCELL RTU R03 1000mAh") == "R03"
    assert MODULE.model_core("Ni-MH PKCELL AA/R06 2800mAh") == "R06"
    assert MODULE.model_core("Ni-MH PKCELL R06 2800mAh") == "R06"
    assert MODULE.model_core("PKCELL LR03 alkaline") is None
    assert MODULE.model_core("Ni-MH OTHER R03 1000mAh") is None
    assert MODULE.model_core("Ni-Cd PKCELL R03 1000mAh") is None


def test_er_cr_and_h_m_suffixes_remain_distinct():
    assert MODULE.primary_lithium_token("PKCELL ER14505") == "ER14505"
    assert MODULE.primary_lithium_token("PKCELL ER14505H") == "ER14505H"
    assert MODULE.primary_lithium_token("PKCELL ER14505M") == "ER14505M"
    assert MODULE.primary_lithium_token("PKCELL CR14505") == "CR14505"
    assert MODULE.primary_lithium_token("PKCELL ER 14505 M") == "ER14505M"
    assert MODULE.primary_lithium_token("PKCELL ER14505M and CR14505") is None


def test_aa_2800_claim_is_blocked_by_official_page_conflict():
    name = "Аккумулятор Ni-MH PKCELL AA/R06 2800mAh"
    assert MODULE.model_core(name) == "R06"
    assert MODULE.blocked_reason(name) == "official_AA_page_caps_range_at_2700mAh_but_queue_claims_2800mAh"


def test_pack_retail_and_rtu_signals_are_separate():
    assert MODULE.execution_signals("10*Ni-MH PKCELL AA/R06 2800mAh") == ["electrical_pack:10_cells"]
    assert MODULE.execution_signals("Ni-MH 6ХPKCELL AAA/R03 1000mAh (п4)") == [
        "electrical_pack:6_cells",
        "retail_pack:4_pieces",
    ]
    assert MODULE.execution_signals("Ni-MH PKCELL RTU R03 1000mAh (4BL)") == [
        "retail_pack:4_pieces",
        "RTU",
    ]


def test_product_row_contains_only_generic_aaa_facts():
    row = MODULE.product_row(source_row("3Ni-MH PKCELL AAA/R03 1000mAh 3.6V"))
    assert row["identity_scope"] == "model_core"
    assert row["model_core"] == "R03"
    assert row["identity_evidence"] == {
        "model_core_token": "R03",
        "required_brand_token": "PKCELL",
        "required_chemistry_token": "Ni-MH",
    }
    assert row["unverified_execution_signals"] == ["electrical_pack:3_cells"]
    serialized = json.dumps(row["technical_attributes"], ensure_ascii=False).lower()
    assert "1000 ма·ч" in serialized
    assert "конкретное исполнение" in serialized
    assert "3,6 в" not in serialized
    assert set(row["technical_attributes"]) == MODULE.ALLOWED_ATTRIBUTE_KEYS
    for name in (
        "Ni-MH OTHER R03 1000mAh",
        "Ni-Cd PKCELL R03 1000mAh",
        "Ni-MH PKCELL R06 2800mAh",
    ):
        with pytest.raises(RuntimeError, match="identity guard"):
            MODULE.product_row(source_row(name))


def test_payload_separates_safe_and_blocked_rows():
    payload = MODULE.build_payload(
        [
            source_row("3Ni-MH PKCELL AAA/R03 1000mAh 3.6V", "КА-1"),
            source_row("Ni-MH PKCELL AA/R06 2800mAh", "КА-2"),
            source_row("PKCELL ER14505M 3.6V", "КА-3"),
            source_row("FANSO ER14505H", "КА-4"),
        ],
        expected=1,
    )
    assert [row["external_id"] for row in payload["products"]] == ["КА-1"]
    assert [row["external_id"] for row in payload["blocked_rows"]] == ["КА-2", "КА-3"]
    assert payload["blocked_rows"][1]["primary_lithium_token"] == "ER14505M"


def test_guards_category_duplicate_ids_and_expected_count():
    wrong_category = source_row("Ni-MH PKCELL AAA/R03 1000mAh")
    wrong_category["category_external_id"] = "seo:batteries-ups"
    with pytest.raises(RuntimeError, match="escaped primary-cells"):
        MODULE.build_payload([wrong_category], expected=1)

    with pytest.raises(RuntimeError, match="duplicate external IDs"):
        MODULE.build_payload(
            [
                source_row("Ni-MH PKCELL AAA/R03 1000mAh", "КА-DUP"),
                source_row("Ni-MH PKCELL R03 1000mAh", "КА-DUP"),
            ],
            expected=2,
        )

    with pytest.raises(RuntimeError, match="Expected 2 safe PKCELL rows, got 1"):
        MODULE.build_payload([source_row("Ni-MH PKCELL AAA/R03 1000mAh")], expected=2)


def test_serializes_unescaped_utf8_without_bom():
    payload = MODULE.build_payload([source_row("Ni-MH PKCELL AAA/R03 1000mAh")], expected=1)
    raw = MODULE.serialize_payload(payload)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert "Никель".encode("utf-8") in raw
    assert b"\\u041d" not in raw
    assert json.loads(raw.decode("utf-8"))["products"][0]["manufacturer"] == "PKCELL"
