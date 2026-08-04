import csv
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).parents[1] / "extract-bitrix-staging-media.py"


def test_extracts_valid_raster_and_keeps_it_staging_only(tmp_path: Path) -> None:
    image_bytes = io.BytesIO()
    Image.new("RGB", (8, 6), "red").save(image_bytes, format="PNG")
    archive = tmp_path / "upload.tar"
    with tarfile.open(archive, "w") as handle:
        info = tarfile.TarInfo("_shared/upload/a/test.png")
        info.size = len(image_bytes.getvalue())
        handle.addfile(info, io.BytesIO(image_bytes.getvalue()))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"records": [{
        "legacy_element_id": "10", "legacy_name": "Legacy", "detail_picture_file_id": "20",
    }]}), encoding="utf-8")
    references = tmp_path / "refs.json"
    references.write_text(json.dumps([{
        "file_id": "20", "legacy_upload_path": "upload/a/test.png",
    }]), encoding="utf-8")
    output_dir = tmp_path / "assets"
    output_csv = tmp_path / "assets.csv"
    summary = tmp_path / "summary.json"

    subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(manifest),
        "--references", str(references), "--archive", str(archive),
        "--output-dir", str(output_dir), "--output-csv", str(output_csv),
        "--summary", str(summary)], check=True)

    with output_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["decision"] == "staging_only_not_identity_verified"
    assert rows[0]["width"] == "8"
    assert (output_dir / rows[0]["asset_file"]).is_file()
