from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).parents[2]
REGISTRY = ROOT / "docs" / "audits" / "generated" / "wave201-cameron-sino-source-registry.csv"
HOLDS = ROOT / "docs" / "audits" / "generated" / "wave201-cameron-sino-holds.csv"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_every_cameron_sino_candidate_is_held_and_never_apply_safe() -> None:
    holds = read(HOLDS)
    assert len(holds) == 12
    assert len({row["product_external_id"] for row in holds}) == 12
    assert all(row["safe_to_apply"] == "false" and row["hold_reason"] for row in holds)


def test_primary_and_secondary_evidence_are_not_equated_and_mc950_conflict_is_held() -> None:
    registry = read(REGISTRY)
    assert all(row["safe_to_apply"] == "false" for row in registry)
    assert any(row["evidence_tier"] == "manufacturer_primary" for row in registry)
    assert any(row["evidence_tier"] == "secondary_dealer" for row in registry)
    mc950 = [row for row in read(HOLDS) if row["model_token"] == "CS-MC950BL"]
    assert len(mc950) == 4
    assert all("capacity_conflict" in row["hold_reason"] for row in mc950)
