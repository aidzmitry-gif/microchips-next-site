#!/usr/bin/env python3
"""Inspect 1C OData price-related entity sets without printing credentials.

Read-only diagnostic. The JSON output contains entity-set names only; it never
contains authentication values or business records.
"""

from __future__ import annotations

import argparse
import base64
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    env = load_env(args.env)
    required = ("ONEC_BASE_URL", "ONEC_USER", "ONEC_PASSWORD")
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise SystemExit(f"Missing environment keys: {', '.join(missing)}")

    base_url = env["ONEC_BASE_URL"].rstrip("/")
    token = base64.b64encode(
        f"{env['ONEC_USER']}:{env['ONEC_PASSWORD']}".encode("utf-8")
    ).decode("ascii")
    request = urllib.request.Request(
        f"{base_url}/$metadata",
        headers={"Authorization": f"Basic {token}", "Accept": "application/xml"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        metadata = response.read()

    root = ET.fromstring(metadata)
    names = sorted(
        {
            node.attrib["Name"]
            for node in root.iter()
            if node.tag.endswith("EntitySet")
            and "Name" in node.attrib
            and any(part in node.attrib["Name"].casefold() for part in ("цен", "валют"))
        }
    )
    payload = {
        "schema_version": 1,
        "base_host": urllib.parse.urlparse(base_url).hostname,
        "matching_entity_sets": names,
        "count": len(names),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Price metadata entity sets: {len(names)}; output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
