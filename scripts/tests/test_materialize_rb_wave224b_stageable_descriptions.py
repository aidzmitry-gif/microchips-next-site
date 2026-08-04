from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
GEN = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
SCRIPT = ROOT / "scripts/materialize-rb-wave224b-stageable-descriptions.py"
SOURCE = IMPORTS / "rb-source-backed-description-candidates-wave223b-2026-07-29.json"
MANIFEST = IMPORTS / "rb-source-backed-description-stageable-wave224b-2026-07-29.json"
LEDGER = GEN / "rb-wave224b-stageable-description-materialization.csv"
SUMMARY = GEN / "rb-wave224b-stageable-description-materialization.summary.json"
WAVE220 = IMPORTS / "rb-source-backed-description-drafts-wave220-2026-07-29.json"
WAVE223A = GEN / "rb-enrichment-queue-wave223c-a-ups-industrial.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def module():
    spec = importlib.util.spec_from_file_location("wave224b", SCRIPT)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_wave224b_materialization_is_deterministic_and_exact() -> None:
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    first = tuple(sha256(path) for path in (MANIFEST, LEDGER, SUMMARY))
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True, capture_output=True)
    assert first == tuple(sha256(path) for path in (MANIFEST, LEDGER, SUMMARY))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["products"]
    materialized = json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]
    assert len(source) == len(materialized) == 294
    assert [row["external_id"] for row in materialized] == [row["external_id"] for row in source]


def test_wave224b_source_pins_registry_and_laravel_contract() -> None:
    mod = module()
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["products"]
    materialized = json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]
    ledger = {row["external_id"]: row for row in rows(LEDGER)}
    by_id = {row["external_id"]: row for row in materialized}
    assert set(by_id) == set(ledger) == {row["external_id"] for row in source}
    assert set(mod.TRUSTED_SOURCE_REGISTRY) >= {row["source_url"] for row in materialized}
    for candidate in source:
        path = ROOT / candidate["source_manifest"]
        original = json.loads(path.read_text(encoding="utf-8-sig"))["products"]
        original = [row for row in original if row.get("external_id") == candidate["external_id"]]
        assert len(original) == 1 and sha256(path) == candidate["source_manifest_sha256"]
        product = by_id[candidate["external_id"]]
        pinned = original[0]
        assert {"external_id", "identity_scope", "manufacturer", "model_core", "technology", "source_url", "technical_attributes", "source_kind", "source_tier", "source_publisher", "manufacturer_primary", "evidence_scope", "checked_at"} == set(product)
        assert all(key not in product for key in ("description", "description_candidate", "apply_intent", "source_manifest", "source_manifest_sha256"))
        assert tuple(product[key] for key in ("manufacturer", "model_core", "technology", "technical_attributes", "source_url")) == tuple(pinned[key] for key in ("manufacturer", "model_core", "technology", "technical_attributes", "source_url"))
        host, publisher, kind = mod.TRUSTED_SOURCE_REGISTRY[product["source_url"]]
        assert urlparse(product["source_url"]).hostname == host
        assert (product["source_publisher"], product["source_kind"], product["source_tier"], product["manufacturer_primary"], product["identity_scope"], product["evidence_scope"]) == (publisher, kind, "manufacturer_primary", True, "model_core", "model_core")
        assert ledger[product["external_id"]]["source_manifest_sha256"] == ledger[product["external_id"]]["source_manifest_actual_sha256"] == candidate["source_manifest_sha256"]


def test_wave224b_nonoverlap_and_zero_mutation_intent() -> None:
    stage_ids = {row["external_id"] for row in json.loads(MANIFEST.read_text(encoding="utf-8"))["products"]}
    wave220_ids = {row["external_id"] for row in json.loads(WAVE220.read_text(encoding="utf-8"))["products"]}
    wave223a_ids = {row["product_external_id"] for row in rows(WAVE223A)}
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert not stage_ids & wave220_ids and not stage_ids & wave223a_ids
    assert summary["nonoverlap_guards"]["wave220_overlap"] == summary["nonoverlap_guards"]["wave223a_overlap"] == 0
    assert summary["safety"] == {"database_operations": 0, "apply_performed": False, "commercial_changes": 0, "media_changes": 0, "publication_changes": 0, "url_changes": 0, "identity_changes": 0}
