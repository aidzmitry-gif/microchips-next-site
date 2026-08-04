import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "build-bitrix-duplicate-review-evidence.py"
SPEC = importlib.util.spec_from_file_location("duplicate_review_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_complete_collision_manifest_is_fail_closed():
    records = [
        transfer_row("1", "P1"),
        transfer_row("2", "P1"),
        transfer_row("3", "P2"),
        transfer_row("4", "P2"),
        transfer_row("5", "P3"),
        transfer_row("6", "P3"),
    ]
    matches = [
        match_row("1", "P1", strict=True),
        match_row("2", "P1", strict=False),
        match_row("3", "P2", strict=True),
        match_row("4", "P2", strict=True),
        match_row("5", "P3", strict=False),
        match_row("6", "P3", strict=False),
    ]

    manifest, queue = MODULE.build(
        {"records": records}, matches, "a" * 64, "b" * 64, 742
    )

    assert manifest["expected_groups"] == 3
    assert manifest["expected_members"] == 6
    assert manifest["group_decision_counts"] == {
        "mixed_mapping_collision_hold": 1,
        "single_high_signal_review_queue": 1,
        "variant_or_collision_hold": 1,
    }
    assert manifest["member_decision_counts"] == {
        "hold_insufficient_identity_evidence": 3,
        "hold_multiple_high_signal_candidates": 2,
        "review_exact_identity_candidate": 1,
    }
    assert len(queue) == 1
    assert all(value is False for value in manifest["mutation_policy"].values())
    assert not any(
        member["merge_product"]
        for group in manifest["groups"]
        for member in group["members"]
    )


def test_code_drift_downgrades_match_to_hold():
    manifest, queue = MODULE.build(
        {"records": [transfer_row("1", "P1"), transfer_row("2", "P1")]},
        [match_row("1", "OTHER", strict=True), match_row("2", "P1", strict=False)],
        "a" * 64,
        "b" * 64,
        742,
    )

    assert manifest["groups"][0]["group_decision"] == "mixed_mapping_collision_hold"
    assert queue == []


def transfer_row(legacy_id, one_c):
    return {
        "legacy_element_id": legacy_id,
        "legacy_name": f"Legacy {legacy_id}",
        "legacy_url_candidate": f"/catalog/{legacy_id}/",
        "legacy_text_sha256": legacy_id * 64,
        "preview_picture_file_id": "",
        "detail_picture_file_id": "",
        "one_c_external_id": one_c,
        "one_c_name": f"Product {one_c}",
        "transfer_status": "candidate_duplicate_group",
    }


def match_row(legacy_id, one_c, strict):
    return {
        "Bitrix ID": legacy_id,
        "1С-код": one_c,
        "brand_ok": "yes" if strict else "no",
        "confidence": "0.95" if strict else "0.6",
        "method": "sig+brand" if strict else "sig+brand+generic",
        "comparison": "agree",
        "signature": f"SIG{legacy_id}",
    }
