#!/usr/bin/env python3
"""Extract a fail-closed visual-review bundle from the company Bitrix archive.

Reviewed Bitrix↔1C links are not sufficient on their own: historical matching
can map several same-capacity products to one 1C row.  This tool therefore
requires the source-backed MPN/model core to occur literally in the legacy
product name before it reads an archive member.  Its output is still only a
review queue, never an import approval.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tarfile
import unicodedata
from pathlib import Path


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", "", value)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_identity(manifests_dir: Path, row: dict[str, str]) -> tuple[str, str]:
    direct_identity = row.get("identity", "").strip()
    direct_scope = row.get("identity_scope", "").strip()
    if direct_identity and direct_scope in {"exact", "model_core"}:
        return direct_identity, direct_scope
    manifest_path = manifests_dir / row["source_manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    matches = [item for item in manifest.get("products", [])
               if isinstance(item, dict) and str(item.get("external_id", "")).strip() == row["external_id"].strip()]
    if len(matches) != 1:
        raise ValueError(f"{row['external_id']}: source manifest must contain exactly one row")
    item = matches[0]
    identity = str(item.get("mpn") or item.get("model_core") or "").strip()
    scope = str(item.get("identity_scope") or "").strip()
    if not identity or scope not in {"exact", "model_core"}:
        raise ValueError(f"{row['external_id']}: source identity is not exact/model_core")
    return identity, scope


def asset_name(external_id: str, source_name: str) -> str:
    prefix = external_id.casefold().replace("ка", "ka").replace("фр", "fr")
    prefix = re.sub(r"[^a-z0-9]+", "-", prefix).strip("-")
    suffix = Path(source_name).suffix.casefold()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError(f"{external_id}: unsupported image extension {suffix!r}")
    return f"{prefix}-detail{suffix}"


def build(candidates_path: Path, references_path: Path, archive_path: Path,
          manifests_dir: Path, output_dir: Path, output_csv: Path) -> dict[str, int]:
    candidates = read_csv(candidates_path)
    references = json.loads(references_path.read_text(encoding="utf-8"))
    by_file = {str(row["file_id"]): row for row in references}
    if len(by_file) != len(references):
        raise ValueError("b_file references must be unique")

    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    seen: set[str] = set()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:") as archive:
        for row in candidates:
            external_id = row.get("external_id", "").strip()
            if not external_id or external_id in seen:
                raise ValueError("candidate external IDs must be unique and non-empty")
            seen.add(external_id)
            try:
                identity, scope = source_identity(manifests_dir, row)
                identity_key = compact(identity)
                legacy_key = compact(row.get("legacy_name", ""))
                if len(identity_key) < 4 or identity_key not in legacy_key:
                    raise ValueError("source identity is not literal in legacy product name")
                file_id = row.get("detail_picture_file_id", "").strip()
                reference = by_file.get(file_id)
                if reference is None or not reference.get("legacy_upload_path"):
                    raise ValueError("detail b_file reference is missing")
                archive_member = "_shared/" + str(reference["legacy_upload_path"]).lstrip("/")
                member = archive.getmember(archive_member)
                if not member.isfile():
                    raise ValueError("archive member is not a regular file")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("archive member could not be read")
                content = stream.read()
                if not content:
                    raise ValueError("archive member is empty")
                name = asset_name(external_id, str(reference.get("file_name") or archive_member))
                target = output_dir / name
                target.write_bytes(content)
                accepted.append({
                    "external_id": external_id,
                    "manufacturer": row.get("manufacturer", ""),
                    "identity": identity,
                    "identity_scope": scope,
                    "legacy_element_id": row.get("legacy_element_id", ""),
                    "legacy_name": row.get("legacy_name", ""),
                    "detail_picture_file_id": file_id,
                    "archive_member": archive_member,
                    "asset_file": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "rights_basis": "company-owned legacy Bitrix upload backup",
                    "decision": "requires_visible_exact_model_and_rating_check",
                })
            except (KeyError, OSError, ValueError) as error:
                rejected.append({
                    "external_id": external_id,
                    "legacy_element_id": row.get("legacy_element_id", ""),
                    "legacy_name": row.get("legacy_name", ""),
                    "reason": str(error),
                })

    fields = ["external_id", "manufacturer", "identity", "identity_scope", "legacy_element_id",
              "legacy_name", "detail_picture_file_id", "archive_member", "asset_file", "sha256",
              "rights_basis", "decision"]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(accepted)
    rejected_path = output_csv.with_name(output_csv.stem + "-rejected.csv")
    with rejected_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["external_id", "legacy_element_id", "legacy_name", "reason"])
        writer.writeheader()
        writer.writerows(rejected)
    summary = {
        "input_candidates": len(candidates),
        "extracted_for_visual_review": len(accepted),
        "rejected_before_extraction": len(rejected),
        "automatic_imports": 0,
    }
    output_csv.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifests-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.candidates, args.references, args.archive, args.manifests_dir,
                           args.output_dir, args.output_csv), ensure_ascii=False))


if __name__ == "__main__":
    main()
