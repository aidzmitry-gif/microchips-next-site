from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("wave242_queue", ROOT / "scripts/build-rb-wave242-queue.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_rollover_preserves_no_repeat_membership_and_refreshes_live_state():
    previous_path = ROOT / "docs/audits/generated/rb-enrichment-queue-wave241.csv"
    full_path = ROOT / ".tmp/rb-enrichment-queue-wave242-full.csv"
    previous = MODULE.read_csv(previous_path)
    rows, counts = MODULE.build(previous_path, full_path)

    assert len(rows) == len(previous) == 1247
    assert [row["product_external_id"] for row in rows] == [row["product_external_id"] for row in previous]
    assert counts == {
        "rows": 1247,
        "description_present": 902,
        "description_missing": 345,
        "verified_image_present": 0,
        "verified_image_missing": 1247,
    }
    assert [row["priority"] for row in rows] == [str(value) for value in range(1, 1248)]
