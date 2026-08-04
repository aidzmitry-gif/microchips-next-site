#!/usr/bin/env python3
"""Freeze and render the 16 genuinely new company-owned media candidates."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "docs/audits/generated/rb-wave246-legacy-preview-candidates.csv"
PRIOR = ROOT / "docs/audits/generated/rb-wave237-reviewed-media-skip-ledger.csv"
ASSETS = ROOT / ".tmp/wave246-assets"
OUT = ROOT / "docs/audits/generated/rb-wave246-new-media-review"
LEDGER = ROOT / "docs/audits/generated/rb-wave246-new-media-review.csv"
INDEX = OUT / "index.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_asset(storage_path: str) -> Path:
    relative = Path(storage_path.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"Unsafe storage path: {storage_path}")
    path = (ASSETS / relative).resolve()
    if ASSETS.resolve() not in path.parents:
        raise RuntimeError(f"Asset escapes root: {storage_path}")
    return path


def render_sheet(rows: list[dict[str, str]], number: int) -> Path:
    width, height = 360, 300
    sheet = Image.new("RGB", (width * 4, height * 2), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)
    for index, row in enumerate(rows):
        image = Image.open(row["asset_path"]).convert("RGB")
        image.thumbnail((320, 220), Image.Resampling.LANCZOS)
        x = (index % 4) * width
        y = (index // 4) * height
        sheet.paste(image, (x + (width - image.width) // 2, y + 4))
        expected = row["mpn"] or row["model_core"]
        draw.text((x + 8, y + 230), f"{row['external_id']} | media {row['media_id']}", fill="black", font=font)
        draw.text((x + 8, y + 252), f"expected: {expected}", fill="black", font=font)
        draw.rectangle((x, y, x + width - 1, y + height - 1), outline="#777", width=1)
    path = OUT / f"sheet-{number:02d}.png"
    sheet.save(path, format="PNG")
    return path


def main() -> None:
    exported = read_csv(EXPORT)
    prior = {(row["external_id"], row["media_id"]) for row in read_csv(PRIOR)}
    rows = [row for row in exported if (row["external_id"], row["media_id"]) not in prior]
    if len(exported) != 292 or len(prior.intersection({(row['external_id'], row['media_id']) for row in exported})) != 276:
        raise RuntimeError("Wave246 prior-review cardinality drift")
    if len(rows) != 16:
        raise RuntimeError(f"Expected 16 genuinely new rows, got {len(rows)}")
    OUT.mkdir(parents=True, exist_ok=True)
    enriched = []
    for row in rows:
        asset = safe_asset(row["storage_path"])
        if not asset.is_file() or sha256(asset) != row["content_sha256"].lower():
            raise RuntimeError(f"Missing or hash-mismatched asset for {row['external_id']}")
        with Image.open(asset) as image:
            width, height = image.size
        enriched.append({
            **row,
            "asset_path": str(asset),
            "dimensions": f"{width}x{height}",
            "prior_review_overlap": "false",
            "visual_decision": "PENDING_MACHINE_VISION",
        })
    sheets = []
    for offset in range(0, len(enriched), 8):
        group = enriched[offset:offset + 8]
        sheet = render_sheet(group, len(sheets) + 1)
        sheets.append({
            "path": str(sheet.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256(sheet),
            "rows": [f"{row['external_id']}|{row['media_id']}" for row in group],
        })
    with LEDGER.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(enriched[0]))
        writer.writeheader()
        writer.writerows(enriched)
    result = {
        "schema_version": 1,
        "export_rows": len(exported),
        "excluded_prior_review": 276,
        "new_rows": len(enriched),
        "contact_sheets": sheets,
        "ledger_sha256": sha256(LEDGER),
        "database_mutations": 0,
        "automatic_promotions": 0,
    }
    INDEX.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
