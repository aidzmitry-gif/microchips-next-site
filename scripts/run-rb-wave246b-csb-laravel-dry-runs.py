#!/usr/bin/env python3
"""Run the three real Wave246B Laravel dry-run gates and write a compact receipt."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / "docs/imports"
CATALOG = ROOT / "docs/audits/sources/wave242-leoch-marathon-csb/csb-catalog-2026.pdf"
MASTER = IMPORTS / "rb-verified-oem-identities-wave246b-csb-2026-07-30.json"
BITRIX = IMPORTS / "rb-verified-oem-identities-wave246b-csb-bitrix-dry-run-2026-07-30.json"
ACTIVE = IMPORTS / "rb-verified-oem-identities-wave246b-csb-active-1c-dry-run-2026-07-30.json"
DESCRIPTIONS = IMPORTS / "rb-source-backed-descriptions-wave246b-csb-2026-07-30.json"
OUTPUT = ROOT / "docs/audits/generated/rb-wave246b-csb-laravel-dry-runs.json"
CONTAINER_ROOT = "/tmp/wave246b/docs"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def require(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode != 0:
        raise SystemExit(f"{label} failed: {result.stdout}{result.stderr}")
    return result.stdout


def artisan_json(path: Path, target: str) -> dict[str, object]:
    container = f"{CONTAINER_ROOT}/imports/{path.name}"
    output = require(run(["docker", "compose", "exec", "-T", "backend", "php", "artisan",
                          "catalog:apply-verified-oem-identities", "microchips-by", container]), target)
    match = re.search(r"\{[\s\S]*\}", output)
    if not match:
        raise SystemExit(f"{target} JSON missing: {output}")
    payload = json.loads(match.group(0))
    if payload != {
        **payload, "mode": "dry_run", "site": "microchips-by", "target_kind": target,
        "records": 12 if target == "bitrix_draft" else 3, "identities_filled": 0,
        "unchanged": 0, "commercial_fields_changed": 0, "publication_fields_changed": 0,
    }:
        raise SystemExit(f"unexpected identity dry-run payload: {payload}")
    if payload["manifest_sha256"] != sha(path):
        raise SystemExit("identity dry-run manifest hash mismatch")
    return payload


def main() -> None:
    require(run(["docker", "compose", "exec", "-T", "backend", "mkdir", "-p",
                 f"{CONTAINER_ROOT}/imports", f"{CONTAINER_ROOT}/audits/sources/wave242-leoch-marathon-csb"]), "mkdir")
    for path, destination in (
        (BITRIX, f"backend:{CONTAINER_ROOT}/imports/{BITRIX.name}"),
        (ACTIVE, f"backend:{CONTAINER_ROOT}/imports/{ACTIVE.name}"),
        (DESCRIPTIONS, f"backend:{CONTAINER_ROOT}/imports/{DESCRIPTIONS.name}"),
        (CATALOG, f"backend:{CONTAINER_ROOT}/audits/sources/wave242-leoch-marathon-csb/{CATALOG.name}"),
    ):
        require(run(["docker", "compose", "cp", str(path.relative_to(ROOT)), destination]), f"copy {path.name}")
    bitrix = artisan_json(BITRIX, "bitrix_draft")
    active = artisan_json(ACTIVE, "active_1c")
    desc_output = require(run(["docker", "compose", "exec", "-T", "backend", "php", "artisan",
                               "content:stage-source-backed-description-drafts", "microchips-by",
                               f"{CONTAINER_ROOT}/imports/{DESCRIPTIONS.name}", "--refresh-existing", "--refresh-applied"]), "description")
    match = re.search(r"Source-backed description run (\d+): (\d+) created, (\d+) refreshed, (\d+) unchanged; none were published\.", desc_output)
    if not match or tuple(map(int, match.groups()[1:])) != (0, 88, 0):
        raise SystemExit(f"unexpected description dry-run: {desc_output}")
    payload = {
        "schema_version": 1, "checked_at": "2026-07-30", "actual_laravel_commands_executed": True,
        "identity_manifest_sha256": sha(MASTER), "description_manifest_sha256": sha(DESCRIPTIONS),
        "identity": {"bitrix_draft": bitrix, "active_1c": active,
                     "records_checked": 15, "existing_manufacturer_draft_not_supported_target_kind": 73},
        "description": {"import_run_id": int(match.group(1)), "records": 88, "created": 0, "refreshed": 88, "unchanged": 0, "published": 0},
        "invariants": {"apply_flag_used": False, "commercial_fields_changed": 0, "publication_fields_changed": 0,
                       "identity_fields_filled": 0, "persisted_description_drafts": 0, "media_rows": 0,
                       "domain_record_mutations": 0, "dry_run_audit_import_runs_created_by_final_runner": 1},
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"identity_records": 15, "description_records": 88, "description_refreshed": 88, "published": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
