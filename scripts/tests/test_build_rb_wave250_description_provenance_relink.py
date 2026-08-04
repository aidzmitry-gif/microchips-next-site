from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-rb-wave250-description-provenance-relink.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wave250_provenance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row(index: int) -> dict[str, object]:
    external_id = f"bitrix:{index}"
    mpn = f"M-{index}"
    return {
        "external_id": external_id,
        "product_id": index,
        "site_product_id": index + 1000,
        "name": f"Acme battery {mpn}",
        "manufacturer": "Acme",
        "mpn": mpn,
        "manufacturer_normalized": "acme",
        "mpn_normalized": f"m{index}",
        "short_description": "Verified existing description. " * 9,
        "is_published": True,
        "identity_pair_catalogue_count": 1,
        "matching_applied_description_count": 1,
        "description_source_urls": "[]",
        "description_source_kind": "",
        "description_source_tier": "",
        "description_identity_scope": "",
        "category_external_id": "seo:batteries-industrial",
    }


def test_exact_pinned_artifact_becomes_candidate_and_all_other_rows_remain_research_queue(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    generated = repo / "docs" / "audits" / "generated"
    imports = repo / "docs" / "imports"
    generated.mkdir(parents=True)
    imports.mkdir(parents=True)

    evidence = imports / "official-description-evidence.csv"
    with evidence.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "external_id", "manufacturer", "mpn", "source_url", "source_kind", "source_tier", "identity_scope",
        ])
        writer.writeheader()
        writer.writerow({
            "external_id": "bitrix:1", "manufacturer": "Acme", "mpn": "M-1",
            "source_url": "https://manufacturer.example/M-1.pdf",
            "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary",
            "identity_scope": "exact",
        })

    recovery = generated / "recovery.json"
    recovery.write_text(json.dumps({
        "schema_version": 1,
        "recovery_status": "ready",
        "unresolved": [],
        "input_pins": [{"path": evidence.relative_to(repo).as_posix(), "sha256": digest(evidence)}],
        "products": [
            {
                "external_id": f"bitrix:{index}", "manufacturer": "Acme", "mpn": f"M-{index}",
                "identity_scope": "exact", "source_url": f"https://manufacturer.example/M-{index}.pdf",
            }
            for index in range(1, 404)
        ],
    }), encoding="utf-8")
    snapshot = {"rows": [row(index) for index in range(1, 404)]}

    rows, summary = module.build(snapshot, recovery, repo)

    assert len(rows) == 403
    assert summary["safe_deterministic_relinks"] == 1
    assert summary["research_required"] == 402
    assert summary["conflicts"] == 0
    candidate = summary["candidates"][0]
    assert candidate["product_external_id"] == "bitrix:1"
    assert candidate["candidate_identity_scope"] == "exact"
    assert candidate["evidence_path"] == evidence.relative_to(repo).as_posix()
    assert candidate["evidence_sha256"] == digest(evidence)
    assert summary["quality"] == {
        "network_requests": 0,
        "database_mutations": 0,
        "audited_external_ids_unique": 403,
        "safe_rows_with_exact_evidence_pin": 1,
    }
    assert {item["research_priority"] for item in summary["research_queue"]} == {"P1"}
    assert {item["manufacturer_blocker_count"] for item in summary["research_queue"]} == {"403"}


def test_unicode_identity_matching_is_not_lost_to_console_encoding():
    module = load_module()

    assert module.normalize("Сфера Света") == "сферасвета"
    assert module.name_contains("Аккумулятор СК-1209 промышленный", "СК-1209")
    assert not module.name_contains("Аккумулятор СК-12090 промышленный", "СК-1209")


def test_recovery_pin_drift_is_a_hard_failure(tmp_path: Path):
    module = load_module()
    repo = tmp_path / "repo"
    generated = repo / "docs" / "audits" / "generated"
    imports = repo / "docs" / "imports"
    generated.mkdir(parents=True)
    imports.mkdir(parents=True)
    evidence = imports / "evidence.csv"
    evidence.write_text("external_id,source_url\n", encoding="utf-8")
    recovery = generated / "recovery.json"
    recovery.write_text(json.dumps({
        "schema_version": 1, "recovery_status": "ready", "unresolved": [],
        "input_pins": [{"path": evidence.relative_to(repo).as_posix(), "sha256": "0" * 64}],
        "products": [{"external_id": f"bitrix:{index}"} for index in range(1, 404)],
    }), encoding="utf-8")

    try:
        module.build({"rows": [row(index) for index in range(1, 404)]}, recovery, repo)
    except module.AuditError as error:
        assert "drifted" in str(error)
    else:
        raise AssertionError("drifted evidence pin must fail closed")
