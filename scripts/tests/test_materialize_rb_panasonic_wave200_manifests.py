from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
EXTRACTOR_SCRIPT = ROOT / "scripts" / "extract-rb-panasonic-wave200-pdf-evidence.py"
MATERIALIZER_SCRIPT = ROOT / "scripts" / "materialize-rb-panasonic-wave200-manifests.py"


def load_module(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


EXTRACTOR = load_module("panasonic_pdf_extract_fixture", EXTRACTOR_SCRIPT)
MODULE = load_module("panasonic_materialize", MATERIALIZER_SCRIPT)
CANDIDATES = ROOT / "docs" / "audits" / "generated" / "rb-panasonic-wave200-candidates.csv"
PDF_DIR = ROOT / "docs" / "audits" / "sources" / "panasonic-wave200"


def temp() -> Path:
    root = ROOT / "docs" / "audits" / "generated" / f"test-panasonic-materialize-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def fixture(root: Path) -> dict[str, Path]:
    paths = {
        "evidence": root / "evidence.csv",
        "holds": root / "holds.csv",
        "evidence_summary": root / "evidence-summary.json",
        "descriptions": root / "descriptions.json",
        "materialization_summary": root / "materialization-summary.json",
    }
    EXTRACTOR.build(
        CANDIDATES,
        PDF_DIR / EXTRACTOR.COIN_FILENAME,
        PDF_DIR / EXTRACTOR.CYLINDRICAL_FILENAME,
        paths["evidence"],
        paths["holds"],
        paths["evidence_summary"],
        EXTRACTOR.sha(CANDIDATES),
    )
    return paths


def materialize(paths: dict[str, Path]) -> dict[str, object]:
    return MODULE.build(
        CANDIDATES,
        paths["evidence"],
        paths["holds"],
        paths["evidence_summary"],
        paths["descriptions"],
        paths["materialization_summary"],
        MODULE.sha(CANDIDATES),
        MODULE.sha(paths["evidence"]),
        MODULE.sha(paths["holds"]),
        MODULE.sha(paths["evidence_summary"]),
    )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_materializes_model_core_facts_without_forbidden_fields() -> None:
    root = temp()
    try:
        paths = fixture(root)
        summary = materialize(paths)
        products = json.loads(paths["descriptions"].read_text(encoding="utf-8"))["products"]
        by_id = {row["external_id"]: row for row in products}
        _, candidates = read_csv(CANDIDATES)
        external_id_by_model = {row["model_token"]: row["product_external_id"] for row in candidates}
        forbidden = {
            "display_name", "mpn", "price", "stock", "image", "indexability",
            "legacy_model_token", "legacy_pack_variant_key", "source_page", "source_snapshot_sha256",
        }

        assert summary["materialized_records"] == 125
        assert summary["hold_records"] == 28
        assert summary["partition_records"] == 153
        assert all(not (forbidden & set(row)) for row in products)
        cr2450 = by_id[external_id_by_model["CR2450/BS"]]
        assert cr2450["model_core"] == "CR2450"
        assert cr2450["identity_scope"] == "model_core"
        assert cr2450["evidence_scope"] == "model_core"
        assert cr2450["technical_attributes"]["Номинальная ёмкость"] == "620 мА·ч"
        assert by_id[external_id_by_model["BR2032/F2N"]]["technology"] == "Литий-поликарбонмонофторид"
        assert by_id[external_id_by_model["CR2032/F2N"]]["technology"] == "Литий-диоксид марганца"
    finally:
        shutil.rmtree(root)


def test_rejects_incomplete_evidence_hold_partition() -> None:
    root = temp()
    try:
        paths = fixture(root)
        fields, holds = read_csv(paths["holds"])
        write_csv(paths["holds"], fields, holds[:-1])
        with pytest.raises(ValueError, match="do not completely partition"):
            materialize(paths)
    finally:
        shutil.rmtree(root)


def test_rejects_false_longest_prefix_model_core() -> None:
    root = temp()
    try:
        paths = fixture(root)
        fields, evidence = read_csv(paths["evidence"])
        target = next(row for row in evidence if row["legacy_model_token"] == "CR2450/BS")
        target["model_core"] = "CR2450B"
        target["match_kind"] = "slash_package_variant"
        write_csv(paths["evidence"], fields, evidence)
        evidence_summary = json.loads(paths["evidence_summary"].read_text(encoding="utf-8"))
        evidence_summary["evidence_sha256"] = MODULE.sha(paths["evidence"])
        evidence_summary["matched_model_core_records"] = len(
            {MODULE.normalize_model(row["model_core"]) for row in evidence}
        )
        paths["evidence_summary"].write_text(
            json.dumps(evidence_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="invalid model-core boundary"):
            materialize(paths)
    finally:
        shutil.rmtree(root)


def test_rejects_summary_coverage_count_mismatch() -> None:
    root = temp()
    try:
        paths = fixture(root)
        evidence_summary = json.loads(paths["evidence_summary"].read_text(encoding="utf-8"))
        evidence_summary["evidence_records"] = 144
        paths["evidence_summary"].write_text(
            json.dumps(evidence_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="evidence_records mismatch"):
            materialize(paths)
    finally:
        shutil.rmtree(root)
