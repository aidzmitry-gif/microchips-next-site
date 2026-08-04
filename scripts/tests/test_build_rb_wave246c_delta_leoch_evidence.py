import csv
import importlib.util
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave246c-delta-leoch-evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wave246c", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_wave246c_complete_no_repeat_packet_is_deterministic():
    module = load_module()
    first = module.build()
    first_hash = first["outputs"]["ledger"]["sha256"]
    second = module.build()
    assert second["outputs"]["ledger"]["sha256"] == first_hash
    assert second["scope"] == {"rows": 92, "manufacturer_counts": {"Delta": 57, "LEOCH": 35}}
    assert second["no_repeat"] == {
        "identity_noops": 92, "description_noops": 92,
        "new_identity_rows": 0, "new_description_rows": 0,
    }
    assert second["live_safety"]["duplicate_owner_conflicts"] == 0
    assert second["live_safety"]["published"] == 92
    assert second["live_safety"]["verified_published_media"] == 0

    with module.LEDGER.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len({row["external_id"] for row in rows}) == 92
    assert Counter(row["manufacturer"] for row in rows) == {"Delta": 57, "LEOCH": 35}
    assert not any(row["live_duplicate_owner_external_ids"] for row in rows)
    assert {row["identity_decision"] for row in rows} == {"PASS_NOOP_ALREADY_COMPLETE_NO_REPEAT"}
    assert {row["description_decision"] for row in rows} == {"PASS_NOOP_ALREADY_APPLIED_NO_REPEAT"}
    assert Counter(row["media_decision"] for row in rows) == {
        "NOOP_PRIOR_REVIEWED_NO_REPEAT": 56,
        "HOLD_NO_EXACT_COMPANY_OWNED_CANDIDATE": 36,
    }


def test_wave246c_pass_only_manifests_are_intentionally_empty():
    module = load_module()
    module.build()
    identity = json.loads(module.IDENTITIES.read_text(encoding="utf-8"))
    description = json.loads(module.DESCRIPTIONS.read_text(encoding="utf-8"))
    assert identity["target_kind"] == "active_1c"
    assert identity["products"] == []
    assert description["locale"] == "ru-BY"
    assert description["products"] == []
    assert "no-repeat" in identity["note"]

