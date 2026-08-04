import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-fanso-image-rights-blocked-manifest.py"
WAVE80 = ROOT / "docs" / "imports" / "rb-source-backed-description-drafts-fanso-model-core-wave-80-2026-07-27.json"
SPEC = importlib.util.spec_from_file_location("build_fanso_rights_block", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def wave80_products():
    return json.loads(WAVE80.read_text(encoding="utf-8"))["products"]


def test_builds_27_non_importable_rights_blockers():
    payload = MODULE.build_payload(wave80_products(), expected=27)
    assert payload["stage_source_image_candidates_compatible"] is False
    assert "products" not in payload
    assert len(payload["blocked_candidates"]) == 27
    assert len({row["external_id"] for row in payload["blocked_candidates"]}) == 27
    assert len({row["source_asset_url"] for row in payload["blocked_candidates"]}) == 9
    for row in payload["blocked_candidates"]:
        assert row["candidate_status"] == "blocked_rights"
        assert row["review_status"] == "needs_written_permission"
        assert row["publication_status"] == "blocked"
        assert row["identity_scope"] == "model_core"
        assert row["source_scope"] == "model_core"
        assert row["rights_status"] == "no_written_permission"
        assert row["remote_check"]["local_copy_retained"] is False
        assert "письменное разрешение" in row["required_action"].lower()


def test_alt_and_visual_notes_do_not_claim_variant_identity():
    payload = MODULE.build_payload(wave80_products(), expected=27)
    forbidden = ("jst", "ehr", "phr", "xhp", "2pf", "3pf", "4pf", "китай")
    for row in payload["blocked_candidates"]:
        safe_text = (row["safe_alt_if_rights_granted"] + " " + row["visual_observation"]).lower()
        assert all(token not in safe_text for token in forbidden)
        assert "не подтверждает разъём" in row["limitation"].lower()


def test_guards_scope_brand_unknown_model_duplicate_and_count():
    base = wave80_products()[0].copy()
    wrong_scope = base.copy()
    wrong_scope["identity_scope"] = "exact"
    with pytest.raises(RuntimeError, match="escaped model_core"):
        MODULE.build_payload([wrong_scope], expected=1)

    wrong_brand = base.copy()
    wrong_brand["manufacturer"] = "Other"
    with pytest.raises(RuntimeError, match="not FANSO"):
        MODULE.build_payload([wrong_brand], expected=1)

    unknown = base.copy()
    unknown["model_core"] = "ER99999H"
    with pytest.raises(RuntimeError, match="unsupported FANSO model"):
        MODULE.build_payload([unknown], expected=1)

    with pytest.raises(RuntimeError, match="repeats external_id"):
        MODULE.build_payload([base, base.copy()], expected=2)

    with pytest.raises(RuntimeError, match="Expected 2 blocked FANSO candidates, got 1"):
        MODULE.build_payload([base], expected=2)


def test_serialization_is_utf8_without_bom_or_unicode_escapes():
    payload = MODULE.build_payload(wave80_products()[:1], expected=1)
    raw = MODULE.serialize_payload(payload)
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert "письменное".encode("utf-8") in raw
    assert b"\\u043f" not in raw
