import csv
import importlib.util
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "merge-rb-research-holds.py"
SPEC = importlib.util.spec_from_file_location("merge_rb_holds", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_merges_duplicate_cluster_evidence(tmp_path: Path) -> None:
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    output = tmp_path / "merged.csv"
    write(first, [{"cluster_id": "brand:model", "decision": "hold", "evidence": "one", "retry_condition": "retry one"}])
    write(second, [{"cluster_id": "brand:model", "decision": "hold", "evidence_summary": "two", "retry_condition": "retry two"}])
    summary = MODULE.merge([first, second], output)
    rows = list(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert summary["source_rows"] == 2
    assert summary["unique_hold_clusters"] == 1
    assert rows[0]["evidence"] == "one || two"
    assert rows[0]["retry_condition"] == "retry one || retry two"


def test_rejects_non_hold_decision(tmp_path: Path) -> None:
    source = tmp_path / "bad.csv"
    write(source, [{"cluster_id": "brand:model", "decision": "apply", "evidence": "x", "retry_condition": "y"}])
    with pytest.raises(ValueError, match="Unsupported"):
        MODULE.merge([source], tmp_path / "out.csv")
