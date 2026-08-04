#!/usr/bin/env python3
"""Render OCR-PASS legacy images into deterministic visual-review sheets."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = Path("C:/Windows/Fonts/arial.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def build(input_csv: Path, review_csv: Path, output_dir: Path, verdict: str = "PASS", per_sheet: int = 12) -> dict[str, object]:
    source = read_rows(input_csv)
    reviews = read_rows(review_csv)
    if len(source) != len(reviews):
        raise ValueError("OCR input and review row counts differ")

    if verdict not in {"PASS", "HOLD"}:
        raise ValueError("verdict must be PASS or HOLD")
    selected: list[dict[str, str]] = []
    for source_row, review_row in zip(source, reviews, strict=True):
        if Path(source_row["image_path"]).resolve() != Path(review_row["image_path"]).resolve():
            raise ValueError("OCR input/review order or path drift")
        if review_row["verdict"] == verdict:
            selected.append({**source_row, **review_row})

    output_dir.mkdir(parents=True, exist_ok=True)
    tile_w, tile_h = 520, 420
    columns, rows_per_sheet = 3, 4
    if per_sheet != columns * rows_per_sheet:
        raise ValueError("per_sheet must remain 12 for deterministic layout")

    sheets: list[dict[str, object]] = []
    title_font, label_font = font(22), font(18)
    for offset in range(0, len(selected), per_sheet):
        batch = selected[offset : offset + per_sheet]
        canvas = Image.new("RGB", (columns * tile_w, rows_per_sheet * tile_h), "white")
        draw = ImageDraw.Draw(canvas)
        sheet_rows: list[dict[str, str]] = []
        for index, item in enumerate(batch):
            x = (index % columns) * tile_w
            y = (index // columns) * tile_h
            image_path = Path(item["image_path"])
            with Image.open(image_path) as original:
                image = ImageOps.contain(original.convert("RGB"), (480, 315))
            image_x = x + (tile_w - image.width) // 2
            image_y = y + 92 + (315 - image.height) // 2
            canvas.paste(image, (image_x, image_y))
            draw.rectangle((x, y, x + tile_w - 1, y + tile_h - 1), outline="#555", width=2)
            draw.text((x + 12, y + 8), f"{item['external_id']} | media {item['media_id']}", fill="black", font=label_font)
            draw.text((x + 12, y + 38), f"Expected: {item['expected_exact']}", fill="#9b2c2c", font=title_font)
            draw.text((x + 12, y + 70), item["manufacturer"][:52], fill="#333", font=label_font)
            sheet_rows.append({
                "external_id": item["external_id"],
                "media_id": item["media_id"],
                "expected_exact": item["expected_exact"],
                "image_path": str(image_path),
            })

        number = len(sheets) + 1
        sheet_path = output_dir / f"wave225-ocr-{verdict.lower()}-{number:02d}.jpg"
        canvas.save(sheet_path, format="JPEG", quality=92, optimize=True)
        sheets.append({"path": str(sheet_path), "rows": sheet_rows})

    summary = {
        "schema_version": 1,
        "ocr_input_rows": len(source),
        "selected_verdict": verdict,
        "selected_rows": len(selected),
        "sheets": sheets,
        "policy": "Contact sheets are review aids only; no media promotion is implied.",
    }
    (output_dir / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verdict", choices=("PASS", "HOLD"), default="PASS")
    args = parser.parse_args()
    result = build(args.input, args.review, args.output_dir, args.verdict)
    print(json.dumps({"selected_rows": result["selected_rows"], "verdict": result["selected_verdict"], "sheets": len(result["sheets"])}))


if __name__ == "__main__":
    main()
