import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave244a-fiamm-duplicate-collapse.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wave244a_fiamm_duplicates", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def live_row(external_id, name, *, manufacturer=None, mpn=None, price=None, duplicate=False):
    return {
        "external_id": external_id, "missing": False, "name": name,
        "manufacturer": manufacturer, "mpn": mpn, "site_product_count": 1,
        "is_published": True, "availability": "on_request", "price": price,
        "price_evidence_total": 0 if price is None else 1,
        "current_price_evidence": [] if price is None else [{"calculated_price": price, "currency": "BYN"}],
        "verified_media": 0 if duplicate else 1, "family_roles": 0,
        "urls": [{"path": f"/catalog/{external_id.replace(':', '-')}", "is_indexable": False}],
        "seos": [{"is_indexable": False, "schema": None}],
        "categories": ["seo:batteries-ups"] if duplicate else ["410", "seo:batteries-ups"],
    }


def test_wave244a_emits_exactly_two_safe_no_repeat_collapses(monkeypatch):
    module = load_module()
    live = {
        "bitrix:3266": live_row("bitrix:3266", "Аккумулятор Fiamm 12FGH36 (AGM, 9Ah)", duplicate=True),
        "ФР-00002108": live_row("ФР-00002108", "Батарея FIAMM 12FGH36 12V 9Ah", manufacturer="FIAMM", mpn="12FGH36", price="126.00"),
        "bitrix:1511": live_row("bitrix:1511", "Аккумулятор Fiamm 4SLA150 (AGM, 150Ah)", duplicate=True),
        "КА-00003136": live_row("КА-00003136", "Аккумуляторная батарея FIAMM 4SLA150", manufacturer="FIAMM", mpn="4SLA150", price="19.00"),
    }

    def safe(row, *, duplicate):
        reasons = []
        if row["missing"] or row["site_product_count"] != 1 or not row["is_published"]:
            reasons.append("missing_or_non_unique_published_site_product")
        if duplicate and (row["price"] is not None or row["verified_media"] or row["family_roles"]):
            reasons.append("unsafe_duplicate_state")
        if not duplicate and row["price_evidence_total"] != 1:
            reasons.append("survivor_price_evidence_mismatch")
        return reasons

    monkeypatch.setattr(module, "safety_module", lambda: SimpleNamespace(
        query_live=lambda ids: {key: live[key] for key in ids}, safe_noindex_state=safe,
    ))
    output = ROOT / "docs/audits/generated"
    monkeypatch.setattr(module, "EVIDENCE", output / "test-wave244a-evidence.csv")
    monkeypatch.setattr(module, "MANIFEST", output / "test-wave244a-manifest.json")
    monkeypatch.setattr(module, "SUMMARY", output / "test-wave244a-summary.json")
    monkeypatch.setattr(module, "REPORT", output / "test-wave244a-report.md")
    module.main()

    summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
    manifest = json.loads(module.MANIFEST.read_text(encoding="utf-8"))
    assert summary["scope"] == 2 and summary["pass"] == 2 and summary["hold"] == 0
    assert summary["prior_exclusions"]["url_overlap"] == 0
    assert summary["prior_exclusions"]["sha_overlap"] == 0
    assert {(row["duplicate_external_id"], row["survivor_external_id"]) for row in manifest["duplicates"]} == {
        ("bitrix:3266", "ФР-00002108"), ("bitrix:1511", "КА-00003136"),
    }


def test_checked_in_manifest_is_fail_closed_and_sha_pinned():
    module = load_module()
    manifest = json.loads(module.MANIFEST.read_text(encoding="utf-8"))
    assert len(manifest["duplicates"]) == 2
    for row in manifest["duplicates"]:
        assert row["source_url"].startswith("https://www.fiamm.ru/")
        assert module.sha(ROOT / row["source_snapshot_path"]) == row["source_snapshot_sha256"]
        assert module.sha(ROOT / row["source_evidence_path"]) == row["source_evidence_sha256"]
        assert row["availability"] == "on_request"
        assert set(row["duplicate_category_external_ids"]).issubset(set(row["category_external_ids"]))
