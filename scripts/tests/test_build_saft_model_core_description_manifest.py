import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "build-saft-model-core-description-manifest.py"
SPEC = importlib.util.spec_from_file_location("build_saft_manifest", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_maps_model_core_without_collapsing_connector_variant():
    assert MODULE.model_core("LS 14500 CNA (SAFT) элемент") == "LS14500"
    assert MODULE.model_core("LS 17330 CNR (SAFT) элемент") == "LS17330"
    assert MODULE.model_core("LSH20 E-STD (SAFT) элемент") == "LSH20"


def test_blocks_assemblies_and_different_datasheet_variants():
    assert MODULE.model_core("2LS 17500 SAFT 7,2V сборка") is None
    assert MODULE.model_core("LSH20 (SAFT) сборка 4шт") is None
    assert MODULE.model_core("LSH20 HTS SAFT") is None
    assert MODULE.model_core("LSH20-150 SAFT") is None
    assert MODULE.model_core("LS26500plus SAFT") is None


def test_generated_fact_labels_are_explicitly_per_cell():
    row = MODULE.product_row(
        {"product_external_id": "КА-TEST", "name": "LS14500 комплект-5шт SAFT"},
        "LS14500",
    )
    assert row["identity_scope"] == "model_core"
    assert "mpn" not in row
    attributes = row["technical_attributes"]
    assert attributes["Номинальное напряжение одного элемента"] == "3,6 В"
    assert "Типичная ёмкость одного элемента" in attributes
    assert "разъём" in attributes["Ограничение источника"]
