import csv
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-safe-legacy-one-c-evidence.py"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_accepts_only_agreed_unique_article_evidence(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    bitrix = tmp_path / "bitrix.csv"
    registry = tmp_path / "registry.csv"
    site_state = tmp_path / "site-state.json"
    output = tmp_path / "accepted.json"
    rejected = tmp_path / "rejected.csv"
    summary = tmp_path / "summary.json"

    candidate_fields = [
        "Bitrix ID", "1С-код", "1С-Артикул", "1С-Наименование", "signature",
        "brand_ok", "confidence", "method", "сравнение",
    ]
    base = {
        "1С-Наименование": "Product",
        "signature": "PRODUCT",
        "brand_ok": "yes",
        "confidence": "0.95",
        "method": "sig+brand",
        "сравнение": "agree",
    }
    write_csv(candidates, candidate_fields, [
        {**base, "Bitrix ID": "1", "1С-код": "A", "1С-Артикул": "OK-1"},
        {**base, "Bitrix ID": "2", "1С-код": "B", "1С-Артикул": "COLLIDE"},
        {**base, "Bitrix ID": "3", "1С-код": "C", "1С-Артикул": "COLLIDE"},
        {**base, "Bitrix ID": "4", "1С-код": "D", "1С-Артикул": "OK-4", "сравнение": "differ"},
    ])
    legacy_fields = [
        "legacy_element_id", "active", "name", "is_first_focus_candidate",
        "legacy_url_candidate", "matched_section_paths", "preview_picture_file_id",
        "detail_picture_file_id",
    ]
    write_csv(bitrix, legacy_fields, [
        {"legacy_element_id": str(i), "active": "Y", "name": f"Legacy {i}",
         "is_first_focus_candidate": "true", "legacy_url_candidate": f"/catalog/{i}/",
         "matched_section_paths": "akkumulyatory/dlya_ibp", "preview_picture_file_id": str(100 + i),
         "detail_picture_file_id": ""}
        for i in range(1, 5)
    ])
    registry_fields = ["bitrix_id", "one_c_code", "identity_status"]
    write_csv(registry, registry_fields, [
        {"bitrix_id": str(i), "one_c_code": code, "identity_status": "linked_candidate"}
        for i, code in enumerate(["A", "B", "C", "D"], start=1)
    ])
    site_state.write_text(json.dumps([
        {"id": i, "is_published": i == 1, "product": {"external_id": code},
         "categories": [{"external_id": "seo:batteries-ups"}]}
        for i, code in enumerate(["A", "B", "C", "D"], start=1)
    ]), encoding="utf-8")

    subprocess.run([
        sys.executable, str(SCRIPT), "--candidates", str(candidates),
        "--bitrix-products", str(bitrix), "--registry", str(registry),
        "--site-state", str(site_state),
        "--output", str(output), "--rejected", str(rejected),
        "--summary", str(summary),
    ], check=True)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [row["one_c_external_id"] for row in payload["records"]] == ["A"]
    assert payload["records"][0]["safe_to_apply"] is False
    assert payload["records"][0]["rb_is_published"] is True
    report = json.loads(summary.read_text(encoding="utf-8"))
    assert report["accepted_rows"] == 1
    assert report["auto_apply_rows"] == 0
    assert report["rejection_reasons"] == {
        "article_collision:COLLIDE": 2,
        "independent_matchers_disagree": 1,
    }
