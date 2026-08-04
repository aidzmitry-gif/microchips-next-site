from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "build-rb-delta-wave198-preparation.py"
SPEC = importlib.util.spec_from_file_location("delta_wave198", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(external_id: str, model: str, **overrides: str) -> dict[str, str]:
    value = {
        "external_id": external_id,
        "name": f"Аккумулятор Delta {model} (AGM, 7Ah)",
        "category_external_id": "seo:batteries-ups",
        "transfer_status": "legacy_only_draft_candidate",
        "identity_candidate_status": "none",
        "has_primary_exact_description": "false",
    }
    value.update(overrides)
    return value


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def workspace_tmp() -> Path:
    path = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-delta-wave198-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    return path


def run_build(
    source: Path,
    output: Path,
    contract: Path,
    expected_records: int,
    evidence: Path | None = None,
    *,
    snapshot_sha256: str | None = None,
) -> dict[str, object]:
    return MODULE.build(
        source,
        output,
        contract,
        expected_records,
        evidence,
        identity_snapshot_id="test-query@run-763",
        identity_snapshot_sha256=snapshot_sha256 or hashlib.sha256(source.read_bytes()).hexdigest(),
    )


def evidence_row(root: Path, model: str, external_id: str = "bitrix:0") -> dict[str, str]:
    snapshot = root / (MODULE.compact(model) + ".html")
    snapshot.write_text(f"<h1>DELTA {model}</h1>", encoding="utf-8")
    return {
        "external_id": external_id,
        "model": model,
        "source_url": f"https://www.delta-batt.com/products/{MODULE.compact(model)}/",
        "source_snapshot_path": snapshot.name,
        "source_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "content_model_key": MODULE.compact(model),
        "voltage_v": "12",
        "capacity_ah": "7",
        "evidence_kind": "exact_product_page",
        "publisher": "DELTA Battery / ENERGON",
        "safe_to_apply": "false",
    }


def test_selection_excludes_all_ct_forms_identity_and_duplicate_model_holds() -> None:
    rows = [row(f"bitrix:{i}", f"DTM {i}") for i in range(130)]
    rows += [
        row("bitrix:ct-space", "CT 1207"),
        row("bitrix:ct-tight", "CT1208"),
        row("bitrix:ct-hyphen", "CT-1209"),
        row("bitrix:ct-nbsp", "CT\u00a01210"),
        row("bitrix:one-c", "HR 12-7", identity_candidate_status="pending"),
        row("bitrix:dup-a", "DT 12008 (T9)"),
        row("bitrix:dup-b", "DT 12008 (T13)"),
    ]
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "input.csv"
        write(source, rows)
        out, contract = tmp_path / "out.csv", tmp_path / "contract.json"
        summary = run_build(source, out, contract, 137)
        candidates = list(csv.DictReader(out.open(encoding="utf-8-sig", newline="")))
        assert len(candidates) == 130
        assert all(item["safe_to_apply"] == "false" for item in candidates)
        assert summary["excluded_counts"] == {
            "duplicate_base_model_hold": 2,
            "identity_candidate_or_one_c_link": 1,
            "motorcycle_or_unparseable_model": 4,
        }
    finally:
        shutil.rmtree(tmp_path)


def test_duplicate_hold_is_global_before_enrichment_eligibility() -> None:
    rows = [row(f"bitrix:{i}", f"DTM {i}") for i in range(130)]
    rows += [row("bitrix:dup-clear", "HR 12-7"), row("bitrix:dup-enriched", "HR 12-7", has_primary_exact_description="true")]
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "input.csv"
        write(source, rows)
        summary = run_build(source, tmp_path / "out.csv", tmp_path / "contract.json", 132)
        assert summary["candidate_records"] == 130
        assert summary["excluded_counts"] == {"duplicate_base_model_hold": 2}
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("identity_candidate_status", "", "identity_candidate_status must be explicit"),
        ("has_primary_exact_description", "unknown", "must be explicitly true or false"),
    ],
)
def test_identity_and_boolean_snapshot_fields_fail_closed(field: str, value: str, message: str) -> None:
    rows = [row(f"bitrix:{i}", f"DTM {i}") for i in range(130)]
    rows[0][field] = value
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "input.csv"
        write(source, rows)
        with pytest.raises(ValueError, match=message):
            run_build(source, tmp_path / "out.csv", tmp_path / "contract.json", 130)
    finally:
        shutil.rmtree(tmp_path)


def test_identity_snapshot_sha256_is_pinned() -> None:
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "input.csv"
        write(source, [row(f"bitrix:{i}", f"DTM {i}") for i in range(130)])
        with pytest.raises(ValueError, match="identity snapshot SHA-256"):
            run_build(source, tmp_path / "out.csv", tmp_path / "contract.json", 130, snapshot_sha256="0" * 64)
    finally:
        shutil.rmtree(tmp_path)


def test_decimal_model_key_does_not_match_integer_model_evidence() -> None:
    rows = [row("bitrix:0", "HR 12-4.5")] + [row(f"bitrix:{i}", f"DTM {i}") for i in range(1, 130)]
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "input.csv"
        write(source, rows)
        evidence = tmp_path / "evidence.csv"
        write(evidence, [evidence_row(tmp_path, "HR 12-45")])
        assert MODULE.compact("HR 12-4.5") != MODULE.compact("HR 12-45")
        with pytest.raises(ValueError, match="outside the eligible snapshot"):
            run_build(source, tmp_path / "out.csv", tmp_path / "contract.json", 130, evidence)
    finally:
        shutil.rmtree(tmp_path)


def test_extractor_evidence_is_pinned_and_contract_hashes_all_artifacts() -> None:
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "input.csv"
        write(source, [row(f"bitrix:{i}", f"HR {i}") for i in range(130)])
        evidence = tmp_path / "evidence.csv"
        write(evidence, [evidence_row(tmp_path, "HR 0")])
        output, contract = tmp_path / "out.csv", tmp_path / "contract.json"
        summary = run_build(source, output, contract, 130, evidence)
        persisted = json.loads(contract.read_text(encoding="utf-8"))
        assert summary["official_exact_matches"] == 1
        assert summary["source_acquisition_required"] == 129
        assert summary["official_evidence_sha256"] == hashlib.sha256(evidence.read_bytes()).hexdigest()
        assert summary["output_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
        assert persisted == summary
    finally:
        shutil.rmtree(tmp_path)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"publisher": ""}, "publisher must be"),
        ({"source_url": "https://www.delta-batt.com/catalog/"}, "path is not valid"),
        ({"source_sha256": "0" * 64}, "snapshot SHA-256 mismatch"),
        ({"content_model_key": "hr999"}, "content_model_key"),
    ],
)
def test_unpinned_or_non_exact_evidence_is_rejected(override: dict[str, str], message: str) -> None:
    tmp_path = workspace_tmp()
    try:
        source = tmp_path / "input.csv"
        write(source, [row(f"bitrix:{i}", f"HR {i}") for i in range(130)])
        evidence = tmp_path / "evidence.csv"
        item = evidence_row(tmp_path, "HR 0")
        item.update(override)
        write(evidence, [item])
        with pytest.raises(ValueError, match=message):
            run_build(source, tmp_path / "out.csv", tmp_path / "contract.json", 130, evidence)
    finally:
        shutil.rmtree(tmp_path)
