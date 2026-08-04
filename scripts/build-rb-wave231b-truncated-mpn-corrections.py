"""Build the guarded Wave231-B manifest for proven legacy MPN truncations.

This is deliberately a manifest builder, not a catalogue writer.  The resulting
JSON is accepted by ``catalog:correct-truncated-mpn`` in dry-run or apply mode.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/audits/generated/rb-wave231a-media-mpn-audit.csv"
REGISTRY = ROOT / "docs/audits/sources/wave211c-stationary/source-registry.json"
ASSET_ROOT = ROOT / ".tmp/wave227-assets"
OUTPUT = ROOT / "docs/imports/rb-truncated-mpn-corrections-wave231b-2026-07-29.json"
EXTRACTION = OUTPUT.with_name("rb-truncated-mpn-corrections-wave231b-2026-07-29.extraction.txt")
CHECKED_AT = "2026-07-29"
RIGHTS_BASIS = "Company-owned Microchips legacy Bitrix upload backup."
SOURCE_ID = "exide-sonnenschein-solar-block.pdf"

# These are the two, and only the two, audit findings classified as a strict
# prefix truncation.  2808 is intentionally excluded: its MPN is sound and its
# image is the defect.
TARGETS = {
    "bitrix:2831": {
        "current_mpn": "S 12/17",
        "corrected_mpn": "S 12/17 G5",
        "visible_mpn": "S12/17 G5",
        "evidence_pattern": r"S12/17 G5\s+NGS0120017HS0BA\s+12\s+17\.0\s+0\.17",
    },
    "bitrix:3117": {
        "current_mpn": "S 12/6",
        "corrected_mpn": "S 12/6.6 S",
        "visible_mpn": "S12/6.6 S",
        "evidence_pattern": r"S12/6\.6 S\s+NGS01206D6HS0SA\s+12\s+6\.60\s+0\.06",
    },
}
EXPECTED_NAMES = {
    "bitrix:2831": "Аккумулятор Sonnenschein Dryfit Solar S 12/17 G5 для ИБП (GEL, 17Ah)",
    "bitrix:3117": "Аккумулятор Sonnenschein Dryfit Solar S 12/6.6 S для ИБП (GEL, 6.6Ah)",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def compact_pdf_text(path: Path) -> str:
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return re.sub(r"\s+", " ", text).strip()


def is_cp1251_utf8_mojibake(value: str) -> bool:
    """Detect UTF-8 bytes that were decoded as Windows-1251, e.g. ``Рђ``."""
    try:
        return value.encode("cp1251").decode("utf-8") != value
    except UnicodeError:
        return False


def main() -> None:
    with AUDIT.open(encoding="utf-8-sig", newline="") as handle:
        audit = {row["product_external_id"]: row for row in csv.DictReader(handle)}
    if not set(TARGETS).issubset(audit):
        raise SystemExit("Wave231-A audit does not contain the two required targets")

    registry = {item["source_id"]: item for item in json.loads(REGISTRY.read_text(encoding="utf-8"))["sources"]}
    source = registry[SOURCE_ID]
    source_path = ROOT / source["snapshot_path"]
    if (
        source["source_kind"] != "official_manufacturer_catalogue"
        or not source["source_url"].startswith("https://www.exidegroup.com/")
        or digest(source_path) != source["snapshot_sha256"]
    ):
        raise SystemExit("Pinned official Exide Solar source drift")
    official_text = compact_pdf_text(source_path)
    # This immutable UTF-8 extraction travels with the manifest into the
    # container.  The command checks both its hash and inclusion of each
    # concise evidence line; the builder binds it to the pinned PDF above.
    EXTRACTION.write_text(official_text + "\n", encoding="utf-8", newline="\n")
    extraction_hash = digest(EXTRACTION)

    corrections = []
    for external_id, target in TARGETS.items():
        row = audit[external_id]
        if (
            row["audit_classification"] != "current_mpn_truncated"
            or row["live_product_name"] != EXPECTED_NAMES[external_id]
            or is_cp1251_utf8_mojibake(row["live_product_name"])
            or row["current_mpn"] != target["current_mpn"]
            or row["visible_label"] != target["visible_mpn"]
            or row["official_source_id"] != SOURCE_ID
            or row["official_source_sha256"] != source["snapshot_sha256"]
            or row["apply_status"] != "not_applied"
        ):
            raise SystemExit(f"{external_id}: Wave231-A audit pin drift")
        if not normalized(target["corrected_mpn"]).startswith(normalized(target["current_mpn"])):
            raise SystemExit(f"{external_id}: correction is not a strict prefix extension")
        evidence = re.search(target["evidence_pattern"], official_text)
        if evidence is None:
            raise SystemExit(f"{external_id}: official PDF no longer contains the exact evidence line")
        asset = ASSET_ROOT / row["media_storage_key"]
        if not asset.is_file() or digest(asset) != row["media_sha256"]:
            raise SystemExit(f"{external_id}: local company-owned media artifact hash drift")
        evidence_text = evidence.group(0)
        corrections.append(
            {
                "external_id": external_id,
                "current_name": row["live_product_name"],
                "manufacturer": "Sonnenschein",
                "current_mpn": target["current_mpn"],
                "corrected_mpn": target["corrected_mpn"],
                "source_url": source["source_url"],
                "source_kind": source["source_kind"],
                "source_snapshot_path": source_path.name,
                "source_snapshot_sha256": source["snapshot_sha256"],
                "source_extraction_path": EXTRACTION.name,
                "source_extraction_sha256": extraction_hash,
                "source_evidence_text": evidence_text,
                "source_evidence_text_sha256": hashlib.sha256(evidence_text.encode()).hexdigest(),
                "media_id": int(row["media_id"]),
                "media_content_sha256": row["media_sha256"],
                "storage_path": row["media_storage_key"],
                "rights_basis": RIGHTS_BASIS,
                "observed_visible_mpn": target["visible_mpn"],
                "checked_at": CHECKED_AT,
                "review_note": "Wave231-A: official Exide text and company-owned visible label prove a strict legacy MPN truncation.",
            }
        )

    manifest = {"locale": "ru-BY", "corrections": corrections}
    # ASCII-escaped JSON is still UTF-8 JSON, while being immune to a host
    # PowerShell code page rendering the Cyrillic current_name as mojibake.
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(corrections)} guarded corrections")


if __name__ == "__main__":
    main()
