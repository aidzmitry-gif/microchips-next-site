import csv
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "build-full-bitrix-staging-manifest.py"
SPEC = importlib.util.spec_from_file_location("full_bitrix_staging", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def registry_row(bitrix_id: str, path: str, identity: str, **extra: str) -> dict[str, str]:
    return {
        "registry_id": f"bitrix:{bitrix_id}",
        "bitrix_id": bitrix_id,
        "is_active": extra.get("is_active", "true"),
        "name": extra.get("name", f"Product {bitrix_id}"),
        "legacy_section_path": path,
        "legacy_url": f"https://microchips.by/catalog/{path}/{bitrix_id}/",
        "one_c_code": extra.get("one_c_code", ""),
        "identity_status": identity,
        "duplicate_candidate_key": extra.get("duplicate_candidate_key", ""),
    }


def test_builds_complete_fail_closed_manifest(tmp_path: Path) -> None:
    registry = tmp_path / "registry.csv"
    tree = tmp_path / "tree.csv"
    output = tmp_path / "manifest.json"
    fields = [
        "registry_id", "bitrix_id", "is_active", "name", "legacy_section_path",
        "legacy_url", "one_c_code", "identity_status", "duplicate_candidate_key",
    ]
    write_csv(registry, fields, [
        registry_row("1", "batareyki/litievye", "unresolved_identity"),
        registry_row("2", "mikroelektronika/chips", "unresolved_identity"),
        registry_row("3", "akkumulyatory/dlya_ibp/agm", "linked_exact_name", one_c_code="C-3"),
        registry_row("4", "akkumulyatory/dlya_ibp/agm", "duplicate_candidate", duplicate_candidate_key="d1"),
        registry_row("5", "batareyki", "inactive_source", is_active="false"),
    ])
    write_csv(tree, ["slug", "source_rule"], [
        {"slug": "primary-cells", "source_rule": "batareyki"},
        {"slug": "batteries-ups", "source_rule": "akkumulyatory/dlya_ibp"},
        {"slug": "electronic-components", "source_rule": "mikroelektronika"},
    ])

    summary = MODULE.build(registry, tree, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert summary["records"] == 5
    assert summary["status_counts"] == {
        "excluded_inactive_legacy": 1,
        "existing_one_c_exact_link": 1,
        "hold_duplicate_candidate": 1,
        "legacy_only_draft_candidate": 1,
        "scope_excluded_electronics": 1,
    }
    assert all(not row["allow_publication"] for row in payload["records"])
    assert all(not row["allow_indexing"] for row in payload["records"])
    assert all(not row["allow_merge"] for row in payload["records"])
    assert [row["bitrix_id"] for row in payload["records"]] == ["1", "2", "3", "4", "5"]
    assert len({row["source_checksum"] for row in payload["records"]}) == 5


def test_rejects_ambiguous_or_missing_taxonomy(tmp_path: Path) -> None:
    registry = tmp_path / "registry.csv"
    tree = tmp_path / "tree.csv"
    fields = [
        "registry_id", "bitrix_id", "is_active", "name", "legacy_section_path",
        "legacy_url", "one_c_code", "identity_status", "duplicate_candidate_key",
    ]
    write_csv(registry, fields, [registry_row("1", "unknown/path", "unresolved_identity")])
    write_csv(tree, ["slug", "source_rule"], [
        {"slug": "primary-cells", "source_rule": "batareyki"},
    ])

    try:
        MODULE.build(registry, tree, tmp_path / "out.json")
    except ValueError as error:
        assert "maps to 0 SEO leaves" in str(error)
    else:
        raise AssertionError("missing taxonomy must fail closed")

