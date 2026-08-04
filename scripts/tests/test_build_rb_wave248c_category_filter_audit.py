import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "wave248c",
    ROOT / "scripts" / "build-rb-wave248c-category-filter-audit.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def snapshot():
    return {
        "categories": [
            {"slug": "catalog/a", "name": "A", "path": "/catalog/a", "parent_slug": None},
            {"slug": "catalog/a/leaf", "name": "Leaf", "path": "/catalog/a/leaf", "parent_slug": "catalog/a"},
        ],
        "api_metrics": {
            "catalog/a": {"total": 12, "price_sort_enabled": True, "visible_facets": {"manufacturer": [{"value": "FIAMM", "count": 12}]}},
            "catalog/a/leaf": {"total": 10, "price_sort_enabled": False, "visible_facets": {"technology": [{"value": "AGM", "count": 10}]}},
            "__catalog_total": {"total": 12},
        },
        "db_facts": {
            "categories": [
                {"external_id": "seo:a", "slug": "catalog/a", "direct_published_products": 2, "subtree_published_products": 12},
                {"external_id": "seo:leaf", "slug": "catalog/a/leaf", "direct_published_products": 10, "subtree_published_products": 10},
            ],
            "attribute_facts": [
                {"root_external_id": "seo:a", "attribute_key": "Номинальное напряжение", "product_count": 12, "distinct_value_count": 1, "sample_values": ["12 В"]},
            ],
        },
    }


def test_wave248c_records_only_live_visibility_gated_facets():
    report = MODULE.audit(snapshot())
    assert report["summary"]["roots"] == 1
    assert report["summary"]["category_nodes"] == 2
    assert report["summary"]["facet_keys_visible_in_at_least_one_category"] == {"manufacturer": 1, "technology": 1}
    assert report["mixed_navigation_categories"][0]["slug"] == "catalog/a"
    assert report["stored_technical_attribute_coverage"][0]["safe_for_public_filter"] is False
    assert report["bounded_delta"]["database_apply"] is False
    assert report["bounded_delta"]["indexable_filter_url_creations"] == 0


def test_wave248c_fails_closed_when_api_and_database_counts_drift():
    broken = snapshot()
    broken["api_metrics"]["catalog/a"]["total"] = 11
    try:
        MODULE.audit(broken)
    except RuntimeError as error:
        assert "category count drift" in str(error)
    else:
        raise AssertionError("count drift was accepted")


def test_wave248c_coverage_thresholds():
    assert MODULE.coverage_label(9, 10) == "broad"
    assert MODULE.coverage_label(1, 10) == "partial"
    assert MODULE.coverage_label(0, 10) == "sparse"
    assert MODULE.coverage_label(0, 0) == "not_applicable"


def test_wave248c_normalizes_laravel_empty_associative_array_shape(monkeypatch):
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if url.endswith("/catalog/categories"):
            return {"data": [{"slug": "catalog/a", "name": "A", "path": "/catalog/a", "children": []}]}
        return {"meta": {"total": 1, "facets": []}}

    monkeypatch.setattr(MODULE, "fetch_json", fake_fetch)
    live = MODULE.live_api_snapshot("http://example.test")
    assert live["api_metrics"]["catalog/a"]["visible_facets"] == {}
    assert len(calls) == 3


def test_wave248c_frontend_backend_contract_is_explicit():
    assert all(MODULE.implementation_checks()["checks"].values())
