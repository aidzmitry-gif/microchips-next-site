import csv
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-bulk-legacy-media-candidates.py"
SPEC = importlib.util.spec_from_file_location("bulk_media", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_builds_only_unique_in_scope_brand_model_candidate(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    generated = tmp_path / "generated"
    imports.mkdir()
    generated.mkdir()
    applied = tmp_path / "applied.json"
    site = tmp_path / "site.json"
    media = tmp_path / "media.json"
    legacy = tmp_path / "legacy.csv"
    links = tmp_path / "links.csv"
    output = tmp_path / "out.csv"

    applied.write_text(json.dumps([{
        "verified_fields": {"manufacturer": "Delta", "model": "DT 612"},
        "source_urls": ["https://dealer.test/dt612"],
        "product": {"external_id": "КА-1", "name": "Аккумулятор Delta DT 612"},
    }]), encoding="utf-8")
    site.write_text(json.dumps([{
        "product": {"external_id": "КА-1", "name": "Аккумулятор Delta DT 612"},
        "categories": [{"external_id": "seo:batteries-ups"}],
    }]), encoding="utf-8")
    media.write_text("[]", encoding="utf-8")
    write_csv(legacy, ["legacy_element_id", "name", "preview_picture_file_id", "detail_picture_file_id"], [{
        "legacy_element_id": "10", "name": "Аккумулятор Delta DT 612 (AGM, 12Ah)",
        "preview_picture_file_id": "100", "detail_picture_file_id": "101",
    }])
    write_csv(links, ["Bitrix ID", "1С-код", "confidence", "brand_ok"], [{
        "Bitrix ID": "10", "1С-код": "КА-1", "confidence": "0.95", "brand_ok": "yes",
    }])
    # Exclusions in the review gate are rejected Bitrix↔1C relationship rows,
    # not product-level exclusions. A separate exact reviewed relationship for
    # the same 1C item must remain eligible.
    write_csv(imports / "rb-1c-review-exclusions.csv", ["Bitrix ID", "1С-код", "exclusion_reasons"], [{
        "Bitrix ID": "99", "1С-код": "КА-1", "exclusion_reasons": "brand_not_confirmed",
    }])

    summary = MODULE.build(applied, site, media, legacy, links, imports, generated, output)
    rows = MODULE.csv_rows(output)

    assert summary["candidates_for_visual_review"] == 1
    assert rows[0]["identity"] == "DT 612"
    assert rows[0]["identity_evidence"] == "reviewed_strict_link_plus_literal_brand_model"


def test_rejects_duplicate_current_identity(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    generated = tmp_path / "generated"
    imports.mkdir()
    generated.mkdir()
    applied = tmp_path / "applied.json"
    site = tmp_path / "site.json"
    media = tmp_path / "media.json"
    legacy = tmp_path / "legacy.csv"
    links = tmp_path / "links.csv"
    output = tmp_path / "out.csv"
    drafts = [{
        "verified_fields": {"manufacturer": "Delta", "model": "DT 612"},
        "source_urls": ["https://dealer.test/dt612"],
        "product": {"external_id": external_id, "name": "Аккумулятор Delta DT 612"},
    } for external_id in ["КА-1", "КА-2"]]
    applied.write_text(json.dumps(drafts), encoding="utf-8")
    site.write_text(json.dumps([{
        "product": row["product"], "categories": [{"external_id": "seo:batteries-ups"}],
    } for row in drafts]), encoding="utf-8")
    media.write_text("[]", encoding="utf-8")
    write_csv(legacy, ["legacy_element_id", "name", "preview_picture_file_id", "detail_picture_file_id"], [])
    write_csv(links, ["Bitrix ID", "1С-код", "confidence", "brand_ok"], [])

    summary = MODULE.build(applied, site, media, legacy, links, imports, generated, output)

    assert summary["candidates_for_visual_review"] == 0
    assert summary["rejection_reasons"]["duplicate_current_brand_model_identity"] == 2


def test_does_not_repeat_a_prior_visual_reject(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    generated = tmp_path / "generated"
    imports.mkdir()
    generated.mkdir()
    applied = tmp_path / "applied.json"
    site = tmp_path / "site.json"
    media = tmp_path / "media.json"
    legacy = tmp_path / "legacy.csv"
    links = tmp_path / "links.csv"
    output = tmp_path / "out.csv"
    applied.write_text(json.dumps([{
        "verified_fields": {"manufacturer": "CSB", "model": "HRL12330W"},
        "source_urls": ["https://manufacturer.test/hrl"],
        "product": {"external_id": "КА-1", "name": "CSB HRL12330W"},
    }]), encoding="utf-8")
    site.write_text(json.dumps([{
        "product": {"external_id": "КА-1", "name": "CSB HRL12330W"},
        "categories": [{"external_id": "seo:batteries-ups"}],
    }]), encoding="utf-8")
    media.write_text("[]", encoding="utf-8")
    write_csv(legacy, ["legacy_element_id", "name", "preview_picture_file_id", "detail_picture_file_id"], [])
    write_csv(links, ["Bitrix ID", "1С-код", "confidence", "brand_ok"], [])
    write_csv(generated / "rb-company-owned-media-visual-old.csv", ["external_id", "verdict"], [
        {"external_id": "КА-1", "verdict": "REJECT"},
    ])

    summary = MODULE.build(applied, site, media, legacy, links, imports, generated, output)

    assert summary["candidates_for_visual_review"] == 0
    assert summary["rejection_reasons"]["legacy_media_already_visually_reviewed"] == 1


def test_rejects_a_strict_legacy_link_owned_by_multiple_1c_products(tmp_path: Path) -> None:
    imports = tmp_path / "imports"
    generated = tmp_path / "generated"
    imports.mkdir()
    generated.mkdir()
    applied = tmp_path / "applied.json"
    site = tmp_path / "site.json"
    media = tmp_path / "media.json"
    legacy = tmp_path / "legacy.csv"
    links = tmp_path / "links.csv"
    output = tmp_path / "out.csv"
    applied.write_text(json.dumps([{
        "verified_fields": {"manufacturer": "Delta", "model": "DT 612"},
        "source_urls": ["https://manufacturer.test/dt612"],
        "product": {"external_id": "КА-1", "name": "Аккумулятор Delta DT 612"},
    }]), encoding="utf-8")
    site.write_text(json.dumps([{
        "product": {"external_id": "КА-1", "name": "Аккумулятор Delta DT 612"},
        "categories": [{"external_id": "seo:batteries-ups"}],
    }]), encoding="utf-8")
    media.write_text("[]", encoding="utf-8")
    write_csv(legacy, ["legacy_element_id", "name", "preview_picture_file_id", "detail_picture_file_id"], [{
        "legacy_element_id": "10", "name": "Аккумулятор Delta DT 612 (AGM, 12Ah)",
        "preview_picture_file_id": "100", "detail_picture_file_id": "101",
    }])
    write_csv(links, ["Bitrix ID", "1С-код", "confidence", "brand_ok"], [
        {"Bitrix ID": "10", "1С-код": "КА-1", "confidence": "0.95", "brand_ok": "yes"},
        {"Bitrix ID": "10", "1С-код": "КА-2", "confidence": "0.95", "brand_ok": "yes"},
    ])

    summary = MODULE.build(applied, site, media, legacy, links, imports, generated, output)

    assert summary["candidates_for_visual_review"] == 0
    assert summary["rejection_reasons"]["ambiguous_strict_legacy_links"] == 1
