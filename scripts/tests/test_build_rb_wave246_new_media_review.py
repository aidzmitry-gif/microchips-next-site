import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs/audits/generated/rb-wave246-new-media-review.csv"
INDEX = ROOT / "docs/audits/generated/rb-wave246-new-media-review/index.json"


def test_wave246_new_media_freeze_excludes_prior_reviews_and_pins_sheets():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build-rb-wave246-new-media-review.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with LEDGER.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 16
    assert len({(row["external_id"], row["media_id"]) for row in rows}) == 16
    assert all(row["prior_review_overlap"] == "false" for row in rows)
    assert all(row["visual_decision"] == "PENDING_MACHINE_VISION" for row in rows)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assert index["export_rows"] == 292
    assert index["excluded_prior_review"] == 276
    assert index["new_rows"] == 16
    assert len(index["contact_sheets"]) == 2
    for sheet in index["contact_sheets"]:
        path = ROOT / sheet["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sheet["sha256"]
        assert len(sheet["rows"]) == 8
    assert index["database_mutations"] == 0
    assert index["automatic_promotions"] == 0
