import csv
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-bulk-source-backed-preview.py"
SPEC = importlib.util.spec_from_file_location("bulk_preview", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_builds_unique_source_backed_noindex_preview_and_ignores_row_review_exclusions(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    generated = tmp_path / "generated"
    imports.mkdir()
    generated.mkdir()
    applied = tmp_path / "applied.json"
    state = tmp_path / "state.json"
    output = tmp_path / "preview.json"
    applied.write_text(json.dumps([{
        "verified_fields": {"manufacturer": "Delta", "model": "DT 612"},
        "source_urls": ["https://manufacturer.test/dt612"],
        "product": {"external_id": "КА-1", "name": "Аккумулятор Delta DT 612"},
    }]), encoding="utf-8")
    state.write_text(json.dumps([{
        "is_published": False,
        "price": None,
        "product": {"external_id": "КА-1", "name": "Аккумулятор Delta DT 612"},
        "categories": [{"external_id": "seo:batteries-ups"}],
    }]), encoding="utf-8")
    write_csv(imports / "rb-1c-review-exclusions.csv", ["Bitrix ID", "1С-код", "exclusion_reasons"], [{
        "Bitrix ID": "99", "1С-код": "КА-1", "exclusion_reasons": "brand_not_confirmed",
    }])

    summary = MODULE.build(applied, state, imports, generated, output)
    manifest = json.loads(output.read_text(encoding="utf-8"))

    assert summary["preview_products"] == 1
    assert manifest["products"][0]["model_core"] == "DT 612"
    assert manifest["products"][0]["category_slug"] == "catalog/industrial-batteries/batteries-ups"


def test_rejects_every_member_of_a_duplicate_brand_model_identity(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    generated = tmp_path / "generated"
    imports.mkdir()
    generated.mkdir()
    applied = tmp_path / "applied.json"
    state = tmp_path / "state.json"
    output = tmp_path / "preview.json"
    drafts = [{
        "verified_fields": {"manufacturer": "Delta", "model": "DT 612"},
        "source_urls": ["https://manufacturer.test/dt612"],
        "product": {"external_id": external_id, "name": "Аккумулятор Delta DT 612"},
    } for external_id in ["КА-1", "КА-2"]]
    applied.write_text(json.dumps(drafts), encoding="utf-8")
    state.write_text(json.dumps([{
        "is_published": False,
        "price": None,
        "product": draft["product"],
        "categories": [{"external_id": "seo:batteries-ups"}],
    } for draft in drafts]), encoding="utf-8")

    summary = MODULE.build(applied, state, imports, generated, output)

    assert summary["preview_products"] == 0
    assert summary["rejection_reasons"]["duplicate_current_brand_model_identity"] == 2
