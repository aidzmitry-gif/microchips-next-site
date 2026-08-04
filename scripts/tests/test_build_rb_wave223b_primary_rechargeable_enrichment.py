from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
SCRIPT = ROOT / "scripts/build-rb-wave223b-primary-rechargeable-enrichment.py"
EVIDENCE = GEN / "rb-wave223b-primary-rechargeable-evidence.csv"
HOLDS = GEN / "rb-wave223b-primary-rechargeable-holds.csv"
GROUPS = GEN / "rb-wave223b-primary-rechargeable-model-core-groups.csv"
SUMMARY = GEN / "rb-wave223b-primary-rechargeable.summary.json"
MANIFEST = ROOT / "docs/imports/rb-source-backed-description-candidates-wave223b-2026-07-29.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_wave223b_is_deterministic_and_complete() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(digest(path) for path in (EVIDENCE, HOLDS, GROUPS, SUMMARY, MANIFEST))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(digest(path) for path in (EVIDENCE, HOLDS, GROUPS, SUMMARY, MANIFEST))
    evidence, holds = read_csv(EVIDENCE), read_csv(HOLDS)
    assert len(evidence) + len(holds) == 300
    assert len({row["product_external_id"] for row in evidence + holds}) == 300
    assert summary_priority_range(evidence + holds) == (631, 930)


def summary_priority_range(rows: list[dict[str, str]]) -> tuple[int, int]:
    priorities = [int(row["priority"]) for row in rows]
    return min(priorities), max(priorities)


def test_wave223b_evidence_and_safety_contract() -> None:
    evidence, holds, groups = read_csv(EVIDENCE), read_csv(HOLDS), read_csv(GROUPS)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(evidence) == len(manifest["products"]) == summary["coverage"]["exact_primary_source_candidates"]
    assert len(holds) == summary["coverage"]["holds"]
    assert len(groups) == summary["coverage"]["manufacturer_model_core_groups"]
    assert summary["selection"]["priority_first"] == 631
    assert summary["selection"]["priority_last"] == 930
    assert summary["selection"]["category_counts"] == {"seo:primary-cells": 300}
    assert summary["selection"]["wave223a_category_overlap"] is False
    assert summary["safety"] == {"database_operations": 0, "apply_performed": False, "price_changes": 0, "stock_changes": 0, "identity_changes": 0, "media_changes": 0, "publication_changes": 0, "url_changes": 0}
    assert all(row["partition"] == "exact_primary_source_candidate" and row["safe_to_apply"] == "false" for row in evidence)
    assert all(row["safe_to_apply"] == "false" and row["hold_reason"] for row in holds)
    assert all(item["apply_intent"] is False and item["evidence_scope"] == "exact_external_id_and_model_core" for item in manifest["products"])
    assert Counter(row["hold_reason"] for row in holds) == {
        "no_exact_primary_manufacturer_source_with_model_core": 2,
        "exact_source_lacks_verified_model_core_or_official_manufacturer_host": 4,
    }
