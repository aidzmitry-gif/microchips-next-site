#!/usr/bin/env python3
"""Pin the official EnerSys reuse-rights terms page for Wave246A."""
from __future__ import annotations
import hashlib, json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audits/sources/wave246a-enersys"
URL = "https://www.enersys.com/en/webpolicies/website-terms-of-use/"

def main() -> None:
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 Wave246A evidence auditor"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read(); content_type = response.headers.get("Content-Type", "")
    text = body.decode("utf-8", errors="replace")
    required = ["personal, non-commercial use only", "must not reproduce", "images", "must not access or use for any commercial purposes"]
    if not all(needle.casefold() in text.casefold() for needle in required):
        raise SystemExit("EnerSys terms rights clauses not found")
    digest = hashlib.sha256(body).hexdigest(); OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"enersys-website-terms-{digest[:16]}.html"; path.write_bytes(body)
    registry = {"schema_version": 1, "checked_at": "2026-07-30", "source_url": URL, "publisher": "EnerSys", "source_kind": "official_terms_of_use", "local_path": path.relative_to(ROOT).as_posix(), "sha256": digest, "bytes": len(body), "content_type": content_type, "rights_finding": "commercial redistribution/public display of website images is not licensed; prior written permission is required"}
    (OUT / "terms-registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(registry, ensure_ascii=False, indent=2))
if __name__ == "__main__": main()
