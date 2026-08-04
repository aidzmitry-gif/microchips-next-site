import csv
import importlib.util
import json
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave243-delta-duplicate-collapse.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wave243_delta_duplicates", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def live_row(external_id: str, name: str, *, manufacturer="", mpn="", price=None):
    evidence = [] if price is None else [{"calculated_price": price, "currency": "BYN"}]
    return {
        "external_id": external_id,
        "missing": False,
        "name": name,
        "manufacturer": manufacturer,
        "mpn": mpn,
        "site_product_count": 1,
        "is_published": True,
        "availability": "on_request",
        "price": price,
        "price_evidence_total": len(evidence),
        "current_price_evidence": evidence,
        "verified_media": 0,
        "family_roles": 0,
        "urls": [{"path": f"/catalog/{external_id.replace(':', '-')}", "is_indexable": False}],
        "seos": [{"is_indexable": False, "schema": None}],
        "categories": ["seo:batteries-ups"],
    }


def test_builder_emits_only_new_exact_official_duplicate(monkeypatch):
    module = load_module()
    # New directories inherit a Docker-created deny ACL on this Windows
    # workspace. Keep isolated fixture files in the existing host-writable
    # tests directory and always remove only those self-created files.
    prefix = ROOT / "scripts/tests" / f".wave243-delta-{uuid.uuid4().hex}"
    source = prefix.with_suffix(".source.csv")
    snapshot = prefix.with_suffix(".official.html")
    evidence = prefix.with_suffix(".evidence.csv")
    manifest_path = prefix.with_suffix(".manifest.json")
    summary_path = prefix.with_suffix(".summary.json")
    fixture_files = [source, snapshot, evidence, manifest_path, summary_path]
    try:
        snapshot.write_text("official Delta table", encoding="utf-8")
        rows = []
        live = {}
        for index in range(23):
            duplicate_id = f"bitrix:{1400 + index}"
            survivor_id = f"ONEC-{index}"
            model = f"DT {400 + index}"
            exact = index == 0
            rows.append({
                "external_id": duplicate_id,
                "current_name": f"Аккумулятор Delta {model} (AGM, 1Ah)",
                "manufacturer": "Delta",
                "mpn": model,
                "mpn_normalized": model.replace(" ", "").lower(),
                "title_capacity_ah": "1",
                "title_voltage_v": "4",
                "source_offered_model": model if exact else "",
                "source_capacity_ah": "1" if exact else "",
                "source_voltage_v": "4" if exact else "",
                "source_technology": "AGM" if exact else "",
                "source_url": "https://delta.example/series/dt/" if exact else "",
                "source_snapshot_path": str(snapshot) if exact else "",
                "source_snapshot_sha256": module.sha256(snapshot) if exact else "",
                "live_duplicate_owner_external_ids": survivor_id,
                "decision": "HOLD",
                "hold_reason": "LIVE_DUPLICATE_OWNERSHIP_CONFLICT",
                "description_decision": "HOLD",
                "description_hold_reason": "LIVE_DUPLICATE_OWNERSHIP_CONFLICT",
            })
            live[duplicate_id] = live_row(duplicate_id, rows[-1]["current_name"])
            live[survivor_id] = live_row(
                survivor_id,
                f"Аккумуляторная батарея Delta {model}",
                manufacturer="Delta",
                mpn=model.replace(" ", ""),
                price="20.00" if exact else None,
            )
        with source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

        monkeypatch.setattr(module, "SOURCE", source)
        monkeypatch.setattr(module, "EVIDENCE", evidence)
        monkeypatch.setattr(module, "MANIFEST", manifest_path)
        monkeypatch.setattr(module, "SUMMARY", summary_path)
        monkeypatch.setattr(module, "query_live", lambda external_ids: {key: live[key] for key in external_ids})
        module.main()

        summary = json.loads(module.SUMMARY.read_text(encoding="utf-8"))
        manifest = json.loads(module.MANIFEST.read_text(encoding="utf-8"))
        assert summary["result"]["decision_counts"] == {"HOLD": 22, "PASS": 1}
        assert summary["result"]["manifest_rows"] == 1
        assert manifest["duplicates"][0]["duplicate_external_id"] == "bitrix:1400"
        assert manifest["duplicates"][0]["survivor_external_id"] == "ONEC-0"
    finally:
        for path in fixture_files:
            path.unlink(missing_ok=True)


def test_survivor_price_requires_one_matching_byn_evidence():
    module = load_module()
    row = live_row("ONEC-1", "Delta DT401", manufacturer="Delta", mpn="DT401", price="20.00")
    assert module.safe_noindex_state(row, duplicate=False) == []
    row["current_price_evidence"][0]["calculated_price"] = "21.00"
    assert module.safe_noindex_state(row, duplicate=False) == ["survivor_price_evidence_mismatch"]
