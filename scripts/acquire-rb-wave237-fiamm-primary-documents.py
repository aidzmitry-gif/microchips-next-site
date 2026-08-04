#!/usr/bin/env python3
"""Pin FIAMM-authored primary brochures linked by the official RU distributor.

The host page is distributor-owned, but the downloaded PDFs are manufacturer
publications.  This acquisition step only stores immutable source snapshots;
identity application remains a separate fail-closed operation.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audits/sources/wave237-fiamm-primary"
SUMMARY = ROOT / "docs/audits/generated/rb-wave237-fiamm-primary-acquisition.json"
AUTHORITY_URL = "https://www.fiamm.ru/about/about-company/"
AUTHORITY_PATH = OUT / "fiamm-russia-authorized-distributor.html"

SOURCES = {
    "fg": "https://www.fiamm.ru/upload/uf/37f/d3hnm0fdfsq00v8hlvz1hsi1lunuhd45.pdf",
    "fgh": "https://www.fiamm.ru/upload/uf/0a7/zbf2yf39iceptbd77lbmu8btak6oaxhq.pdf",
    "fgl": "https://www.fiamm.ru/upload/uf/754/4okq6sd39k1z6j1rutvma6ckvp07xlt8.pdf",
    "flb": "https://www.fiamm.ru/upload/uf/23a/nqca7ygtoejpde7fjhzxq6jfwwwqzm3o.pdf",
    "sla": "https://www.fiamm.ru/upload/uf/e1b/g37frazu0hbhurid4a4z4qzq9im2qpdv.pdf",
    "fit": "https://www.fiamm.ru/data/Catalogue/2022/FIT_web.pdf",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    authority_request = urllib.request.Request(
        AUTHORITY_URL,
        headers={"User-Agent": "microchips.by catalog evidence acquisition/1.0"},
    )
    with urllib.request.urlopen(authority_request, timeout=60) as response:
        authority_body = response.read()
    authority_text = authority_body.decode("utf-8", errors="replace")
    required_authority_markers = (
        "официальный авторизованный дистрибьютор",
        "FIAMM Energy Technology S.p.A",
        "странах Таможенного союза и СНГ",
    )
    if not all(marker.casefold() in authority_text.casefold() for marker in required_authority_markers):
        raise SystemExit("FIAMM distributor authority page lacks the pinned authorization markers")
    AUTHORITY_PATH.write_bytes(authority_body)
    rows: list[dict[str, object]] = []
    for series, url in SOURCES.items():
        target = OUT / f"fiamm-{series}-manufacturer-brochure.pdf"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "microchips.by catalog evidence acquisition/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
        if not body.startswith(b"%PDF-"):
            raise SystemExit(f"{series}: response is not a PDF ({content_type!r})")
        if len(body) < 10_000:
            raise SystemExit(f"{series}: suspiciously small PDF ({len(body)} bytes)")
        target.write_bytes(body)
        rows.append(
            {
                "series": series,
                "url": url,
                "path": target.relative_to(ROOT).as_posix(),
                "sha256": digest(target),
                "bytes": len(body),
                "content_type": content_type,
            }
        )
    payload = {
        "schema_version": 1,
        "purpose": "immutable FIAMM manufacturer-document snapshots",
        "host": "official FIAMM Energy Technology distributor in Russia",
        "authority": {
            "url": AUTHORITY_URL,
            "path": AUTHORITY_PATH.relative_to(ROOT).as_posix(),
            "sha256": digest(AUTHORITY_PATH),
            "required_markers": list(required_authority_markers),
        },
        "documents": rows,
        "database_mutations": 0,
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"documents": len(rows), "bytes": sum(int(row["bytes"]) for row in rows)}))


if __name__ == "__main__":
    main()
