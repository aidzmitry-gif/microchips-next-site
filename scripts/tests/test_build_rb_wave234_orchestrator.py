from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave234-orchestrator.py"
GEN = ROOT / "docs/audits/generated"
VERIFY = GEN / "rb-wave234-orchestration.verification.json"
OUTPUTS = (
    GEN / "rb-wave234-a-panasonic-mnb.csv",
    GEN / "rb-wave234-b-apc-enersys.csv",
    GEN / "rb-wave234-c-remaining-ups-batteries.csv",
    GEN / "rb-wave234-prior-reviewed-wave233.csv",
    GEN / "rb-wave234-non-b2b-exclusions.csv",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave234_is_deterministic_complete_and_disjoint() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(sha256(path) for path in (*OUTPUTS, VERIFY))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(sha256(path) for path in (*OUTPUTS, VERIFY))
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert verify["input"]["rows"] == verify["input"]["unique_ids"] == 611
    assert verify["partition"] == {
        "b2b_ups_batteries": 553,
        "prior_wave233_reviewed": 389,
        "lane_a_panasonic_mnb": 56,
        "lane_b_apc_enersys": 34,
        "lane_c_remaining": 74,
        "non_b2b_excluded": 58,
        "overlap_ids": [],
        "unpartitioned_ids": [],
    }
    datasets = [rows(path) for path in OUTPUTS]
    assert [len(data) for data in datasets] == [56, 34, 74, 389, 58]
    id_sets = [{row["external_id"] for row in data} for data in datasets]
    assert all(len(data) == len(ids) for data, ids in zip(datasets, id_sets, strict=True))
    assert not any(id_sets[left] & id_sets[right] for left in range(len(id_sets)) for right in range(left + 1, len(id_sets)))
    assert len(set().union(*id_sets)) == 611
    assert all(row["category_external_id"] == "seo:batteries-ups" for data in datasets[:3] for row in data)
    assert verify["policy"] == {"database_queries": 0, "database_mutations": 0, "network_requests": 0, "commercial_changes": 0, "publication_changes": 0}
