import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave203-pos-evidence.py"
ACQUIRE = ROOT / "scripts/acquire-rb-wave203-verifone-evidence.py"
INPUT = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
REGISTRY = ROOT / "docs/audits/evidence/wave203-pos-official-source-evidence.json"
OUTPUT = ROOT / "docs/audits/generated/wave203-pos-evidence.csv"
SUMMARY = ROOT / "docs/audits/generated/wave203-pos-evidence-summary.json"
SNAPSHOT = ROOT / "docs/audits/sources/verifone-wave203/verifone-se-webshop-2026-07-29.html"
SNAPSHOT_METADATA = ROOT / "docs/audits/sources/verifone-wave203/verifone-se-webshop-2026-07-29.json"
BRANDS = {
    "VeriFone", "Ingenico", "Pax", "Castles", "Dejavoo", "FirstData",
    "Hypercom", "Newpos", "Sagem", "Sunmi", "Bitel",
}


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_builder_is_reproducible_and_covers_only_the_42_new_pos_rows():
    subprocess.run([sys.executable, str(ACQUIRE)], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    first = OUTPUT.read_bytes()
    subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, check=True)
    assert OUTPUT.read_bytes() == first

    candidates = [
        row for row in read_csv(INPUT)
        if row["recommended_wave"] == "wave203"
        and row["repeat_handling"] == "new"
        and row["brand_or_series"] in BRANDS
    ]
    evidence = read_csv(OUTPUT)
    assert len(candidates) == len(evidence) == 42
    assert len({row["product_external_id"] for row in evidence}) == 42
    assert {row["product_external_id"] for row in evidence} == {
        row["product_external_id"] for row in candidates
    }
    assert all(row["repeat_handling"] != "previously_processed" for row in evidence)
    prior_hits = []
    ids = {row["product_external_id"] for row in evidence}
    for path in (ROOT / "docs/audits/generated").glob("*evidence*.csv"):
        if path.resolve() == OUTPUT.resolve():
            continue
        if path.name.startswith("wave203-"):
            continue
        try:
            prior_hits.extend(
                (path.name, row.get("product_external_id") or row.get("external_id"))
                for row in read_csv(path)
                if (row.get("product_external_id") or row.get("external_id")) in ids
            )
        except (OSError, UnicodeDecodeError, csv.Error):
            continue
    assert prior_hits == []


def test_compatibility_and_conflict_rows_never_infer_replacement_identity():
    evidence = read_csv(OUTPUT)
    unsafe = [row for row in evidence if row["partition"] != "exact_safe"]
    assert unsafe
    assert all(not row["replacement_manufacturer"] for row in unsafe)
    assert all(not row["replacement_mpn"] for row in unsafe)
    assert all(row["manufacturer_mpn_inference"] == "none" for row in unsafe)
    assert all(row["safe_to_apply"] == "false" for row in unsafe)

    exact = [row for row in evidence if row["partition"] == "exact_safe"]
    assert len(exact) == 1
    assert exact[0]["product_external_id"] == "bitrix:12398"
    assert exact[0]["replacement_manufacturer"] == "Verifone"
    assert exact[0]["replacement_mpn"] == "BPK268-001-01-A"
    assert exact[0]["safe_to_apply"] == "true"
    assert exact[0]["source_evidence_sha256"]
    assert exact[0]["snapshot_paths"] == SNAPSHOT.relative_to(ROOT).as_posix()
    assert exact[0]["snapshot_sha256s"] == hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()


