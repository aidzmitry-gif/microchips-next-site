import csv
import io
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-rb-wave248a-release-cohort.py"


def module():
    spec = importlib.util.spec_from_file_location("wave248a_release_cohort", SCRIPT)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def row(index: int, category: str = "seo:batteries-industrial") -> dict[str, object]:
    return {
        "product_id": index,
        "external_id": f"bitrix:{10000 + index}",
        "name": f"Industrial UPS battery {index}",
        "manufacturer": "Exact Manufacturer",
        "mpn": f"EX-{index:04d}",
        "short_description": "Verified technical description. " * 8,
        "site_product_id": 20000 + index,
        "is_published": True,
        "price": "100.00" if index % 2 else None,
        "availability": "on_request",
        "category_external_id": category,
        "category_name": "B2B category",
        "verified_published_media_count": 0,
        "current_price_evidence_count": 1 if index % 2 else 0,
    }


def test_build_contract_and_no_repeat(monkeypatch) -> None:
    wave = module()
    monkeypatch.setattr(wave, "LIMIT", 200)
    monkeypatch.setattr(
        wave,
        "read_queues",
        lambda: ({"bitrix:10001"}, {"files": [], "latest_terminal_status_rows": 1}),
    )
    monkeypatch.setattr(wave, "read_direct_research_ids", lambda: ({"bitrix:10002"}, []))
    snapshot = {"site_key": "microchips-by", "currency": "BYN", "rows": [row(index) for index in range(1, 205)]}

    selected, summary = wave.build(snapshot)
    assert len(selected) == 200
    ids = {item["product_external_id"] for item in selected}
    assert len(ids) == 200
    assert "bitrix:10001" not in ids
    assert "bitrix:10002" not in ids
    assert all(item["is_published"] == "true" for item in selected)
    assert all(item["is_indexable"] == "false" for item in selected)
    assert all(item["identity_ready"] == "true" for item in selected)
    assert all(item["description_ready"] == "true" for item in selected)
    assert all(item["verified_published_media_count"] == "0" for item in selected)
    assert summary["no_repeat"]["selected_overlap_direct_research"] == 0
    assert summary["no_repeat"]["selected_overlap_terminal_queue"] == 0

    rendered = io.StringIO()
    writer = csv.DictWriter(rendered, fieldnames=wave.CSV_FIELDS)
    writer.writeheader()
    writer.writerows(selected)
    persisted = list(csv.DictReader(io.StringIO(rendered.getvalue())))
    assert len(persisted) == 200
    assert list(persisted[0]) == wave.CSV_FIELDS
    assert summary["quality"]["database_mutations"] == 0
    assert summary["quality"]["network_requests"] == 0


def test_rejects_a_cohort_outside_required_size(monkeypatch) -> None:
    wave = module()
    monkeypatch.setattr(wave, "read_queues", lambda: (set(), {"files": [], "latest_terminal_status_rows": 0}))
    monkeypatch.setattr(wave, "read_direct_research_ids", lambda: (set(), []))
    snapshot = {"site_key": "microchips-by", "currency": "BYN", "rows": [row(index) for index in range(1, 199)]}
    try:
        wave.build(snapshot)
    except wave.CohortError as error:
        assert "200-500" in str(error)
    else:
        raise AssertionError("under-sized cohort must fail closed")
