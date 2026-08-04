import csv
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-reviewed-model-core-preview-media.py"
SPEC = importlib.util.spec_from_file_location("reviewed_preview_media", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_builds_exact_and_model_core_rows_from_nested_site_state(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    bundle = tmp_path / "bundle.csv"
    visual = tmp_path / "visual.csv"
    state = tmp_path / "state.json"
    preview = tmp_path / "preview.json"
    media = tmp_path / "media.json"
    write_csv(candidates, ["external_id", "source_url"], [
        {"external_id": "A", "source_url": "https://manufacturer.test/a"},
        {"external_id": "B", "source_url": "https://dealer.test/b"},
    ])
    write_csv(bundle, ["external_id", "manufacturer", "identity", "identity_scope", "asset_file", "sha256", "archive_member"], [
        {"external_id": "A", "manufacturer": "FIAMM", "identity": "FG10451", "identity_scope": "exact", "asset_file": "a.png", "sha256": "a" * 64, "archive_member": "upload/a.png"},
        {"external_id": "B", "manufacturer": "Delta", "identity": "DT1207", "identity_scope": "model_core", "asset_file": "b.png", "sha256": "b" * 64, "archive_member": "upload/b.png"},
    ])
    write_csv(visual, ["external_id", "verdict", "note"], [
        {"external_id": "A", "verdict": "PASS", "note": "Exact MPN is visible."},
        {"external_id": "B", "verdict": "PASS", "note": "Exact model core is visible."},
    ])
    state.write_text(json.dumps([
        {"price": "12.00", "product": {"external_id": "A"}},
        {"price": None, "product": {"external_id": "B"}},
    ]), encoding="utf-8")

    summary = MODULE.build(candidates, bundle, [visual], state, preview, media, set())
    preview_rows = json.loads(preview.read_text(encoding="utf-8"))["products"]
    media_rows = json.loads(media.read_text(encoding="utf-8"))["images"]

    assert summary["preview_products"] == 2
    assert preview_rows[0]["mpn"] == "FG10451"
    assert preview_rows[0]["allow_verified_price"] is True
    assert "model_core" not in preview_rows[0]
    assert preview_rows[1]["model_core"] == "DT1207"
    assert media_rows[0]["identity_evidence_level"] == "visible_exact_mpn"
    assert media_rows[1]["identity_evidence_level"] == "visible_exact_model_core"
