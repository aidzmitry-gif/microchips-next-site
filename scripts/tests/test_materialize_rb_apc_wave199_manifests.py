from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "materialize-rb-apc-wave199-manifests.py"
SPEC = importlib.util.spec_from_file_location("apc_materialize", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CANDIDATE_FIELDS = ["external_id", "model_token", "safe_to_apply"]
HOLD_FIELDS = ["external_id", "model_token", "reason"]
EVIDENCE_FIELDS = [
    "external_id",
    "model_token",
    "source_url",
    "source_snapshot_path",
    "source_sha256",
    "product_type",
    "technology",
    "voltage_v",
    "capacity_ah",
    "capacity_vah",
    "image_url_candidate",
    "image_safe_to_publish",
    "price_or_stock_imported",
    "publisher",
    "evidence_kind",
    "safe_to_apply",
]


def temp() -> Path:
    root = SCRIPT.parents[1] / "docs" / "audits" / "generated" / f"test-apc-materialize-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fixture(root: Path, holds: list[dict[str, str]] | None = None) -> dict[str, object]:
    candidates = root / "candidates.csv"
    evidence = root / "evidence.csv"
    holds_path = root / "holds.csv"
    evidence_summary = root / "evidence-summary.json"
    snapshot = root / "snapshot.html"
    snapshot.write_bytes(b"exact APC RBC7 product snapshot")
    write_csv(
        candidates,
        CANDIDATE_FIELDS,
        [{"external_id": "bitrix:1", "model_token": "RBC7", "safe_to_apply": "false"}],
    )
    evidence_row = {
        "external_id": "bitrix:1",
        "model_token": "RBC7",
        "source_url": "https://www.se.com/us/en/product/RBC7/exact-product/",
        "source_snapshot_path": snapshot.name,
        "source_sha256": MODULE.sha(snapshot),
        "product_type": "replacement_battery_cartridge",
        "technology": "VRLA lead-acid",
        "voltage_v": "24",
        "capacity_ah": "17",
        "capacity_vah": "",
        "image_url_candidate": "https://download.schneider-electric.com/image",
        "image_safe_to_publish": "false",
        "price_or_stock_imported": "false",
        "publisher": "APC by Schneider Electric",
        "evidence_kind": "exact_product_jsonld",
        "safe_to_apply": "false",
    }
    write_csv(evidence, EVIDENCE_FIELDS, [evidence_row])
    write_csv(holds_path, HOLD_FIELDS, holds or [])
    evidence_summary_value = {
        "candidate_sha256": MODULE.sha(candidates),
        "registry_sha256": "b" * 64,
        "output_sha256": MODULE.sha(evidence),
        "candidate_records": 1,
        "registry_records": 1,
        "exact_evidence_records": 1,
        "technical_fact_records": 1,
        "image_candidates_not_publishable": 1,
        "rejected_counts": {},
        "price_or_stock_records": 0,
        "automatic_database_mutations": 0,
        "safe_to_apply_records": 0,
    }
    write_json(evidence_summary, evidence_summary_value)
    return {
        "candidates": candidates,
        "evidence": evidence,
        "holds": holds_path,
        "evidence_summary": evidence_summary,
        "snapshot": snapshot,
        "descriptions": root / "descriptions.json",
        "images": root / "images.csv",
        "summary": root / "summary.json",
        "expected": {
            "candidate": MODULE.sha(candidates),
            "evidence": MODULE.sha(evidence),
            "holds": MODULE.sha(holds_path),
            "evidence_summary": MODULE.sha(evidence_summary),
        },
    }


def build(paths: dict[str, object], **expected_overrides: str) -> dict[str, object]:
    expected = dict(paths["expected"])
    expected.update(expected_overrides)
    return MODULE.build(
        paths["candidates"],
        paths["evidence"],
        paths["holds"],
        paths["evidence_summary"],
        paths["descriptions"],
        paths["images"],
        paths["summary"],
        expected["candidate"],
        expected["evidence"],
        expected["holds"],
        expected["evidence_summary"],
    )


def mutate_evidence(paths: dict[str, object], **changes: str) -> None:
    evidence = paths["evidence"]
    with evidence.open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    row.update(changes)
    write_csv(evidence, EVIDENCE_FIELDS, [row])
    summary_path = paths["evidence_summary"]
    evidence_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    evidence_summary["output_sha256"] = MODULE.sha(evidence)
    write_json(summary_path, evidence_summary)
    paths["expected"]["evidence"] = MODULE.sha(evidence)
    paths["expected"]["evidence_summary"] = MODULE.sha(summary_path)


def mutate_evidence_summary(paths: dict[str, object], **changes: object) -> None:
    summary_path = paths["evidence_summary"]
    evidence_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    evidence_summary.update(changes)
    write_json(summary_path, evidence_summary)
    paths["expected"]["evidence_summary"] = MODULE.sha(summary_path)


def test_builds_exact_description_and_non_publishable_image_review() -> None:
    root = temp()
    try:
        paths = fixture(root)
        summary = build(paths)
        product = json.loads(paths["descriptions"].read_text(encoding="utf-8"))["products"][0]
        with paths["images"].open(encoding="utf-8-sig", newline="") as handle:
            image = next(csv.DictReader(handle))

        assert summary["description_records"] == 1
        assert summary["publishable_image_records"] == 0
        assert summary["partition_candidate_records"] == 1
        assert summary["partition_evidence_records"] == 1
        assert summary["partition_rejected_records"] == 0
        assert summary["identity_holds_sha256"] == MODULE.sha(paths["holds"])
        assert product["display_name"] == "Сменный аккумуляторный картридж APC RBC7"
        assert product["technical_attributes"]["Номинальное напряжение"] == "24 В"
        assert image["safe_to_publish"] == "false"
    finally:
        shutil.rmtree(root)


def test_pinned_hold_removes_collision_from_both_manifests() -> None:
    root = temp()
    try:
        paths = fixture(
            root,
            [{"external_id": "bitrix:1", "model_token": "RBC7", "reason": "existing canonical identity"}],
        )
        summary = build(paths)
        assert summary["description_records"] == 0
        assert summary["image_review_records"] == 0
        assert summary["identity_holds"] == 1
    finally:
        shutil.rmtree(root)


def test_identity_holds_file_is_mandatory() -> None:
    root = temp()
    try:
        paths = fixture(root)
        paths["holds"].unlink()
        with pytest.raises(ValueError, match="identity holds must be an existing file"):
            build(paths)
    finally:
        shutil.rmtree(root)


def test_identity_holds_sha256_must_be_pinned() -> None:
    root = temp()
    try:
        paths = fixture(root)
        with pytest.raises(ValueError, match="identity holds SHA-256 mismatch"):
            build(paths, holds="0" * 64)
    finally:
        shutil.rmtree(root)


def test_evidence_summary_file_and_sha256_are_mandatory() -> None:
    root = temp()
    try:
        paths = fixture(root)
        paths["evidence_summary"].unlink()
        with pytest.raises(ValueError, match="evidence summary must be an existing file"):
            build(paths)
    finally:
        shutil.rmtree(root)


@pytest.mark.parametrize("mode", ["missing", "sha_mismatch"])
def test_source_snapshot_must_exist_and_match_pinned_sha256(mode: str) -> None:
    root = temp()
    try:
        paths = fixture(root)
        if mode == "missing":
            paths["snapshot"].unlink()
        else:
            paths["snapshot"].write_bytes(b"tampered snapshot")
        with pytest.raises(ValueError, match="source snapshot SHA-256 mismatch"):
            build(paths)
    finally:
        shutil.rmtree(root)


@pytest.mark.parametrize(
    "source_url",
    [
        "https://se.com/us/en/product/RBC7/exact-product/",
        "https://www.se.com/us/en/product/RBC8/exact-product/",
        "https://www.se.com/us/en/product/RBC7/exact-product/?tracking=1",
        "https://www.se.com:443/us/en/product/RBC7/exact-product/",
        "http://www.se.com/us/en/product/RBC7/exact-product/",
    ],
)
def test_source_url_must_be_exact_www_se_com_product_url_for_model(source_url: str) -> None:
    root = temp()
    try:
        paths = fixture(root)
        mutate_evidence(paths, source_url=source_url)
        with pytest.raises(ValueError, match="not an exact www.se.com product URL"):
            build(paths)
    finally:
        shutil.rmtree(root)


def test_unknown_technology_is_rejected_without_fallback() -> None:
    root = temp()
    try:
        paths = fixture(root)
        mutate_evidence(paths, technology="lithium-ion")
        with pytest.raises(ValueError, match="unsupported battery technology"):
            build(paths)
    finally:
        shutil.rmtree(root)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"rejected_counts": {"acquisition_hold": 1}}, "does not completely partition"),
        ({"registry_records": 0}, "candidate/registry count mismatch"),
        ({"technical_fact_records": 0}, "technical fact count mismatch"),
        ({"image_candidates_not_publishable": 0}, "image candidate count mismatch"),
    ],
)
def test_evidence_summary_counts_must_match_complete_partition(
    changes: dict[str, object], message: str
) -> None:
    root = temp()
    try:
        paths = fixture(root)
        mutate_evidence_summary(paths, **changes)
        with pytest.raises(ValueError, match=message):
            build(paths)
    finally:
        shutil.rmtree(root)


def test_evidence_summary_output_hash_must_match_evidence() -> None:
    root = temp()
    try:
        paths = fixture(root)
        mutate_evidence_summary(paths, output_sha256="0" * 64)
        with pytest.raises(ValueError, match="summary output SHA-256 mismatch"):
            build(paths)
    finally:
        shutil.rmtree(root)


@pytest.mark.parametrize(
    "field",
    ["price_or_stock_records", "automatic_database_mutations", "safe_to_apply_records"],
)
def test_evidence_summary_prohibited_counts_must_remain_zero(field: str) -> None:
    root = temp()
    try:
        paths = fixture(root)
        mutate_evidence_summary(paths, **{field: 1})
        with pytest.raises(ValueError, match=rf"{field} must be zero"):
            build(paths)
    finally:
        shutil.rmtree(root)


def test_evidence_price_or_stock_flag_must_be_explicitly_false() -> None:
    root = temp()
    try:
        paths = fixture(root)
        mutate_evidence(paths, price_or_stock_imported="true")
        with pytest.raises(ValueError, match="price_or_stock_imported must explicitly be false"):
            build(paths)
    finally:
        shutil.rmtree(root)
