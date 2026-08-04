#!/usr/bin/env python3
"""Build deterministic OCR chunks from the read-only legacy-preview exporter."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
EXPORT = GEN / "rb-wave227-legacy-preview-candidates.csv"
REVIEWED = (
    ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave225-2026-07-29.json",
    ROOT / "docs/imports/rb-reviewed-legacy-preview-media-wave226-2026-07-29.json",
)
ASSETS = ROOT / ".tmp/wave227-assets"
OUT_DIR = GEN / "wave227-ocr-batches"
EXPORT_FIELDS = {"external_id", "media_id", "storage_path", "content_sha256", "rights_basis", "identity_scope", "mpn", "model_core", "manufacturer"}
OCR_FIELDS = ["external_id", "media_id", "image_path", "expected_mpn", "expected_model_core", "manufacturer", "hash"]
LEDGER_FIELDS = ["external_id", "media_id", "identity_scope", "expected_exact", "content_sha256", "status", "reason"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def display_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def reviewed_media(paths: tuple[Path, ...]) -> tuple[set[tuple[str, str]], set[str], set[str]]:
    keys, ids, hashes = set(), set(), set()
    for path in paths:
        for image in json.loads(path.read_text(encoding="utf-8"))["images"]:
            key = (image["external_id"], str(image["media_id"]))
            if key in keys:
                raise SystemExit(f"reviewed media repeats external/media key: {path.name}:{key}")
            keys.add(key); ids.add(str(image["media_id"])); hashes.add(image["content_sha256"].lower())
    return keys, ids, hashes


def safe_asset_path(root: Path, storage_path: str) -> Path | None:
    relative = Path(storage_path.replace("\\", "/"))
    if not storage_path or relative.is_absolute() or ".." in relative.parts:
        return None
    path = (root / relative).resolve()
    return path if root in path.parents else None


def exact_expectation(row: dict[str, str]) -> tuple[str, str, str]:
    scope, mpn, core = row["identity_scope"].strip(), row["mpn"].strip(), row["model_core"].strip()
    if scope == "exact" and mpn and not core:
        return mpn, "", ""
    if scope == "model_core" and core and not mpn and row["manufacturer"].strip():
        return "", core, ""
    return "", "", "invalid_exported_identity_scope_or_fields"


def build(export_path: Path, reviewed_paths: tuple[Path, ...], assets_root: Path, output_dir: Path, chunk_size: int) -> dict:
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    fields, exported = read_csv(export_path)
    if set(fields) != EXPORT_FIELDS or len(fields) != len(EXPORT_FIELDS):
        raise SystemExit("legacy-preview exporter field contract drift")
    if not exported:
        raise SystemExit("legacy-preview exporter is empty")
    keys = {(row["external_id"], row["media_id"]) for row in exported}
    if len(keys) != len(exported) or any(not ext or not media.isdigit() for ext, media in keys):
        raise SystemExit("legacy-preview exporter has duplicate or invalid external/media identity")
    reviewed_keys, reviewed_ids, reviewed_hashes = reviewed_media(reviewed_paths)
    # A content hash is a binary asset identity. It cannot prove two products,
    # even if their exported exact MPN happens to agree. Hold every row in an
    # ambiguous current-batch hash group before attempting OCR.
    hash_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in exported:
        digest = row["content_sha256"].lower()
        expected_mpn, expected_model_core, reason = exact_expectation(row)
        if not reason and len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
            hash_groups[digest].append({**row, "_expected": expected_mpn or expected_model_core})
    ambiguous_hashes = {
        digest for digest, rows in hash_groups.items()
        if len({row["external_id"] for row in rows}) > 1
        or len({(row["identity_scope"], row["_expected"]) for row in rows}) > 1
    }
    assets_root = assets_root.resolve()
    ledger, selected = [], []
    for row in exported:
        external_id, media_id, digest = row["external_id"], row["media_id"], row["content_sha256"].lower()
        expected_mpn, expected_model_core, reason = exact_expectation(row)
        expected = expected_mpn or expected_model_core
        base = {"external_id": external_id, "media_id": media_id, "identity_scope": row["identity_scope"], "expected_exact": expected, "content_sha256": digest, "status": "", "reason": ""}
        if (external_id, media_id) in reviewed_keys or media_id in reviewed_ids or digest in reviewed_hashes:
            ledger.append({**base, "status": "excluded", "reason": "already_reviewed_in_wave225_or_wave226"})
            continue
        if digest in ambiguous_hashes:
            ledger.append({**base, "status": "hold", "reason": "shared_asset_hash_across_products"})
            continue
        if reason:
            ledger.append({**base, "status": "hold", "reason": reason})
            continue
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            ledger.append({**base, "status": "hold", "reason": "invalid_exported_content_sha256"})
            continue
        asset = safe_asset_path(assets_root, row["storage_path"])
        if asset is None:
            ledger.append({**base, "status": "hold", "reason": "unsafe_exported_storage_path"})
            continue
        if not asset.is_file():
            ledger.append({**base, "status": "hold", "reason": "materialized_asset_missing"})
            continue
        if sha256(asset) != digest:
            ledger.append({**base, "status": "hold", "reason": "materialized_asset_sha256_mismatch"})
            continue
        selected.append({"external_id": external_id, "media_id": media_id, "image_path": str(asset), "expected_mpn": expected_mpn, "expected_model_core": expected_model_core, "manufacturer": row["manufacturer"].strip(), "hash": digest})
        ledger.append({**base, "status": "selected", "reason": "exported_pinned_identity_and_materialized_hash_match"})
    selected.sort(key=lambda row: (row["external_id"], int(row["media_id"])))
    ledger.sort(key=lambda row: (row["external_id"], int(row["media_id"])))
    output_dir.mkdir(parents=True, exist_ok=True)
    batches = []
    for offset in range(0, len(selected), chunk_size):
        batch_rows = selected[offset:offset + chunk_size]
        number = len(batches) + 1
        input_path = output_dir / f"wave227-ocr-input-{number:03d}.csv"
        write_csv(input_path, OCR_FIELDS, batch_rows)
        batches.append({"batch": number, "input": display_path(input_path), "review": display_path(output_dir / f"wave227-ocr-review-{number:03d}.csv"), "rows": len(batch_rows), "sha256": sha256(input_path)})
    ledger_path = output_dir / "wave227-ocr-batch-ledger.csv"
    write_csv(ledger_path, LEDGER_FIELDS, ledger)
    result = {
        "schema_version": 1, "batch": "wave227_legacy_preview_ocr_batches",
        "export": {"path": display_path(export_path), "sha256": sha256(export_path), "rows": len(exported), "fields": fields},
        "reviewed_media": {"manifests": [display_path(path) for path in reviewed_paths], "unique_media_keys": len(reviewed_keys)},
        "chunk_size": chunk_size, "selected_rows": len(selected), "shared_asset_hash_holds": sum(row["reason"] == "shared_asset_hash_across_products" for row in ledger), "batches": batches,
        "ledger": {"path": display_path(ledger_path), "sha256": sha256(ledger_path), "rows": len(ledger), "counts": dict(sorted(Counter(row["status"] for row in ledger).items()))},
        "policy": {"ocr_executed": False, "database_apply": False, "media_promotion": False, "auto_pass": False, "publication_changes": 0},
    }
    (output_dir / "index.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", type=Path, default=EXPORT)
    parser.add_argument("--assets-root", type=Path, default=ASSETS)
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--chunk-size", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(build(args.export, REVIEWED, args.assets_root, args.output_dir, args.chunk_size), ensure_ascii=False))


if __name__ == "__main__":
    main()
