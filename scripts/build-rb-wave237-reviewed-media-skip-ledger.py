#!/usr/bin/env python3
"""Merge every completed media-review ledger into one pinned skip ledger."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/generated/rb-wave237-reviewed-media-skip-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave237-reviewed-media-skip-ledger.summary.json"
PINS = {
    ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave225.csv": "f1c3265378f5c84a0d1607f23e46fc87f09b5dd847f86ba4c766c59d946651d5",
    ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave226.csv": "395352f5f5e176dd850d195ecbddff2dacfb4e45bdcc965a21f2350ca842ca4c",
    ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave227.csv": "e241ccba4d451a9aa5dacc0a8cbaa6015c6014e9a5844fed43dc40a642d7894f",
    ROOT / "docs/audits/generated/rb-reviewed-legacy-preview-media-wave229c.csv": "a3080a9544f46b62015c0e6d33312bcf78ed2cb10437870f7b0d980be0b52007",
    ROOT / "docs/audits/generated/rb-wave229a-reviewed-media.csv": "1593f5046718ee69e4ca0912142045da00874bac3a0217bfabd82c22bba84047",
    ROOT / "docs/audits/generated/rb-wave229b-hold-002-visual-review.csv": "6f6a0df844ecf895c80ee7b0a007c3ebb12695c65d3c0d4405d0ae558cc10d08",
    ROOT / "docs/audits/generated/rb-wave232d-apc-visual-review.csv": "1e0b5318fc16e8d24980cea112c5529364b2a2f55a1e4474c10c8e9583a4ab65",
    ROOT / "docs/audits/generated/rb-wave232e-enersys-cyclon-media-review.csv": "52d9549a74d1e547992db806fa06d9fec37bd249aca7ab2d06cbc6289dee08b5",
    ROOT / "docs/audits/generated/rb-wave232f-ippon-enersys-media-review.csv": "94907dbf8276aed980e137a375fbba6393b6432a7f95a86274c436cfaab345c2",
    ROOT / "docs/audits/generated/rb-wave233d-delta-media-review.csv": "68069d4e7523a3b20e9513d6d5f78b8b9471cc585e37ffc0a6064bcc574e388f",
    ROOT / "docs/audits/generated/rb-wave234-prior-reviewed-wave233.csv": "79c5a212f1e3627f81176a0f4619e845834a02b9130d344e33d82fcc1be9dfb2",
    ROOT / "docs/audits/generated/rb-wave234f-general-security-media-review.csv": "93c6a7f14a57c0688b6ee9766abe75cfa3cf280adebe671f96ff808b31a49d2c",
    ROOT / "docs/audits/generated/rb-wave235-reviewed-media.csv": "611b166bb32aecfca6f507fa40cd6ab0d1a7503aa2552108a712950eb782823d",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    reviewed: dict[tuple[str, int], set[str]] = {}
    raw_rows = 0
    for path, digest in PINS.items():
        if not path.is_file() or sha256(path) != digest:
            raise SystemExit(f"Pinned reviewed-media ledger drift: {path.relative_to(ROOT)}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not {"external_id", "media_id"} <= set(reader.fieldnames):
                raise SystemExit(f"Reviewed-media ledger schema drift: {path.relative_to(ROOT)}")
            for row in reader:
                raw_rows += 1
                external_id, media_id = row["external_id"].strip(), row["media_id"].strip()
                if not external_id or not media_id.isdigit() or int(media_id) < 1:
                    raise SystemExit(f"Invalid reviewed media key: {path.relative_to(ROOT)}")
                reviewed.setdefault((external_id, int(media_id)), set()).add(path.name)

    rows = [
        {"external_id": external_id, "media_id": str(media_id), "review_ledgers": "|".join(sorted(sources))}
        for (external_id, media_id), sources in sorted(reviewed.items())
    ]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["external_id", "media_id", "review_ledgers"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "schema_version": 1,
        "wave": "wave237_reviewed_media_skip_ledger",
        "checked_at": "2026-07-29",
        "source_ledgers": len(PINS),
        "raw_review_rows": raw_rows,
        "unique_reviewed_media": len(rows),
        "inputs": {path.relative_to(ROOT).as_posix(): digest for path, digest in PINS.items()},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(rows)},
        "database_operations": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_ledgers": len(PINS), "raw_rows": raw_rows, "unique_rows": len(rows)}))


if __name__ == "__main__":
    main()
