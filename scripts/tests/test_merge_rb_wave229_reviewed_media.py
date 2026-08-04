import json
import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "merge-rb-wave229-reviewed-media.py"
SPEC = importlib.util.spec_from_file_location("wave229_merge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def row(external_id="bitrix:1", media_id=1, digest="a" * 64):
    return {
        "external_id": external_id,
        "media_id": media_id,
        "content_sha256": digest,
        "storage_path": f"legacy-staging/rb/{media_id}.jpg",
        "rights_basis": "Company-owned Microchips legacy Bitrix upload backup.",
        "identity_scope": "exact",
        "mpn": "MODEL-1",
        "identity_evidence_level": "visible_exact_mpn",
        "visual_verification_note": "Exact MODEL-1 marking is visibly legible.",
        "reviewed_at": "2026-07-29",
    }


def payload(rows):
    return {"locale": "ru-BY", "images": rows}


def test_merges_unique_exact_rows():
    images = MODULE.merge_payloads(
        [("a", payload([row()])), ("b", payload([row("bitrix:2", 2, "b" * 64)]))],
        [],
    )
    assert len(images) == 2


def test_blocks_prior_or_duplicate_hash():
    try:
        MODULE.merge_payloads([("current", payload([row("bitrix:2", 2)]))], [payload([row()])])
    except ValueError as error:
        assert "replay" in str(error)
    else:
        raise AssertionError("prior hash replay must be rejected")
