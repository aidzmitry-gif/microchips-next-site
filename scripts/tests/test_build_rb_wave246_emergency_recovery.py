import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-rb-wave246-emergency-recovery.py"
VALIDATOR = Path(__file__).parents[1] / "validate-rb-description-manifest-contract.php"
FIXTURE_ROOT = Path(__file__).parent / "fixtures/wave246_emergency_recovery"
ROOT = Path(__file__).parents[2]
REAL_DESCRIPTION_MANIFEST = ROOT / "docs/audits/generated/rb-wave246-recovery-source-backed-descriptions.json"


def dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def target(path: Path, preview_category: str = "seo:batteries-ups") -> None:
    fields = ["product_external_id", "manufacturer", "mpn", "category_external_id", "has_applied_description"]
    rows = [
        ["manufacturer:acme:M1", "Acme", "M1", "seo:batteries-ups", "true"],
        ["КА-1", "Acme", "M2", preview_category, "true"],
        ["bitrix:1", "Acme", "M3", "seo:batteries-ups", "true"],
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)


def fixtures(case: str, preview_category: str = "seo:batteries-ups") -> tuple[Path, Path, Path]:
    root = FIXTURE_ROOT / case
    imports = root / "docs/imports"
    output = root / "out"
    target_path = root / "target.csv"
    target(target_path, preview_category)
    dump(imports / "rb-manufacturer-product-candidates-wave1.json", {"products": [{
        "external_id": "manufacturer:acme:M1", "manufacturer": "Acme", "mpn": "M1",
        "category_external_id": "seo:batteries-ups", "name": "Acme M1",
    }]})
    dump(imports / "rb-source-backed-description-drafts-wave1.json", {"products": [
        {"external_id": "manufacturer:acme:M1", "manufacturer": "Acme", "mpn": "M1", "source_url": "https://acme.test/m1", "source_kind": "legacy free-text kind", "technology": "AGM", "technical_attributes": {"V": "12"}},
        {"external_id": "КА-1", "manufacturer": "Acme", "mpn": "M2", "source_url": "https://acme.test/m2", "technology": "sealed VRLA AGM", "technical_attributes": {"V": "12", "Технология": "VRLA AGM"}},
        {"external_id": "bitrix:1", "manufacturer": "Acme", "mpn": "M3", "source_url": "https://acme.test/m3", "technology": "AGM", "technical_attributes": {"V": "12"}},
    ]})
    dump(imports / "rb-source-verified-preview-wave-1.json", {"products": [
        {"external_id": "manufacturer:acme:M1", "manufacturer": "Acme", "mpn": "M1", "category_slug": "catalog/industrial-batteries/batteries-ups", "product_slug": "acme-m1"},
        {"external_id": "КА-1", "manufacturer": "Acme", "mpn": "M2", "category_slug": "catalog/industrial-batteries/batteries-ups", "product_slug": "acme-m2"},
    ]})
    return target_path, imports, output


