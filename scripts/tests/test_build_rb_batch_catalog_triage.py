import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-rb-batch-catalog-triage.py"
SPEC = importlib.util.spec_from_file_location("rb_batch_triage", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(external_id: str, name: str, **overrides: str) -> dict[str, str]:
    value = {
        "priority": "1",
        "product_external_id": external_id,
        "name": name,
        "sku": "",
        "mpn": "",
        "manufacturer": "",
        "category_external_id": "seo:primary-cells",
        "category_name": "Первичные элементы",
        "has_applied_description": "false",
        "has_verified_published_image": "false",
        "completion_gap_count": "2",
        "identity_fields_present": "0",
        "is_published": "false",
        "research_status": "pending_official_source_research",
    }
    value.update(overrides)
    return value


def test_model_normalization_preserves_plus_and_suffix():
    assert MODULE.model_key("Save+") != MODULE.model_key("Save")
    assert MODULE.model_key("SURT192RMXLBP-CH").endswith("CH")


def test_explicit_units_only_and_decimal_is_preserved():
    facts = MODULE.explicit_facts("Delta 12V, 1.2 Ah")
    assert facts["voltage_candidates"] == "12"
    assert facts["capacity_candidates"] == "1.2"
    assert MODULE.explicit_facts("модель 6-FM-120")["voltage_candidates"] == ""


def test_model_extractor_prefers_product_model_over_pack_wording():
    assert MODULE.extract_model_from_name("LS 33600 (комплект-2шт) (SAFT)", "Saft") == "LS 33600"


def test_primary_cell_stays_in_scope_but_electronics_do_not():
    assert MODULE.out_of_scope_reason("Элемент питания Panasonic CR2032") == ""
    assert MODULE.out_of_scope_reason("Резистор 10 кОм") == "electronic_component"
    assert MODULE.out_of_scope_reason("Смазка силиконовая") == "non_product_material"


def test_battery_connector_variants_are_not_installation_parts():
    assert MODULE.out_of_scope_reason("Батарея литиевая CR17335-SE разъем PHR-2") == ""
    assert MODULE.out_of_scope_reason("Элемент питания CR2450-MF с разъем JST ZH 1.5 2 pin") == ""


def test_batch_outputs_candidates_without_applying():
    tmp_path = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-rb-batch-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True)
    rows = [
        row("A", "Аккумулятор APC SURT192RMXLBP-CH", manufacturer="APC", mpn="SURT192RMXLBP-CH", has_applied_description="true"),
        row("B", "APC SURT192RMXLBP-CH", manufacturer="APC", mpn="SURT192RMXLBP-CH"),
        row("C", "Элемент питания Panasonic CR2032"),
        row("D", "Дисплей OLED 0.96"),
        row("E", "Безымянный аккумулятор 12 В 7 А·ч"),
    ]
    source = tmp_path / "queue.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    try:
        summary = MODULE.build(source, tmp_path, "result")
        assert summary["total_rows"] == 5
        assert summary["automatic_database_mutations"] == 0
        assert summary["duplicate_candidate_pairs"] == 1
        assert summary["exact_duplicate_candidate_pairs"] == 1
        assert summary["out_of_scope_candidates"] == 1

        duplicates = list(csv.DictReader((tmp_path / "result-duplicate-candidates.csv").open(encoding="utf-8-sig")))
        assert duplicates[0]["survivor_external_id"] == "A"
        assert duplicates[0]["safe_to_apply"] == "false"

        triage = list(csv.DictReader((tmp_path / "result-all.csv").open(encoding="utf-8-sig")))
        statuses = {item["product_external_id"]: item["triage_status"] for item in triage}
        assert statuses["C"] == "identity_candidate_needs_primary_source"
        assert statuses["D"] == "out_of_scope_candidate"
        assert statuses["E"] == "hold_missing_identity"

        payload = json.loads((tmp_path / "result-summary.json").read_text(encoding="utf-8"))
        assert payload["unique_external_ids"] == 5
    finally:
        shutil.rmtree(tmp_path)


def test_prior_hold_registry_suppresses_only_research_clusters():
    tmp_path = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-rb-batch-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True)
    rows = [
        row("A", "APC SURT192RMXLBP-CH", manufacturer="APC", mpn="SURT192RMXLBP-CH"),
        row("B", "Energizer Industrial EN91", manufacturer="Energizer", mpn="EN91"),
        row("C", "Unknown battery 12 V"),
    ]
    source = tmp_path / "queue.csv"
    registry = tmp_path / "prior-decisions.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with registry.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["cluster_id", "decision"])
        writer.writeheader()
        writer.writerow({"cluster_id": "apc:SURT192RMXLBPCH", "decision": "hold"})

    try:
        summary = MODULE.build(source, tmp_path, "result", registry)
        research = list(csv.DictReader((tmp_path / "result-research-clusters.csv").open(encoding="utf-8-sig")))
        held_members = list(csv.DictReader((tmp_path / "result-known-hold-members.csv").open(encoding="utf-8-sig")))
        triage = list(csv.DictReader((tmp_path / "result-all.csv").open(encoding="utf-8-sig")))
        assert [item["cluster_id"] for item in research] == ["energizer:EN91"]
        assert {item["product_external_id"] for item in triage} == {"A", "B", "C"}
        held_by_external_id = {item["product_external_id"]: item for item in held_members}
        assert held_by_external_id == {
            "A": {
                "product_external_id": "A",
                "cluster_id": "apc:SURT192RMXLBPCH",
                "manufacturer_candidate": "APC",
                "model_candidate": "SURT192RMXLBP-CH",
                "decision": "hold",
                "hold_source": "prior_decision_cluster",
                "hold_reason": "prior_registry_decision",
                "safe_to_apply": "false",
            },
            "C": {
                "product_external_id": "C",
                "cluster_id": "",
                "manufacturer_candidate": "",
                "model_candidate": "",
                "decision": "hold",
                "hold_source": "missing_identity",
                "hold_reason": "manufacturer_or_stable_model_missing",
                "safe_to_apply": "false",
            },
        }
        assert summary["known_hold_clusters"] == 1
        assert summary["known_hold_cluster_member_records"] == 1
        assert summary["missing_identity_hold_records"] == 1
        assert summary["known_hold_member_records"] == 2
        assert summary["prior_decision_registry_known_holds"] == 1
    finally:
        shutil.rmtree(tmp_path)


def test_prior_hold_registry_missing_or_malformed_decision_fails_closed():
    tmp_path = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-rb-batch-{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True)
    registry = tmp_path / "prior-decisions.csv"
    try:
        registry.write_text("cluster_id,decision\napc:SURT192RMXLBPCH,\n", encoding="utf-8-sig")
        try:
            MODULE.load_known_hold_cluster_ids(registry)
            assert False, "missing decision must fail closed"
        except ValueError as error:
            assert "missing decision" in str(error)

        registry.write_text("cluster_id,decision\napc:SURT192RMXLBPCH,merge\n", encoding="utf-8-sig")
        try:
            MODULE.load_known_hold_cluster_ids(registry)
            assert False, "unsupported decision must fail closed"
        except ValueError as error:
            assert "unsupported decision" in str(error)
    finally:
        shutil.rmtree(tmp_path)
