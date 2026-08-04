import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "materialize-dealer-backed-description-manifest.py"
SPEC = importlib.util.spec_from_file_location("materialize_dealer", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_materializes_only_admitted_rows_with_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    admission = tmp_path / "admission.json"
    output = tmp_path / "output.json"
    source.write_text(json.dumps({"locale": "ru-BY", "products": [
        {"external_id": "A", "model_core": "A1", "source_url": "https://dealer.test/a"},
        {"external_id": "B", "model_core": "B1", "source_url": "https://dealer.test/b"},
    ]}), encoding="utf-8")
    admission.write_text(json.dumps({
        "admission_policy": {
            "source_kind": "official_dealer_product_page", "source_tier": "dealer_backed",
            "source_publisher": "Dealer", "manufacturer_primary": False,
            "evidence_scope": "model_core", "checked_at": "2026-07-28",
        },
        "candidate_external_ids": ["A"], "excluded_pending_cache_recheck": ["B"],
    }), encoding="utf-8")

    summary = MODULE.build(source, admission, output)
    result = json.loads(output.read_text(encoding="utf-8"))

    assert summary == {"source_records": 2, "dealer_backed_records": 1, "excluded_pending_recheck": 1}
    assert [row["external_id"] for row in result["products"]] == ["A"]
    assert result["products"][0]["source_tier"] == "dealer_backed"
    assert result["products"][0]["manufacturer_primary"] is False
