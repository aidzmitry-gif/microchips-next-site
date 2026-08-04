from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave242c-official-image-audit.py"
GENERATED = ROOT / "docs/audits/generated"
LEDGER = GENERATED / "rb-wave242c-official-image-ledger.csv"
INDEX = GENERATED / "rb-wave242c-official-image-candidate-index.csv"
SUMMARY = GENERATED / "rb-wave242c-official-image-audit.summary.json"
PROMOTION = ROOT / "docs/imports/rb-official-exact-media-wave242c-2026-07-29.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture(scope="module", autouse=True)
def build() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)


def test_scope_is_exactly_the_wave241_manifest() -> None:
    ledger = rows(LEDGER)
    assert len(ledger) == 44
    assert len({row["product_external_id"] for row in ledger}) == 44
    assert {row["decision"] for row in ledger} == {"HOLD"}
    assert {row["promotion_eligible"] for row in ledger} == {"false"}
    assert {row["prior_legacy_decision"] for row in ledger} == {"HOLD"}
    assert not PROMOTION.exists()


def test_rights_and_visual_gates_fail_closed() -> None:
    ledger = rows(LEDGER)
    assert {row["rights_status"] for row in ledger} == {"NO_DOCUMENTED_REUSE_PERMISSION"}
    counts: dict[str, int] = {}
    for row in ledger:
        counts[row["visual_identity_status"]] = counts.get(row["visual_identity_status"], 0) + 1
    assert counts == {
        "EXACT_MODEL_DOCUMENT_PAGE_ONLY": 4,
        "EXACT_PAGE_ASSOCIATION_WITHOUT_VISIBLE_MPN": 3,
        "NOT_EXACT_FAMILY_OR_SELECTION_TABLE": 35,
        "NOT_EXACT_SHARED_OFFICIAL_RASTER": 2,
    }
    shared = {row["mpn"] for row in ledger if row["visual_identity_status"] == "NOT_EXACT_SHARED_OFFICIAL_RASTER"}
    assert shared == {"RBC17", "RBC40"}


def test_candidate_hashes_and_contact_sheets_are_pinned() -> None:
    candidates = rows(INDEX)
    assert len(candidates) == 37
    assert sum(row["candidate_kind"] == "official_pdf_page_render" for row in candidates) == 33
    assert sum(row["candidate_kind"] == "official_html_linked_raster" for row in candidates) == 4
    for row in candidates:
        local = ROOT / row["local_path"]
        sheet = ROOT / row["contact_sheet_path"]
        assert digest(local) == row["local_sha256"]
        assert digest(sheet) == row["contact_sheet_sha256"]
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert len(summary["candidate_evidence"]["contact_sheets"]) == 7


def test_rebuild_is_deterministic() -> None:
    before = {path: digest(path) for path in (LEDGER, INDEX, SUMMARY)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True, text=True)
    after = {path: digest(path) for path in (LEDGER, INDEX, SUMMARY)}
    assert after == before
