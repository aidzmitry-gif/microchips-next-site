#!/usr/bin/env python3
"""Extract validated raster assets for the non-public Bitrix snapshot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tarfile
from collections import Counter
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError


FORMAT_EXTENSIONS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}


def safe_archive_member(upload_path: str) -> str:
    relative = PurePosixPath(upload_path.lstrip("/"))
    if not relative.parts or relative.parts[0] != "upload" or ".." in relative.parts:
        raise ValueError("unsafe legacy upload path")
    return "_shared/" + relative.as_posix()


def validate_image(content: bytes) -> tuple[str, int, int]:
    if not content or len(content) > 25 * 1024 * 1024:
        raise ValueError("empty or oversized image")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError) as error:
        raise ValueError("invalid raster image") from error
    if image_format not in FORMAT_EXTENSIONS or width < 1 or height < 1:
        raise ValueError("unsupported raster format or dimensions")
    return image_format, width, height


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    records = json.loads(args.manifest.read_text(encoding="utf-8-sig")).get("records", [])
    references = json.loads(args.references.read_text(encoding="utf-8-sig"))
    by_id = {str(row["file_id"]): row for row in references}
    if len(by_id) != len(references):
        raise ValueError("duplicate b_file reference")

    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, str]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.archive, "r:") as archive:
        for record in records:
            legacy_id = str(record.get("legacy_element_id", "")).strip()
            file_id = str(record.get("detail_picture_file_id") or record.get("preview_picture_file_id") or "").strip()
            if not file_id:
                rejected.append({"legacy_element_id": legacy_id, "file_id": "", "reason": "no_media_reference"})
                continue
            try:
                reference = by_id.get(file_id)
                if reference is None or not reference.get("legacy_upload_path"):
                    raise ValueError("b_file reference missing")
                member_name = safe_archive_member(str(reference["legacy_upload_path"]))
                member = archive.getmember(member_name)
                if not member.isfile():
                    raise ValueError("archive member is not a regular file")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("archive member cannot be read")
                content = stream.read()
                image_format, width, height = validate_image(content)
                asset_name = f"bitrix-{legacy_id}-{file_id}{FORMAT_EXTENSIONS[image_format]}"
                (args.output_dir / asset_name).write_bytes(content)
                accepted.append({
                    "legacy_element_id": legacy_id,
                    "legacy_name": str(record.get("legacy_name", "")),
                    "file_id": file_id,
                    "archive_member": member_name,
                    "asset_file": asset_name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "format": image_format,
                    "width": width,
                    "height": height,
                    "rights_basis": "company-owned legacy Bitrix upload backup",
                    "decision": "staging_only_not_identity_verified",
                })
            except (KeyError, OSError, ValueError) as error:
                rejected.append({"legacy_element_id": legacy_id, "file_id": file_id, "reason": str(error)})

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["legacy_element_id", "legacy_name", "file_id", "archive_member", "asset_file",
              "sha256", "format", "width", "height", "rights_basis", "decision"]
    with args.output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(accepted)
    rejected_path = args.output_csv.with_name(args.output_csv.stem + "-rejected.csv")
    with rejected_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["legacy_element_id", "file_id", "reason"])
        writer.writeheader()
        writer.writerows(rejected)
    summary = {
        "manifest_rows": len(records),
        "extracted_assets": len(accepted),
        "rejected_rows": len(rejected),
        "rejection_reasons": dict(sorted(Counter(row["reason"] for row in rejected).items())),
        "canonical_media_imports": 0,
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
