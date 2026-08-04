import csv
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "extract-legacy-media-review-bundle.py"
SPEC = importlib.util.spec_from_file_location("legacy_media_bundle", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_extracts_only_literal_model_identity(tmp_path: Path) -> None:
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "m.json").write_text(json.dumps({"products": [
        {"external_id": "A", "identity_scope": "model_core", "model_core": "GP 1272"},
        {"external_id": "B", "identity_scope": "exact", "mpn": "SMT3000IC"},
    ]}), encoding="utf-8")
    candidates = tmp_path / "c.csv"
    write_csv(candidates, [
        {"external_id": "A", "manufacturer": "CSB", "source_manifest": "m.json", "legacy_element_id": "1",
         "legacy_name": "CSB GP1272", "detail_picture_file_id": "10"},
        {"external_id": "B", "manufacturer": "APC", "source_manifest": "m.json", "legacy_element_id": "2",
         "legacy_name": "INELT GAMMA 3000VA", "detail_picture_file_id": "20"},
    ])
    references = tmp_path / "refs.json"
    references.write_text(json.dumps([
        {"file_id": "10", "file_name": "a.png", "legacy_upload_path": "upload/a.png"},
        {"file_id": "20", "file_name": "b.png", "legacy_upload_path": "upload/b.png"},
    ]), encoding="utf-8")
    archive_path = tmp_path / "media.tar"
    with tarfile.open(archive_path, "w") as archive:
        for name, body in [("_shared/upload/a.png", b"image-a"), ("_shared/upload/b.png", b"image-b")]:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            archive.addfile(info, io.BytesIO(body))
    output_csv = tmp_path / "out.csv"
    summary = MODULE.build(candidates, references, archive_path, manifests, tmp_path / "assets", output_csv)
    rows = list(csv.DictReader(output_csv.open(encoding="utf-8-sig")))
    rejected = list(csv.DictReader(output_csv.with_name("out-rejected.csv").open(encoding="utf-8-sig")))
    assert summary == {"input_candidates": 2, "extracted_for_visual_review": 1,
                       "rejected_before_extraction": 1, "automatic_imports": 0}
    assert rows[0]["external_id"] == "A"
    assert rejected[0]["external_id"] == "B"
