import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_wave245c_panasonic_is_exact_no_repeat_and_fail_closed() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/build-rb-wave245c-panasonic-evidence.py")], cwd=ROOT, check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == {"scope": 2, "identity_description_pass": 1, "duplicate_hold": 1, "media_rights_hold": 2}
    identities = json.loads((ROOT / "docs/imports/rb-verified-oem-identities-wave245c-panasonic-2026-07-30.json").read_text(encoding="utf-8"))
    descriptions = json.loads((ROOT / "docs/imports/rb-source-backed-descriptions-wave245c-panasonic-2026-07-30.json").read_text(encoding="utf-8"))
    assert [row["external_id"] for row in identities["products"]] == ["bitrix:3232"]
    assert descriptions["products"][0]["technical_attributes"]["Номинальная ёмкость (20 ч)"] == "7,8 А·ч"
    duplicates = json.loads((ROOT / "docs/audits/generated/rb-wave245c-panasonic-duplicate-review.json").read_text(encoding="utf-8"))
    held = next(row for row in duplicates["pairs"] if row["bitrix_external_id"] == "bitrix:1598")
    assert {row["external_id"] for row in held["live_1c_candidates"]} == {"КА-00003724", "КА-00005218"}
    assert held["collapse_manifest_emitted"] is False
    media = json.loads((ROOT / "docs/audits/generated/rb-wave245c-panasonic-media-review.json").read_text(encoding="utf-8"))
    assert len(media["candidates"]) == 2
    assert all(row["visual_review"]["result"].startswith("PASS_EXACT") and row["safe_to_import"] is False for row in media["candidates"])
    assert media["verified_media_import_manifest_emitted"] is False
