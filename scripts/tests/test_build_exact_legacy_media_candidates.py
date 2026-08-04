import csv
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-exact-legacy-media-candidates.py"
SPEC = importlib.util.spec_from_file_location("exact_legacy_media", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_emits_only_unique_exact_name_with_both_media(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"products": [{"external_id": "A"}, {"external_id": "B"}]}), encoding="utf-8")
    queue = tmp_path / "queue.csv"
    legacy = tmp_path / "legacy.csv"
    output = tmp_path / "out.csv"
    write_csv(queue, [{"product_external_id": "A", "name": "Battery Ё-1"},
                      {"product_external_id": "B", "name": "Ambiguous"}])
    write_csv(legacy, [
        {"legacy_element_id": "1", "name": "Battery Е 1", "preview_picture_file_id": "10", "detail_picture_file_id": "11"},
        {"legacy_element_id": "2", "name": "Ambiguous", "preview_picture_file_id": "20", "detail_picture_file_id": "21"},
        {"legacy_element_id": "3", "name": "Ambiguous", "preview_picture_file_id": "30", "detail_picture_file_id": "31"},
    ])
    summary = MODULE.build(manifest, queue, legacy, output)
    rows = list(csv.DictReader(output.open(encoding="utf-8-sig")))
    assert summary["candidates"] == 1
    assert summary["ambiguous_exact_names"] == 1
    assert rows[0]["external_id"] == "A"
    assert rows[0]["decision"] == "requires_exact_model_visual_check"
