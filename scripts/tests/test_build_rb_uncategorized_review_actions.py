import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "build-rb-uncategorized-review-actions.py"
SPEC = importlib.util.spec_from_file_location("uncategorized_review_actions", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


FIELDS = [
    "site_id", "product_external_id", "name", "manufacturer", "mpn", "is_published",
    "decision", "target_category", "reason",
]


def row(external_id: str, decision: str, category: str = "", published: str = "f") -> dict[str, str]:
    return {
        "site_id": "microchips-by",
        "product_external_id": external_id,
        "name": f"Product {external_id}",
        "manufacturer": "",
        "mpn": "",
        "is_published": published,
        "decision": decision,
        "target_category": category,
        "reason": "test reason",
    }


def write_review(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_builds_expected_action_manifests(tmp_path: Path):
    review = tmp_path / "review.csv"
    write_review(review, [
        row("A", "existing_leaf_candidate", "seo:primary-cells"),
        row("B", "electronics_defer"),
        row("C", "obvious_nonprofile"),
        row("D", "hold"),
    ])

    summary = MODULE.build(review, tmp_path, "result")
    assert summary["assignment_candidates"] == 1
    assert summary["exclusion_candidates"] == 2
    assert summary["hold_candidates"] == 1
    assert summary["automatic_database_mutations"] == 0

    assignments = list(csv.DictReader((tmp_path / "result-assignments.csv").open(encoding="utf-8-sig")))
    exclusions = list(csv.DictReader((tmp_path / "result-exclusions.csv").open(encoding="utf-8-sig")))
    holds = list(csv.DictReader((tmp_path / "result-holds.csv").open(encoding="utf-8-sig")))
    assert assignments == [{"product_external_id": "A", "category_external_id": "seo:primary-cells"}]
    assert {item["product_external_id"] for item in exclusions} == {"B", "C"}
    assert holds == [{"product_external_id": "D", "reason": "test reason"}]
    assert json.loads((tmp_path / "result-summary.json").read_text(encoding="utf-8"))["total_rows"] == 4


@pytest.mark.parametrize("mutator, expected", [
    (lambda rows: rows.__setitem__(1, row("A", "hold")), "duplicates product_external_id"),
    (lambda rows: rows.__setitem__(0, row("A", "unknown")), "unsupported decision"),
    (lambda rows: rows.__setitem__(0, row("A", "existing_leaf_candidate")), "no target_category"),
    (lambda rows: rows.__setitem__(0, row("A", "hold", "seo:primary-cells")), "Non-leaf decision"),
    (lambda rows: rows.__setitem__(0, row("A", "existing_leaf_candidate", "battery/root")), "Unsafe target_category"),
    (lambda rows: rows.__setitem__(1, row("B", "electronics_defer", published="t")), "Refusing exclusion of published"),
])
def test_fails_closed_for_unsafe_review(tmp_path: Path, mutator, expected: str):
    review = tmp_path / "review.csv"
    rows = [row("A", "existing_leaf_candidate", "seo:primary-cells"), row("B", "hold")]
    mutator(rows)
    write_review(review, rows)
    with pytest.raises(ValueError, match=expected):
        MODULE.build(review, tmp_path / "out", "result")
