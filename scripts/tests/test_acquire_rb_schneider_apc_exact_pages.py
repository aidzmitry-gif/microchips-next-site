from __future__ import annotations

import csv
import hashlib
import importlib.util
import shutil
import sys
import uuid
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "acquire-rb-schneider-apc-exact-pages.py"
SPEC = importlib.util.spec_from_file_location("schneider_acquire", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def root() -> Path:
    value = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-schneider-acquire-{uuid.uuid4().hex}"
    value.mkdir(parents=True)
    return value


def candidates(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["external_id", "model_token", "safe_to_apply"])
        writer.writeheader(); writer.writerows(rows)


def test_acquires_exact_sku_from_locale_redirect_and_writes_sha_registry() -> None:
    tmp = root()
    try:
        candidate_path = tmp / "candidates.csv"
        candidates(candidate_path, [{"external_id": "bitrix:1", "model_token": "APCRBC123", "safe_to_apply": "false"}])
        body = b'<html><head><meta name="description" content="APC APCRBC123 replacement cartridge"></head><body></body></html>'

        def fake_fetch(url: str, timeout: float) -> object:
            assert url == "https://www.se.com/us/en/product/APCRBC123/"
            return MODULE.FetchResult(
                "https://www.se.com/us/en/product/APCRBC123/apc-replacement-battery-cartridge/",
                body,
            )

        summary = MODULE.acquire(candidate_path, tmp / "registry.csv", tmp / "summary.json", tmp / "snapshots", fetcher=fake_fetch)
        rows = list(csv.DictReader((tmp / "registry.csv").open(encoding="utf-8-sig")))
        assert summary["acquired_records"] == 1 and summary["technical_facts_parsed"] == 0
        assert rows[0]["acquisition_status"] == "acquired"
        assert rows[0]["page_evidence_field"] == "meta"
        assert rows[0]["source_sha256"] == hashlib.sha256(body).hexdigest()
        assert Path(rows[0]["snapshot_path"]).read_bytes() == body
        assert rows[0]["safe_to_apply"] == "false"
    finally:
        shutil.rmtree(tmp)


def test_holds_redirect_to_non_schneider_or_page_without_exact_sku() -> None:
    tmp = root()
    try:
        candidate_path = tmp / "candidates.csv"
        candidates(candidate_path, [
            {"external_id": "bitrix:1", "model_token": "RBC31", "safe_to_apply": "false"},
            {"external_id": "bitrix:2", "model_token": "APCRBC105", "safe_to_apply": "false"},
        ])

        def fake_fetch(url: str, timeout: float) -> object:
            if "RBC31" in url:
                return MODULE.FetchResult("https://example.test/product/RBC31/", b"<h1>RBC31</h1>")
            return MODULE.FetchResult("https://www.se.com/ca/en/product/APCRBC105/", b"<h1>APCRBC106</h1>")

        summary = MODULE.acquire(candidate_path, tmp / "registry.csv", tmp / "summary.json", tmp / "snapshots", fetcher=fake_fetch)
        rows = list(csv.DictReader((tmp / "registry.csv").open(encoding="utf-8-sig")))
        assert summary["acquired_records"] == 0 and summary["held_records"] == 2
        assert summary["rejected_counts"] == {"exact_sku_not_in_h1_h2_meta_or_json": 1, "final_url_not_exact_first_party_product": 1}
        assert {row["hold_reason"] for row in rows} == set(summary["rejected_counts"])
        assert not list((tmp / "snapshots").glob("*.html"))
    finally:
        shutil.rmtree(tmp)


def test_rejects_apply_safe_or_non_exact_tokens_before_network() -> None:
    tmp = root()
    try:
        path = tmp / "bad.csv"
        candidates(path, [{"external_id": "bitrix:1", "model_token": "APC RBC 123", "safe_to_apply": "true"}])
        try:
            MODULE.acquire(path, tmp / "registry.csv", tmp / "summary.json", tmp / "snapshots")
        except ValueError as error:
            assert "model_token" in str(error)
        else:
            raise AssertionError("invalid candidate input was accepted")
    finally:
        shutil.rmtree(tmp)
