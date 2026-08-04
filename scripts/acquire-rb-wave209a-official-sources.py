#!/usr/bin/env python3
"""Download the bounded first-party source set for Wave209-A."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


SOURCES = {
    "enersys-cyclon-selection-guide.pdf": "https://www.enersys.com/493c0d/globalassets/documents/product-documentation/cyclon/emea/en-cyc-sg-004_0614.pdf",
    "enersys-cyclon-us-selection-guide.pdf": "https://www.enersys.com/493c0d/globalassets/documents/product-documentation/cyclon/amer/us-cyc-sg-003_0608.pdf",
    "enersys-powersafe-v-range.pdf": "https://www.enersys.com/493bb4/globalassets/documents/product-documentation/powersafe/v-tt/emea/en-v-rs-013.pdf",
    "exide-sonnenschein-a400.pdf": "https://www.exidegroup.com/eu/sites/default/files/2017-01/Sonnenschein_A400_en.pdf",
    "exide-sonnenschein-a500.pdf": "https://www.exidegroup.com/eu/sites/default/files/2017-01/Sonnenschein_A500_en.pdf",
    "exide-sonnenschein-a600.pdf": "https://www.exidegroup.com/eu/sites/default/files/2017-01/Sonnenschein_A600_en.pdf",
    "exide-sonnenschein-a600-solar.pdf": "https://www.exidegroup.com/at/sites/default/files/2023-04/230404_Sonnenschein_Solar_A600_technicaldata.pdf",
    "exide-sonnenschein-a700.pdf": "https://www.exidegroup.com/eu/sites/default/files/2017-01/Sonnenschein_A700_en.pdf",
    "exide-sonnenschein-solar-block.pdf": "https://www.exidegroup.com/sites/default/files/2017-01/Sonnenschein_SOLAR_en.pdf",
}
ALLOWED_HOSTS = {"www.enersys.com", "www.exidegroup.com"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    registry = []
    for filename, url in SOURCES.items():
        if urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise SystemExit(f"non-official host: {url}")
        request = urllib.request.Request(url, headers={"User-Agent": "microchips.by-source-audit/1.0"})
        with urllib.request.urlopen(request, timeout=45) as response:
            data = response.read()
            content_type = response.headers.get_content_type()
            final_url = response.geturl()
        if not data.startswith(b"%PDF-"):
            raise SystemExit(f"not a PDF: {url} ({content_type}, {len(data)} bytes)")
        path = args.output_dir / filename
        path.write_bytes(data)
        registry.append({
            "filename": filename,
            "source_url": url,
            "final_url": final_url,
            "publisher": "EnerSys" if "enersys" in filename else "Exide Technologies",
            "content_type": content_type,
            "bytes": len(data),
            "sha256": sha256(data),
            "snapshot_path": str(path.relative_to(args.registry.parents[2])).replace("\\", "/"),
        })
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    args.registry.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_records": len(registry), "registry": str(args.registry)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