def run(target_path: Path, imports: Path, output: Path, root: Path,
        verified_price_evidence: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    command = [
        sys.executable, str(SCRIPT), "--target", str(target_path), "--imports-dir", str(imports),
        "--output-dir", str(output), "--repo-root", str(root),
    ]
    if verified_price_evidence is not None:
        command.extend(["--verified-price-evidence", str(verified_price_evidence)])
    return subprocess.run(
        command,
        text=True, capture_output=True, encoding="utf-8", check=False, env=env,
    )


def php_validator_command(manifest: Path) -> list[str] | None:
    php = shutil.which("php")
    if not php:
        return None
    command = [php]
    extension = Path(php).parent / "ext/php_mbstring.dll"
    if extension.is_file():
        command.extend(["-d", f"extension_dir={extension.parent}", "-d", f"extension={extension.name}"])
    return [*command, str(VALIDATOR), str(manifest)]


def test_build_is_complete_pinned_and_byte_deterministic() -> None:
    root = FIXTURE_ROOT / "success"
    target_path, imports, output = fixtures("success")
    first = run(target_path, imports, output, root)
    assert first.returncode == 0, first.stderr
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    second = run(target_path, imports, output, root)
    assert second.returncode == 0, second.stderr
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}
    summary = json.loads((output / "rb-wave246-recovery.summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ready"
    assert summary["manufacturer"]["selected"] == 1
    assert summary["descriptions"]["selected"] == 3
    assert summary["preview_publication"]["selected"] == 2
    assert all(len(item["sha256"]) == 64 for item in summary["input_pins"])
    manufacturer = json.loads((output / "rb-wave246-recovery-manufacturer-product-candidates.json").read_text(encoding="utf-8"))
    assert manufacturer["schema_version"] == 1
    assert manufacturer["site_key"] == "microchips-by"
    assert manufacturer["products"]
    descriptions = json.loads((output / "rb-wave246-recovery-source-backed-descriptions.json").read_text(encoding="utf-8"))
    assert descriptions["legacy_partial_provenance_omissions"] == ["manufacturer:acme:M1"]
    assert "source_kind" not in descriptions["products"][0]
    assert descriptions["technology_normalizations"] == ["КА-1"]
    assert descriptions["products"][1]["technology"] == "VRLA AGM"
    command = php_validator_command(output / "rb-wave246-recovery-source-backed-descriptions.json")
    if command:
        contract = subprocess.run(
            command,
            text=True, capture_output=True, encoding="utf-8", check=False,
        )
        assert contract.returncode == 0, contract.stderr
        assert json.loads(contract.stdout)["products"] == 3


def test_unresolved_category_drift_writes_diagnostics_and_fails() -> None:
    root = FIXTURE_ROOT / "blocked"
    target_path, imports, output = fixtures("blocked", preview_category="seo:primary-cells")
    result = run(target_path, imports, output, root)
    assert result.returncode == 2
    summary = json.loads((output / "rb-wave246-recovery.summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "blocked_unresolved"
    assert summary["preview_publication"]["selected"] == 1
    assert summary["preview_publication"]["unresolved"][0]["external_id"] == "КА-1"


def test_final_wave246_resolves_four_preview_holds_from_pinned_evidence() -> None:
    repo = Path(__file__).resolve().parents[2]
    output = FIXTURE_ROOT / "actual" / "out"
    result = run(
        repo / "docs/audits/generated/rb-full-content-readiness-wave246-after.csv",
        repo / "docs/imports",
        output,
        repo,
        repo / "docs/imports/rb-emergency-recovery-price-evidence-wave246-2026-07-30.csv",
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads((output / "rb-wave246-recovery.summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "ready"
    assert summary["preview_publication"]["target"] == 649
    assert summary["preview_publication"]["selected"] == 649
    assert summary["preview_publication"]["unresolved"] == []
    assert summary["preview_publication"]["verified_price_authorizations"] == 34
    assert len(summary["preview_publication"]["applied_description_source_realignments"]) == 88
    assert len(summary["preview_publication"]["applied_description_model_core_realignments"]) == 2
    resolutions = summary["preview_publication"]["recovery_resolutions"]
    assert {row["external_id"] for row in resolutions} == {
        "КА-00005774", "КА-00000471", "КА-00004972", "КА-00002676",
    }
    assert all(row["decision"] == "SAFE_EXACT_RECOVERY_PREVIEW" for row in resolutions)

    manifest = json.loads((output / "rb-wave246-recovery-preview-publication.json").read_text(encoding="utf-8"))
    rows = {row["external_id"]: row for row in manifest["products"]}
    assert sum(row.get("allow_verified_price") is True for row in rows.values()) == 34
    assert rows["КА-00003582"]["allow_verified_price"] is True
    descriptions = json.loads((output / "rb-wave246-recovery-source-backed-descriptions.json").read_text(encoding="utf-8"))
    description_sources = {row["external_id"]: row["source_url"] for row in descriptions["products"]}
    assert all(row["source_url"] == description_sources[external_id] for external_id, row in rows.items())
    expected = {
        "КА-00005774": ("APCRBC123", "catalog/industrial-batteries/batteries-ups"),
        "КА-00000471": ("GP12170", "catalog/industrial-batteries/batteries-ups"),
        "КА-00004972": ("HRL 12650W", "catalog/industrial-batteries/batteries-ups"),
        "КА-00002676": ("B9-500", "catalog/power-systems/power-supplies"),
    }
    for external_id, (identity, category_slug) in expected.items():
        row = rows[external_id]
        assert row["identity_scope"] == "model_core"
        assert row["model_core"] == identity
        assert row["category_slug"] == category_slug
        assert row["replace_categories"] is True
        assert "allow_verified_price" not in row


def test_real_combined_description_manifest_matches_every_php_contract_row() -> None:
    assert REAL_DESCRIPTION_MANIFEST.is_file()
    command = php_validator_command(REAL_DESCRIPTION_MANIFEST)
    assert command is not None
    contract = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", check=False)
    assert contract.returncode == 0, contract.stderr
    assert json.loads(contract.stdout)["products"] == 1321
