#!/usr/bin/env python3
"""Build the guarded Wave203 OEM identity manifest from all three evidence partitions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PREPARATION = ROOT / "docs/audits/generated/wave203-industrial-unassigned-preparation.csv"
POS_EVIDENCE = ROOT / "docs/audits/generated/wave203-pos-evidence.csv"
CAPTURE_EVIDENCE = ROOT / "docs/audits/generated/wave203-capture-evidence.csv"
REMAINING_EVIDENCE = ROOT / "docs/audits/generated/wave203-remaining-evidence.csv"
POS_REGISTRY = ROOT / "docs/audits/evidence/wave203-pos-official-source-evidence.json"
REMAINING_REGISTRY = ROOT / "docs/audits/evidence/wave203-remaining-official-source-evidence.json"
OUTPUT = ROOT / "docs/imports/rb-verified-oem-identities-wave203-2026-07-29.json"

UPSTREAM_BUILDERS = (
    ROOT / "scripts/build-rb-wave203-pos-evidence.py",
    ROOT / "scripts/build-rb-wave203-capture-evidence.py",
    ROOT / "scripts/build-rb-wave203-remaining-evidence.py",
)

ALLOWED_SOURCE_KINDS = {
    "official_manufacturer_catalogue",
    "official_manufacturer_accessory_catalogue",
    "official_manufacturer_product_page",
    "official_manufacturer_service_document",
}
EXPECTED_PARTITION_SIZES = {"pos": 42, "capture": 74, "remaining": 27}
EXPECTED_UNION_SIZE = 143


@dataclass(frozen=True)
class ProductEvidence:
    partition: str
    external_id: str
    current_name: str
    manufacturer: str
    mpn: str
    product_type: str
    source_url: str
    source_kind: str
    source_publisher: str
    checked_at: str
    snapshot_repo_path: str
    snapshot_sha256: str
    required_exact_tokens: tuple[str, ...]


PRODUCTS = (
    ProductEvidence(
        partition="pos",
        external_id="bitrix:12398",
        current_name="Аккумулятор для VeriFone VX680 (BPK268-001-01-A) 1800mah",
        manufacturer="Verifone",
        mpn="BPK268-001-01-A",
        product_type="Battery pack",
        source_url="https://go.verifone.com/sv/se/webshop",
        source_kind="official_manufacturer_accessory_catalogue",
        source_publisher="Verifone Sweden AB",
        checked_at="2026-07-29",
        snapshot_repo_path="docs/audits/sources/verifone-wave203/verifone-se-webshop-2026-07-29.html",
        snapshot_sha256="de1a95294ce8c1c7bb89218f00de39b124a9b1db2f65d665dd3c0f1b196d0961",
        required_exact_tokens=("BPK268-001-01-A", "VX680", "Batteripack"),
    ),
    ProductEvidence(
        partition="remaining",
        external_id="bitrix:12204",
        current_name="Аккумулятор для Cino F680BT, F780BT (BT2100) 2600mah",
        manufacturer="Cino",
        mpn="BT2100",
        product_type="Li-ion battery pack",
        source_url="https://www.cino.com.tw/cn/products/cordless_cn/F680bt/f680bt_ac.html",
        source_kind="official_manufacturer_accessory_catalogue",
        source_publisher="Cino Group",
        checked_at="2026-07-29",
        snapshot_repo_path="docs/audits/sources/wave203-remaining/cino-f680bt-accessories-2026-07-29.html",
        snapshot_sha256="a94c49b26ad693e2a933a44be41de579aba2045113592f8d1e7ee829c6f3325b",
        required_exact_tokens=("F680BT", "BT2100", "2.6Ah"),
    ),
    ProductEvidence(
        partition="remaining",
        external_id="bitrix:12304",
        current_name="Аккумулятор для Koamtac KDC-100, KDC-200 (KDC-BAT100) 190mah",
        manufacturer="KOAMTAC",
        mpn="KDC-BAT100",
        product_type="Soft-pack battery",
        source_url="https://koamtac.com/wp-content/uploads/KDC_Accessories.pdf",
        source_kind="official_manufacturer_accessory_catalogue",
        source_publisher="KOAMTAC, Inc.",
        checked_at="2026-07-29",
        snapshot_repo_path="docs/audits/sources/wave203-remaining/koamtac-kdc-accessories-2026-07-29.pdf",
        snapshot_sha256="06edd33f7f1e30baf849e6c78a42cf7bf8e0e9a5aa698541df824d0491bb83b1",
        required_exact_tokens=("KDC-BAT100", "KDC100/200", "190mAh"),
    ),
    ProductEvidence(
        partition="remaining",
        external_id="bitrix:12329",
        current_name="Аккумулятор для NCR Orderman 5 (5555-0105-8801) 4200mAh",
        manufacturer="NCR Orderman",
        mpn="5555-0105-8801",
        product_type="Battery pack",
        source_url="https://www.orderman.com/wp-content/uploads/Orderman5.pdf",
        source_kind="official_manufacturer_service_document",
        source_publisher="Orderman GmbH (part of NCR Corporation)",
        checked_at="2026-07-29",
        snapshot_repo_path="docs/audits/sources/wave203-remaining/orderman5-regulatory-guide-2026-07-29.pdf",
        snapshot_sha256="6aa86d554c0171e1c624f88e9c034192c0e9839d40879703010d0686d497c95c",
        required_exact_tokens=("5555-0105-8801", "NCR Orderman5 Battery Pack", "NCR Orderman5"),
    ),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Required evidence artifact is missing: {path.relative_to(ROOT).as_posix()}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized_snapshot_text(path: Path) -> str:
    if path.suffix.casefold() == ".pdf":
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        # Official commerce pages may expose the accessory identity only in
        # their server-rendered JSON payload.  The pinned HTML bytes are the
        # evidence artifact, so search the complete decoded snapshot rather
        # than silently discarding script data.
        text = path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", text).strip()


def validate_snapshot(path: Path, expected_sha256: str, required_tokens: tuple[str, ...]) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise ValueError(f"Pinned snapshot is missing or outside the repository: {path}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or sha256(path) != expected_sha256:
        raise ValueError(f"Pinned snapshot SHA256 mismatch: {path.relative_to(ROOT).as_posix()}")
    text = normalized_snapshot_text(path).casefold()
    missing = [token for token in required_tokens if token.casefold() not in text]
    if missing:
        raise ValueError(
            f"Pinned snapshot {path.relative_to(ROOT).as_posix()} lacks exact tokens: {', '.join(missing)}"
        )


def evidence_external_id(row: dict[str, str]) -> str:
    return row.get("product_external_id") or row.get("external_id") or ""


def validate_union() -> dict[str, dict[str, dict[str, str]]]:
    partitions = {
        "pos": read_csv(POS_EVIDENCE),
        "capture": read_csv(CAPTURE_EVIDENCE),
        "remaining": read_csv(REMAINING_EVIDENCE),
    }
    id_sets = {
        name: {evidence_external_id(row) for row in rows}
        for name, rows in partitions.items()
    }
    if {name: len(ids) for name, ids in id_sets.items()} != EXPECTED_PARTITION_SIZES:
        raise ValueError("Wave203 evidence partition counts drifted from 42/74/27")
    if any(
        id_sets[left] & id_sets[right]
        for index, left in enumerate(id_sets)
        for right in list(id_sets)[index + 1 :]
    ):
        raise ValueError("Wave203 evidence partitions overlap")

    preparation = read_csv(PREPARATION)
    expected_ids = {
        row["product_external_id"]
        for row in preparation
        if row["recommended_wave"] == "wave203" and row["repeat_handling"] == "new"
    }
    union_ids = set().union(*id_sets.values())
    if len(expected_ids) != EXPECTED_UNION_SIZE or union_ids != expected_ids:
        raise ValueError("Wave203 evidence union is not the exact 143-row recommended/new partition")

    by_partition = {
        name: {evidence_external_id(row): row for row in rows}
        for name, rows in partitions.items()
    }
    safe_ids = {
        evidence_external_id(row)
        for rows in partitions.values()
        for row in rows
        if row.get("safe_to_apply") == "true"
    }
    expected_safe = {product.external_id for product in PRODUCTS}
    if safe_ids != expected_safe:
        raise ValueError(f"Wave203 exact-safe set drifted: expected {sorted(expected_safe)}, got {sorted(safe_ids)}")
    return by_partition


def normalized_identity(value: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]+", "", value.casefold())


def validate_product(product: ProductEvidence, evidence: dict[str, str]) -> None:
    expected = {
        "name": product.current_name,
        "partition": "exact_safe",
        "replacement_manufacturer": product.manufacturer,
        "replacement_mpn": product.mpn,
        "repeat_handling": "new_exact_source",
        "safe_to_apply": "true",
    }
    for field, value in expected.items():
        if evidence.get(field) != value:
            raise ValueError(f"{product.external_id}: evidence {field} drifted")

    evidence_url = evidence.get("source_urls") or evidence.get("source_url") or ""
    evidence_snapshot = evidence.get("snapshot_paths") or evidence.get("snapshot_path") or ""
    evidence_snapshot_sha = evidence.get("snapshot_sha256s") or evidence.get("snapshot_sha256") or ""
    if evidence_url != product.source_url or evidence_snapshot != product.snapshot_repo_path:
        raise ValueError(f"{product.external_id}: official URL or snapshot path drifted")
    if evidence_snapshot_sha != product.snapshot_sha256:
        raise ValueError(f"{product.external_id}: evidence snapshot SHA256 drifted")
    if evidence.get("source_publisher") and evidence["source_publisher"] != product.source_publisher:
        raise ValueError(f"{product.external_id}: source publisher drifted")
    if product.source_kind not in ALLOWED_SOURCE_KINDS:
        raise ValueError(f"{product.external_id}: uncontrolled source_kind")
    parsed = urlparse(product.source_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"{product.external_id}: source URL must be HTTPS")
    try:
        checked_at = date.fromisoformat(product.checked_at)
    except ValueError as error:
        raise ValueError(f"{product.external_id}: invalid checked_at") from error
    if checked_at > date.today():
        raise ValueError(f"{product.external_id}: checked_at is in the future")
    normalized_name = normalized_identity(product.current_name)
    if normalized_identity(product.manufacturer) not in normalized_name or normalized_identity(product.mpn) not in normalized_name:
        raise ValueError(f"{product.external_id}: current_name lacks bounded manufacturer/MPN evidence")
    validate_snapshot(ROOT / product.snapshot_repo_path, product.snapshot_sha256, product.required_exact_tokens)


def validate_registries() -> None:
    pos = json.loads(POS_REGISTRY.read_text(encoding="utf-8-sig"))
    pos_sources = {source["id"]: source for source in pos.get("sources", [])}
    verifone = pos_sources.get("verifone-se-vx680-webshop")
    product = next(item for item in PRODUCTS if item.external_id == "bitrix:12398")
    expected_verifone = {
        "publisher": product.source_publisher,
        "source_kind": product.source_kind,
        "url": product.source_url,
        "checked_at": product.checked_at,
        "snapshot_path": product.snapshot_repo_path,
        "snapshot_sha256": product.snapshot_sha256,
        "required_exact_tokens": list(product.required_exact_tokens),
    }
    if not isinstance(verifone, dict) or any(verifone.get(key) != value for key, value in expected_verifone.items()):
        raise ValueError("Verifone POS source registry drifted from the pinned manifest contract")

    remaining = json.loads(REMAINING_REGISTRY.read_text(encoding="utf-8-sig"))
    remaining_by_id = {row["product_external_id"]: row for row in remaining.get("evidence", [])}
    for item in PRODUCTS:
        if item.partition != "remaining":
            continue
        row = remaining_by_id.get(item.external_id)
        expected = {
            "classification": "exact_safe",
            "source_publisher": item.source_publisher,
            "source_url": item.source_url,
            "snapshot_path": item.snapshot_repo_path,
            "snapshot_sha256": item.snapshot_sha256,
            "replacement_manufacturer": item.manufacturer,
            "replacement_mpn": item.mpn,
        }
        if not isinstance(row, dict) or any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(f"{item.external_id}: remaining source registry drifted")


def manifest_row(product: ProductEvidence, output_path: Path) -> dict[str, str]:
    snapshot = ROOT / product.snapshot_repo_path
    relative_snapshot = Path(os.path.relpath(snapshot, output_path.parent)).as_posix()
    if not relative_snapshot.startswith("../audits/sources/"):
        raise ValueError(f"{product.external_id}: snapshot path is not relative to docs/imports")
    return {
        "external_id": product.external_id,
        "current_name": product.current_name,
        "manufacturer": product.manufacturer,
        "mpn": product.mpn,
        "source_url": product.source_url,
        "source_kind": product.source_kind,
        "source_publisher": product.source_publisher,
        "checked_at": product.checked_at,
        "product_type": product.product_type,
        "source_snapshot_path": relative_snapshot,
        "source_snapshot_sha256": product.snapshot_sha256,
    }


def build(output_path: Path, rebuild_upstream: bool = True) -> dict[str, object]:
    if rebuild_upstream:
        for builder in UPSTREAM_BUILDERS:
            subprocess.run([sys.executable, str(builder)], cwd=ROOT, check=True)
    partitions = validate_union()
    validate_registries()
    if len({product.external_id for product in PRODUCTS}) != 4:
        raise ValueError("Combined manifest external IDs are not unique")
    normalized_mpns = [normalized_identity(product.mpn) for product in PRODUCTS]
    if len(set(normalized_mpns)) != 4:
        raise ValueError("Combined manifest normalized MPNs are not unique")
    for product in PRODUCTS:
        evidence = partitions[product.partition].get(product.external_id)
        if evidence is None:
            raise ValueError(f"{product.external_id}: exact evidence row is missing")
        validate_product(product, evidence)

    manifest: dict[str, object] = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "products": [manifest_row(product, output_path) for product in PRODUCTS],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--skip-upstream-build", action="store_true")
    args = parser.parse_args()
    manifest = build(args.output, rebuild_upstream=not args.skip_upstream_build)
    print(json.dumps({"output": args.output.relative_to(ROOT).as_posix(), "products": len(manifest["products"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
