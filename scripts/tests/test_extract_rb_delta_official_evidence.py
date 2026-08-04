from __future__ import annotations

import csv
import hashlib
import importlib.util
import shutil
import sys
import uuid
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "extract-rb-delta-official-evidence.py"
SPEC = importlib.util.spec_from_file_location("delta_extract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def workspace_tmp() -> Path:
    root = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-delta-extract-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def source_row(page: Path, model: str, external_id: str = "bitrix:1", page_model: str | None = None) -> dict[str, str]:
    return {
        "external_id": external_id,
        "model": model,
        "page_model": page_model or model,
        "source_url": "https://www.delta-batt.com/products/test_model/",
        "html_path": str(page),
        "source_sha256": hashlib.sha256(page.read_bytes()).hexdigest(),
    }


def product_html(model: str, properties: str, after: str = "") -> str:
    return f'<h1>DELTA {model}</h1><div class="product-page__info">{properties}Показать все характеристики</div>{after}'


def test_exact_page_extracts_only_unambiguous_model_facts() -> None:
    root = workspace_tmp()
    try:
        candidates = root / "candidates.csv"
        write(candidates, [{"external_id": "bitrix:1", "model_candidate_unverified": "DTM 1217", "safe_to_apply": "false"}])
        page = root / "dtm.html"
        page.write_text(product_html("DTM 1217", "Напряжение, В: 12 Емкость, Ач: 17"), encoding="utf-8")
        sources = root / "sources.csv"; write(sources, [source_row(page, "DTM 1217")])
        summary = MODULE.build(candidates, sources, root / "out.csv", root / "summary.json", 1)
        rows = list(csv.DictReader((root / "out.csv").open(encoding="utf-8-sig")))
        assert summary["exact_evidence_records"] == 1
        assert summary["output_sha256"] == hashlib.sha256((root / "out.csv").read_bytes()).hexdigest()
        assert rows[0]["voltage_v"] == "12" and rows[0]["capacity_ah"] == "17"
        assert rows[0]["publisher"] == "DELTA Battery / ENERGON"
        assert rows[0]["content_model_key"] == MODULE.model_key("DTM 1217")
        assert Path(rows[0]["source_snapshot_path"]) == page.resolve()
        assert rows[0]["safe_to_apply"] == "false"
    finally:
        shutil.rmtree(root)


def test_ambiguous_values_fail_closed() -> None:
    root = workspace_tmp()
    try:
        candidates = root / "candidates.csv"; write(candidates, [{"external_id": "bitrix:1", "model_candidate_unverified": "HR 12-7", "safe_to_apply": "false"}])
        page = root / "bad.html"
        page.write_text(product_html("HR 12-7", "Напряжение, В: 6 Напряжение, В: 12 Емкость, Ач: 7"), encoding="utf-8")
        sources = root / "sources.csv"; write(sources, [source_row(page, "HR 12-7")])
        summary = MODULE.build(candidates, sources, root / "out.csv", root / "summary.json", 1)
        assert summary["exact_evidence_records"] == 0
        assert summary["rejected_source_pages"]["ambiguous_or_missing_voltage_capacity"] == 1
    finally:
        shutil.rmtree(root)


def test_decimal_collision_and_recommendation_facts_fail_closed() -> None:
    root = workspace_tmp()
    try:
        candidates = root / "candidates.csv"; write(candidates, [{"external_id": "bitrix:1", "model_candidate_unverified": "HR 12-4.5", "safe_to_apply": "false"}])
        page = root / "wrong.html"
        page.write_text(product_html("HR 12-45", "", "<aside>Напряжение, В: 12 Емкость, Ач: 45</aside>"), encoding="utf-8")
        sources = root / "sources.csv"; write(sources, [source_row(page, "HR 12-4.5", page_model="HR 12-45")])
        summary = MODULE.build(candidates, sources, root / "out.csv", root / "summary.json", 1)
        assert summary["exact_evidence_records"] == 0
        assert summary["rejected_source_pages"]["exact_model_not_in_page_h1"] == 1
    finally:
        shutil.rmtree(root)


def test_source_hash_mismatch_fails_closed() -> None:
    root = workspace_tmp()
    try:
        candidates = root / "candidates.csv"; write(candidates, [{"external_id": "bitrix:1", "model_candidate_unverified": "DTM 1217", "safe_to_apply": "false"}])
        page = root / "changed.html"; page.write_text(product_html("DTM 1217", "Напряжение, В: 12 Емкость, Ач: 17"), encoding="utf-8")
        row = source_row(page, "DTM 1217"); row["source_sha256"] = "0" * 64
        sources = root / "sources.csv"; write(sources, [row])
        summary = MODULE.build(candidates, sources, root / "out.csv", root / "summary.json", 1)
        assert summary["rejected_source_pages"]["source_sha256_mismatch"] == 1
    finally:
        shutil.rmtree(root)
