import csv
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-bitrix-staging-transfer-manifest.py"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_preserves_all_focus_rows_without_rendering_or_publication(tmp_path: Path) -> None:
    products = tmp_path / "products.csv"
    content = tmp_path / "content.csv"
    matches = tmp_path / "matches.csv"
    safe = tmp_path / "safe.json"
    state = tmp_path / "state.json"
    output = tmp_path / "manifest.json"
    summary = tmp_path / "summary.json"
    write_csv(products, ["legacy_element_id", "legacy_iblock_id", "active", "name",
        "is_first_focus_candidate", "legacy_url_candidate", "primary_section_path",
        "matched_section_paths", "preview_picture_file_id", "detail_picture_file_id"], [
        {"legacy_element_id": "1", "legacy_iblock_id": "26", "active": "Y", "name": "A",
         "is_first_focus_candidate": "true", "legacy_url_candidate": "/catalog/1/",
         "primary_section_path": "a", "matched_section_paths": "a", "preview_picture_file_id": "10", "detail_picture_file_id": "11"},
        {"legacy_element_id": "2", "legacy_iblock_id": "26", "active": "Y", "name": "B",
         "is_first_focus_candidate": "true", "legacy_url_candidate": "/catalog/2/",
         "primary_section_path": "b", "matched_section_paths": "b", "preview_picture_file_id": "", "detail_picture_file_id": ""},
    ])
    write_csv(content, ["legacy_element_id", "preview_text_type", "preview_text", "detail_text_type", "detail_text"], [
        {"legacy_element_id": "1", "preview_text_type": "text", "preview_text": "short", "detail_text_type": "html", "detail_text": "<b>old</b>"},
        {"legacy_element_id": "2", "preview_text_type": "text", "preview_text": "", "detail_text_type": "text", "detail_text": ""},
    ])
    write_csv(matches, ["Bitrix ID", "1С-код", "1С-наименование", "1С-артикул", "Цена сайта", "1С-цена", "match_method", "match_score"], [
        {"Bitrix ID": "1", "1С-код": "P1", "1С-наименование": "A1", "1С-артикул": "X", "Цена сайта": "10", "1С-цена": "5", "match_method": "exact", "match_score": "100"},
        {"Bitrix ID": "2", "1С-код": "", "1С-наименование": "", "1С-артикул": "", "Цена сайта": "", "1С-цена": "", "match_method": "none", "match_score": "0"},
    ])
    safe.write_text(json.dumps({"records": [{"legacy_element_id": "1", "one_c_external_id": "P1"}]}), encoding="utf-8")
    state.write_text(json.dumps([{"id": 7, "is_published": True, "product": {"external_id": "P1"}, "categories": [{"external_id": "seo:batteries-ups"}]}]), encoding="utf-8")

    subprocess.run([sys.executable, str(SCRIPT), "--products", str(products),
        "--content", str(content), "--matches", str(matches), "--safe-evidence", str(safe),
        "--site-state", str(state), "--output", str(output), "--summary", str(summary)], check=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["records"]) == 2
    assert payload["records"][0]["transfer_status"] == "strict_mapped_evidence"
    assert payload["records"][1]["transfer_status"] == "hold_missing_1c_identity"
    assert all(row["render_legacy_html"] is False for row in payload["records"])
    assert all(row["change_publication"] is False for row in payload["records"])