def test_known_conflict_and_summary_are_pinned_and_reconciled():
    evidence = read_csv(OUTPUT)
    conflict = next(row for row in evidence if row["product_external_id"] == "bitrix:12286")
    assert conflict["partition"] == "conflict"
    assert "2900mAh" in conflict["verified_facts"]
    assert "3000mAh" in conflict["unsupported_legacy_claims"]
    assert not conflict["replacement_mpn"]

    summary = json.loads(SUMMARY.read_text(encoding="utf-8-sig"))
    assert summary["partition_counts"] == {
        "compatibility_only": 18,
        "conflict": 1,
        "exact_safe": 1,
        "no_evidence": 22,
    }
    assert summary["safe_to_apply"] == {
        "rows": 1,
        "external_ids": ["bitrix:12398"],
    }
    assert summary["previously_processed"] == {"rows": 0, "external_ids": []}
    assert summary["policy"]["database_mutations"] == 0
    assert summary["output"]["sha256"] == hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert summary["pinned_evidence_registry"]["sha256"] == hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    official = next(source for source in summary["official_sources"] if source["id"] == "verifone-se-vx680-webshop")
    assert official["snapshot_path"] == SNAPSHOT.relative_to(ROOT).as_posix()
    assert official["snapshot_sha256"] == hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    assert official["snapshot_validation"] == "snapshot_sha256_and_exact_tokens_verified"


def test_pinned_sources_are_https_primary_and_have_facts():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    assert registry["policy"]["primary_sources_only"] is True
    assert len(registry["sources"]) == 7
    assert len({source["id"] for source in registry["sources"]}) == 7
    assert all(source["url"].startswith("https://") for source in registry["sources"])
    assert all(source["publisher"] for source in registry["sources"])
    assert all(source["source_kind"].startswith("official_manufacturer_") for source in registry["sources"])
    assert all(source["pinned_facts"] for source in registry["sources"])


def test_verifone_exact_source_is_a_local_hash_pinned_html_snapshot():
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    source = next(source for source in registry["sources"] if source["id"] == "verifone-se-vx680-webshop")
    data = SNAPSHOT.read_bytes()
    text = data.decode("utf-8", errors="replace").casefold()
    assert source["snapshot_path"] == SNAPSHOT.relative_to(ROOT).as_posix()
    assert source["snapshot_metadata_path"] == SNAPSHOT_METADATA.relative_to(ROOT).as_posix()
    assert source["snapshot_sha256"] == hashlib.sha256(data).hexdigest()
    assert source["required_exact_tokens"] == ["BPK268-001-01-A", "VX680", "Batteripack"]
    assert all(token.casefold() in text for token in source["required_exact_tokens"])

    metadata = json.loads(SNAPSHOT_METADATA.read_text(encoding="utf-8-sig"))
    assert metadata["snapshot_sha256"] == source["snapshot_sha256"]
    assert metadata["required_exact_tokens"] == source["required_exact_tokens"]
    assert all(metadata["token_counts"][token] > 0 for token in source["required_exact_tokens"])
    assert metadata["network_refresh_performed"] is True


def test_exact_candidate_fails_closed_when_snapshot_is_not_reproducible():
    spec = importlib.util.spec_from_file_location("wave203_pos_builder", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    missing = ROOT / "docs/audits/sources/verifone-wave203/__missing-official.html"
    assert not missing.exists()
    source = {
        "id": "verifone-se-vx680-webshop",
        "url": "https://go.verifone.com/sv/se/webshop",
        "publisher": "Verifone Sweden AB",
        "pinned_facts": ["exact part"],
        "snapshot_path": str(missing),
        "snapshot_sha256": "0" * 64,
        "required_exact_tokens": ["BPK268-001-01-A", "VX680", "Batteripack"],
    }
    candidate = {
        "product_external_id": "bitrix:12398",
        "brand_or_series": "VeriFone",
        "name": "Аккумулятор для VeriFone VX680 (BPK268-001-01-A) 1800mah",
        "model_tokens_unverified": "VX680|BPK268-001-01-A|1800mah",
    }
    row = module.classify(candidate, {source["id"]: source})
    assert row["partition"] == "no_evidence"
    assert row["evidence_scope"] == "exact_source_snapshot_invalid_hold"
    assert row["repeat_handling"] == "source_snapshot_invalid"
    assert row["safe_to_apply"] == "false"
    assert not row["replacement_manufacturer"]
    assert not row["replacement_mpn"]
