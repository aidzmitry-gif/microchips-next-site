#!/usr/bin/env python3
"""Pin first-party Motorola and Kenwood accessory catalogues for Wave207."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/audits/sources/wave207-motorola-kenwood"
INDEX = OUTPUT / "snapshot-index.json"

SOURCES = (
    {
        "source_id": "kenwood_ksc35s_service_manual",
        "publisher": "JVCKENWOOD Corporation",
        "source_url": "https://kasc.kenwood.com/files/prod/2150/5/KSC-35SE_EU_B51-8947-00.pdf",
        "snapshot_name": "kenwood-ksc35s-service-manual.pdf",
    },
    {
        "source_id": "kenwood_portable_radio_accessories_2015",
        "publisher": "JVCKENWOOD Corporation",
        "source_url": "https://comms.kenwood.com/en/common/pdf/products/accessories.pdf",
        "snapshot_name": "kenwood-portable-radio-accessories.pdf",
    },
    {
        "source_id": "motorola_mototrbo_energy_buyers_guide",
        "publisher": "Motorola Solutions",
        "source_url": "https://www.motorolasolutions.com/content/dam/msi/docs/EA_Collaterals/ENGLISH/Accessories/MOTOTRBO_Energy_Buyers_Guide_ENG.pdf",
        "snapshot_name": "motorola-mototrbo-energy-buyers-guide.pdf",
    },
    {
        "source_id": "motorola_commercial_radio_accessory_catalog",
        "publisher": "Motorola Solutions",
        "source_url": "https://www.motorolasolutions.com/content/dam/msi/Products/two-way-radios/MOTOTRBO_Commercial_Tier_Accessory_Catalog.pdf",
        "snapshot_name": "motorola-commercial-radio-accessory-catalog.pdf",
    },
    {
        "source_id": "motorola_low_tier_accessory_catalog",
        "publisher": "Motorola Solutions",
        "source_url": "https://www.motorolasolutions.com/content/dam/msi/docs/business/products/two-way_radios/portable_radios/_documents/static_files/low_tier_accessory_catalog_commercial.pdf",
        "snapshot_name": "motorola-low-tier-accessory-catalog.pdf",
    },
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(url: str, output: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "microchips.by evidence archiver/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read()
    if not payload.startswith(b"%PDF"):
        raise SystemExit(f"Expected PDF from {url}")
    output.write_bytes(payload)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    failures = []
    for source in SOURCES:
        snapshot = OUTPUT / source["snapshot_name"]
        if not snapshot.exists():
            try:
                download(source["source_url"], snapshot)
            except (HTTPError, URLError, TimeoutError) as error:
                failures.append({
                    "source_id": source["source_id"],
                    "source_url": source["source_url"],
                    "error_type": type(error).__name__,
                    "reason": str(error),
                })
                continue
        text_path = snapshot.with_suffix(".txt")
        text = "\n".join(page.extract_text() or "" for page in PdfReader(snapshot).pages)
        text_path.write_text(text, encoding="utf-8")
        records.append({
            "source_id": source["source_id"],
            "publisher": source["publisher"],
            "source_url": source["source_url"],
            "source_kind": "official_manufacturer_accessory_catalogue",
            "snapshot_path": snapshot.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha256(snapshot),
            "extracted_text_path": text_path.relative_to(ROOT).as_posix(),
            "extracted_text_sha256": sha256(text_path),
        })
    INDEX.write_text(json.dumps({
        "schema_version": 1,
        "checked_at": "2026-07-29",
        "sources": records,
        "acquisition_failures": failures,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sources": len(records), "failures": len(failures), "index": INDEX.relative_to(ROOT).as_posix()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
