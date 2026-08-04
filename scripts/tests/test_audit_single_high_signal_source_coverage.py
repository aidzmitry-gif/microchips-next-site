import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "audit-single-high-signal-source-coverage.py"
SPEC = importlib.util.spec_from_file_location("source_coverage", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_reuses_exact_and_model_core_evidence_without_emitting_identity_decisions():
    queue = [row("1", "P1"), row("2", "P2"), row("3", "P3")]
    evidence = {
        "P1": [(Path("exact.json"), {"external_id": "P1", "mpn": "M1", "source_url": "https://example.test/p1"})],
        "P2": [(Path("model.json"), {"external_id": "P2", "identity_scope": "model_core", "source_url": "https://example.test/p2"})],
    }

    rows, summary = MODULE.classify(queue, evidence)

    assert [item["coverage_status"] for item in rows] == [
        "existing_exact_evidence",
        "existing_model_core_evidence",
        "source_research_required",
    ]
    assert summary["identity_decisions_emitted"] == 0
    assert summary["coverage"] == {
        "existing_exact_evidence": 1,
        "existing_model_core_evidence": 1,
        "source_research_required": 1,
    }


def row(priority, external_id):
    return {
        "review_priority": priority,
        "one_c_external_id": external_id,
        "legacy_element_id": priority,
        "legacy_name": f"Legacy {priority}",
    }
