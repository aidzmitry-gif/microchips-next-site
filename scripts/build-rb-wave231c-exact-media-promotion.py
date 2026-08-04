"""Build the Wave231-C exact legacy-preview-media promotion manifest.

The builder is intentionally offline and fail-closed: the promotion command
will independently re-check every current DB/media pin before it can apply.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/audits/generated/rb-wave231a-media-mpn-audit.csv"
CORRECTIONS = ROOT / "docs/imports/rb-truncated-mpn-corrections-wave231b-2026-07-29.json"
ASSET_ROOT = ROOT / ".tmp/wave227-assets"
OUTPUT = ROOT / "docs/imports/rb-legacy-exact-preview-media-wave231c-2026-07-29.json"
REVIEWED_AT = "2026-07-29"
RIGHTS_BASIS = "Company-owned Microchips legacy Bitrix upload backup."

TARGETS = {
    "bitrix:2831": {"mpn": "S 12/17 G5", "visible_label": "S12/17 G5"},
    "bitrix:3117": {"mpn": "S 12/6.6 S", "visible_label": "S12/6.6 S"},
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def main() -> None:
    with AUDIT.open(encoding="utf-8-sig", newline="") as handle:
        audit = {row["product_external_id"]: row for row in csv.DictReader(handle)}
    corrections = {
        row["external_id"]: row
        for row in json.loads(CORRECTIONS.read_text(encoding="utf-8"))["corrections"]
    }
    if not set(TARGETS).issubset(audit) or not set(TARGETS).issubset(corrections):
        raise SystemExit("Wave231 prerequisite audit or correction manifest scope drift")

    images = []
    for external_id, target in TARGETS.items():
        audit_row = audit[external_id]
        correction = corrections[external_id]
        if (
            audit_row["audit_classification"] != "current_mpn_truncated"
            or audit_row["apply_status"] != "not_applied"
            or audit_row["visible_label"] != target["visible_label"]
            or correction["corrected_mpn"] != target["mpn"]
            or normalized(correction["observed_visible_mpn"]) != normalized(target["mpn"])
            or correction["media_id"] != int(audit_row["media_id"])
            or correction["media_content_sha256"] != audit_row["media_sha256"]
            or correction["storage_path"] != audit_row["media_storage_key"]
            or correction["rights_basis"] != RIGHTS_BASIS
        ):
            raise SystemExit(f"{external_id}: corrected MPN or Wave231-A media audit pin drift")
        asset = ASSET_ROOT / audit_row["media_storage_key"]
        if not asset.is_file() or digest(asset) != audit_row["media_sha256"]:
            raise SystemExit(f"{external_id}: local company-owned media artifact hash drift")
        images.append(
            {
                "external_id": external_id,
                "media_id": int(audit_row["media_id"]),
                "content_sha256": audit_row["media_sha256"],
                "storage_path": audit_row["media_storage_key"],
                "rights_basis": RIGHTS_BASIS,
                "identity_scope": "exact",
                "mpn": target["mpn"],
                "identity_evidence_level": "visible_exact_mpn",
                "visual_verification_note": (
                    f"Wave231-A visual inspection of the company-owned original shows the exact visible "
                    f"label {target['visible_label']}; it matches the corrected product MPN."
                ),
                "reviewed_at": REVIEWED_AT,
            }
        )

    # ASCII JSON keeps the manifest display-stable across Windows host code pages.
    OUTPUT.write_text(json.dumps({"locale": "ru-BY", "images": images}, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(images)} exact preview promotions")


if __name__ == "__main__":
    main()
