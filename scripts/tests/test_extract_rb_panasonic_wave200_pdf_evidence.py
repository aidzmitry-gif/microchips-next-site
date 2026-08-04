from __future__ import annotations

import csv
import importlib.util
import shutil
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "extract-rb-panasonic-wave200-pdf-evidence.py"
SPEC = importlib.util.spec_from_file_location("panasonic_pdf_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CANDIDATES = ROOT / "docs" / "audits" / "generated" / "rb-panasonic-wave200-candidates.csv"
PDF_DIR = ROOT / "docs" / "audits" / "sources" / "panasonic-wave200"


def temp() -> Path:
    root = ROOT / "docs" / "audits" / "generated" / f"test-panasonic-pdf-evidence-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def extract(root: Path) -> dict[str, object]:
    return MODULE.build(
        CANDIDATES,
        PDF_DIR / MODULE.COIN_FILENAME,
        PDF_DIR / MODULE.CYLINDRICAL_FILENAME,
        root / "evidence.csv",
        root / "holds.csv",
        root / "summary.json",
        MODULE.sha(CANDIDATES),
    )


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_extracts_real_pinned_tables_with_honest_partition() -> None:
    root = temp()
    try:
        summary = extract(root)
        evidence = rows(root / "evidence.csv")
        holds = rows(root / "holds.csv")
        evidence_by_model = {row["legacy_model_token"]: row for row in evidence}
        held_models = {row["legacy_model_token"] for row in holds}

        assert summary["candidate_records"] == 153
        assert summary["evidence_records"] == 125
        assert summary["hold_records"] == 28
        assert summary["partition_records"] == 153
        assert summary["matched_model_core_records"] == 28
        assert summary["pinned_table_core_records"] == 51
        assert summary["live_identity_hold_records"] == 18
        assert summary["unmatched_model_core_hold_records"] == 10
        assert set(MODULE.LIVE_IDENTITY_HOLDS) <= {row["product_external_id"] for row in holds}
        assert {"CR2430", "CR2032L/F1N", "BR2450A/FAN", "BR2450A/HAN"} <= held_models
        assert evidence_by_model["CR2450/BS"]["model_core"] == "CR2450"
        assert evidence_by_model["CR2450/BS"]["capacity_mah"] == "620"
        assert evidence_by_model["CR2450/BS"]["temperature_min_c"] == "-30"
        assert evidence_by_model["CR2450/BS"]["legacy_pack_variant_key"] == "Батарейка Panasonic CR2450/BS"
    finally:
        shutil.rmtree(root)


def test_rejects_unpinned_pdf_hash() -> None:
    root = temp()
    try:
        bad_coin = root / MODULE.COIN_FILENAME
        bad_coin.write_bytes(b"tampered PDF")
        with pytest.raises(ValueError, match="pinned PDF SHA-256 mismatch"):
            MODULE.build(
                CANDIDATES,
                bad_coin,
                PDF_DIR / MODULE.CYLINDRICAL_FILENAME,
                root / "evidence.csv",
                root / "holds.csv",
                root / "summary.json",
                MODULE.sha(CANDIDATES),
            )
    finally:
        shutil.rmtree(root)


def test_rejects_ambiguous_normalized_model_cores() -> None:
    with pytest.raises(ValueError, match="ambiguous normalized model core"):
        MODULE.build_core_index([
            {"model_core": "CR-2", "normalized_model_core": "CR2"},
            {"model_core": "CR2", "normalized_model_core": "CR2"},
        ])


def test_delimiter_aware_matching_blocks_prefix_traps() -> None:
    core_index = MODULE.build_core_index([
        {"model_core": model, "normalized_model_core": MODULE.normalize_model(model)}
        for model in ("CR2", "CR2032", "CR2450", "CR2450B")
    ])
    assert MODULE.match_model_core("CR2430", core_index) is None
    assert MODULE.match_model_core("CR2032L/F1N", core_index) is None
    match = MODULE.match_model_core("CR2450/BS", core_index)
    assert match is not None
    assert match[0]["model_core"] == "CR2450"
    assert match[1] == "slash_package_variant"


def test_only_explicit_attached_suffixes_are_accepted() -> None:
    core_index = MODULE.build_core_index([
        {"model_core": "CR123A", "normalized_model_core": "CR123A"},
    ])
    accepted = MODULE.match_model_core("CR123APE/BN", core_index)
    assert accepted is not None and accepted[1] == "whitelisted_attached_suffix"
    assert MODULE.match_model_core("CR123AX/BN", core_index) is None
