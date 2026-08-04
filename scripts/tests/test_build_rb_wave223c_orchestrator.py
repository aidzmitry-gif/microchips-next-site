from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
VERIFY = GEN / "rb-enrichment-queue-wave223c.verification.json"
QUEUES = [
    GEN / "rb-enrichment-queue-wave223c-a-ups-industrial.csv",
    GEN / "rb-enrichment-queue-wave223c-b-primary-rechargeable.csv",
    GEN / "rb-enrichment-queue-wave223c-c-other-b2b.csv",
]
REMAINDER = GEN / "rb-enrichment-queue-wave223c-remainder.csv"
EXCLUSIONS = GEN / "rb-enrichment-queue-wave223c-exclusions.csv"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_wave223c_validates_and_partitions_the_pinned_wave222_queue() -> None:
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert verify["input"]["rows"] == verify["input"]["unique_ids"] == 1554
    assert verify["input"]["deterministic_priority_sequence"] is True
    assert verify["input"]["excluded_irrelevant_categories_present"] == []
    assert verify["exclusions"] == {
        "wave220_historical_identity_research_input_overlap": 596,
        "wave220_applied15_input_overlap": 4,
        "rows": 596,
        "eligible_rows": 958,
        "path": "docs/audits/generated/rb-enrichment-queue-wave223c-exclusions.csv",
        "sha256": verify["exclusions"]["sha256"],
    }
    assert verify["partition"] == {"input_ids": 1554, "excluded_ids": 596, "eligible_ids": 958, "selected_ids": 632, "remainder_ids": 326, "queue_overlap_ids": [], "remainder_overlap_ids": [], "unpartitioned_eligible_ids": []}


def test_wave223c_lanes_are_disjoint_ordered_and_capped() -> None:
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    lane_rows = [rows(path) for path in QUEUES]
    lane_ids = [{row["product_external_id"] for row in lane} for lane in lane_rows]
    assert [len(lane) for lane in lane_rows] == [300, 300, 32]
    assert all(len(lane) == len(ids) for lane, ids in zip(lane_rows, lane_ids, strict=True))
    assert not lane_ids[0] & lane_ids[1] and not lane_ids[0] & lane_ids[2] and not lane_ids[1] & lane_ids[2]
    assert all([int(row["priority"]) for row in lane] == sorted(int(row["priority"]) for row in lane) for lane in lane_rows)
    assert set(row["category_external_id"] for row in lane_rows[0]) <= {"seo:batteries-ups", "seo:ups-systems", "seo:batteries-industrial"}
    assert set(row["category_external_id"] for row in lane_rows[1]) <= {"seo:primary-cells", "seo:rechargeable-cells"}
    assert verify["lanes"]["A"]["rows"] == verify["lanes"]["B"]["rows"] == 300
    assert verify["lanes"]["C"]["rows"] == 32


def test_wave223c_remainder_and_repeat_exclusions_are_explicit() -> None:
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    remainder = rows(REMAINDER)
    exclusions = rows(EXCLUSIONS)
    assert len(remainder) == 326 and {row["remainder_reason"] for row in remainder} == {"lane_capacity_reached"}
    assert len(exclusions) == len({row["product_external_id"] for row in exclusions}) == 596
    assert sum("wave220_applied_description" in row["exclusion_reasons"] for row in exclusions) == 4
    assert all("historical_identity_research_wave220" in row["exclusion_reasons"] for row in exclusions)
    assert all(verify["byte_identical_rerun"].values())
    assert verify["automatic_web_requests"] == verify["automatic_database_queries"] == verify["automatic_database_mutations"] == 0
    assert verify["apply_performed"] is False
