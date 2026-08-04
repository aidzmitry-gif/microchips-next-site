import csv
import importlib.util
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-rb-wave249a-indexable-b2b-cohort.py"


def module():
    spec = importlib.util.spec_from_file_location("wave249a_indexable_b2b", SCRIPT)
    assert spec and spec.loader
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def row(index: int) -> dict[str, object]:
    return {
        "product_id": index,
        "external_id": f"bitrix:{10000 + index}",
        "name": f"Industrial battery {index}",
        "manufacturer": "Exact Manufacturer",
        "mpn": f"EX-{index:04d}",
        "manufacturer_normalized": "exactmanufacturer",
        "mpn_normalized": f"ex{index:04d}",
        "short_description": "Source-backed exact product description. " * 8,
        "site_product_id": 20000 + index,
        "is_published": True,
        "price": None,
        "availability": "on_request",
        "category_external_id": "seo:batteries-industrial",
        "category_name": "Industrial batteries",
        "identity_pair_catalogue_count": 1,
        "verified_media_count": 1,
        "verified_media_ids": json.dumps([30000 + index]),
        "matching_applied_description_count": 1,
        "description_source_urls": json.dumps([f"https://manufacturer.example/products/{index}"]),
        "description_source_kind": "official_manufacturer_product_page",
        "description_source_tier": "manufacturer_primary",
        "description_identity_scope": "exact",
        "description_source_checked_at": "2026-07-29",
        "product_url_count": 1,
        "product_path": f"/catalog/industrial/product-{index}",
        "url_is_indexable": False,
        "seo_record_count": 1,
        "seo_canonical_path": f"/catalog/industrial/product-{index}",
        "seo_is_indexable": False,
        "canonical_redirect_source_count": 0,
        "current_price_evidence_count": 0,
        "fresh_matching_price_evidence_count": 0,
        "open_duplicate_conflict_count": 0,
        "unresolved_identity_candidate_count": 0,
    }


def snapshot(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "site_key": "microchips-by", "currency": "BYN", "locale": "ru-BY", "rows": rows,
        "meta": {"open_duplicate_conflicts": 0, "unresolved_identity_candidates": 0, "duplicate_site_url_paths": 0},
    }


def test_selects_100_strict_unique_release_candidates() -> None:
    wave = module()
    rows, summary = wave.build(snapshot([row(index) for index in range(1, 106)]))
    assert len(rows) == 100
    assert summary["target_met"] is True
    assert summary["shortfall"] == 0
    assert summary["release_blocker"] is None
    assert len({item["product_external_id"] for item in rows}) == 100
    assert len({item["canonical_path"] for item in rows}) == 100
    assert all(item["release_decision"] == "READY_FOR_BOUNDED_INDEXABLE_RELEASE" for item in rows)
    assert all(item["price_evidence_status"] == "no_visible_numeric_price_request_quote" for item in rows)

    rendered = io.StringIO()
    writer = csv.DictWriter(rendered, fieldnames=wave.CSV_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    assert len(list(csv.DictReader(io.StringIO(rendered.getvalue())))) == 100
    assert summary["quality"]["database_mutations"] == 0


def test_fails_closed_with_shortfall_instead_of_padding() -> None:
    wave = module()
    data = [row(index) for index in range(1, 11)]
    data[1]["verified_media_count"] = 0
    data[2]["description_source_urls"] = json.dumps(["http://not-secure.example/product"])
    data[3]["identity_pair_catalogue_count"] = 2
    data[4]["price"] = "100.00"
    data[4]["current_price_evidence_count"] = 1
    data[4]["fresh_matching_price_evidence_count"] = 0
    data[5]["open_duplicate_conflict_count"] = 1

    rows, summary = wave.build(snapshot(data))
    assert len(rows) == 5
    assert summary["target_met"] is False
    assert summary["shortfall"] == 95
    assert summary["release_blocker"] == "ONLY_5_CARDS_PASS_ALL_STRICT_GATES"
    assert summary["excluded"] == {
        "description_source_urls_invalid": 1,
        "exact_verified_published_media_missing": 1,
        "identity_pair_collision": 1,
        "open_duplicate_conflict": 1,
        "visible_price_not_fresh_unique_and_pinned": 1,
    }
    assert [item["product_external_id"] for item in summary["price_only_near_ready_blockers"]] == ["bitrix:10005"]
    assert summary["price_only_near_ready_blockers"][0]["safe_next_action"].startswith("CLEAR_STALE_VISIBLE_PRICE")


def test_allows_only_a_single_fresh_matching_pinned_visible_price() -> None:
    wave = module()
    priced = row(1)
    priced["price"] = "244.00"
    priced["current_price_evidence_count"] = 1
    priced["fresh_matching_price_evidence_count"] = 1
    rows, _ = wave.build(snapshot([priced]))
    assert rows[0]["price_evidence_status"] == "fresh_unique_matching_pinned"


def test_rejects_global_site_url_path_collision() -> None:
    wave = module()
    payload = snapshot([row(1)])
    payload["meta"]["duplicate_site_url_paths"] = 1
    try:
        wave.build(payload)
    except wave.CohortError as error:
        assert "URL path uniqueness" in str(error)
    else:
        raise AssertionError("global URL path collision must fail closed")
