from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-rb-wave248b-price-freshness.py"

spec = importlib.util.spec_from_file_location("wave248b", SCRIPT)
assert spec and spec.loader
wave248b = importlib.util.module_from_spec(spec)
sys.modules["wave248b"] = wave248b
spec.loader.exec_module(wave248b)


def evidence(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "external_id": "bitrix:1", "site_product_id": 1, "site_price": "20.00", "availability": "on_request",
        "evidence_id": 1, "source": "legacy_site", "source_price": "20.0000", "multiplier": "1.0000",
        "calculated_price": "20.00", "evidence_currency": "BYN", "price_type": "legacy_public_price",
        "source_reference": "bitrix-backup://2026-07-25/element/1", "source_external_id": "1",
        "observed_at": "2026-07-25T00:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_fresh_legacy_price_is_showable_only_when_every_integrity_check_matches() -> None:
    row = wave248b.classify(evidence(), "BYN")
    assert row["classification"] == "showable_fresh"
    assert row["multiplier_policy_match"] == "true"
    assert row["offer_eligible"] == "false"


def test_old_but_integral_price_is_held_not_called_fresh() -> None:
    row = wave248b.classify(evidence(observed_at="2026-06-23T00:00:00+00:00"), "BYN")
    assert row["classification"] == "stale_hold"
    assert row["age_days"] == "37"
    assert "older_than_30" in row["reason"]


def test_x2_is_allowed_only_for_the_persisted_one_c_source() -> None:
    good = wave248b.classify(evidence(source="one_c_x2", source_price="10", multiplier="2", calculated_price="20"), "BYN")
    bad = wave248b.classify(evidence(source="legacy_site", source_price="10", multiplier="2", calculated_price="20"), "BYN")
    assert good["classification"] == "showable_fresh"
    assert bad["classification"] == "invalid_mismatch"
    assert "source_multiplier_policy_mismatch" in bad["reason"]


def test_mismatch_or_missing_evidence_fails_closed() -> None:
    mismatch = wave248b.classify(evidence(calculated_price="21"), "BYN")
    missing = wave248b.classify(evidence(evidence_id=None), "BYN")
    assert mismatch["classification"] == "invalid_mismatch"
    assert "visible_price_evidence_mismatch" in mismatch["reason"]
    assert missing["classification"] == "invalid_mismatch"
    assert "missing_current_evidence" in missing["reason"]


def test_snapshot_build_sorts_rows_and_counts_non_visible_evidence() -> None:
    snapshot = {"site_key": "microchips-by", "site_currency": "BYN", "all_current_evidence_rows": 3, "rows": [
        evidence(external_id="bitrix:2"),
        evidence(external_id="bitrix:1", observed_at="2026-06-23T00:00:00+00:00"),
    ]}
    ledger, summary = wave248b.build(snapshot)
    assert [row["product_external_id"] for row in ledger] == ["bitrix:1", "bitrix:2"]
    assert summary["classifications"] == {"showable_fresh": 1, "stale_hold": 1}
    assert summary["scope"]["excluded_non_visible_current_evidence_rows"] == 1
    assert summary["x2_rule"]["one_c_x2_rows_in_visible_scope"] == 0
