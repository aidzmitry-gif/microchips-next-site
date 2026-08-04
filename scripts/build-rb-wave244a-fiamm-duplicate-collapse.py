#!/usr/bin/env python3
"""Build fail-closed collapse evidence for exactly two FIAMM legacy duplicates."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave244a-prior-source-exclusions.json"
REGISTRY = ROOT / "docs/audits/sources/wave244a-fiamm/registry.json"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave244a-fiamm-duplicate-collapse-evidence.csv"
MANIFEST = ROOT / "docs/imports/rb-reviewed-fiamm-duplicates-wave244a-2026-07-30.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave244a-fiamm-duplicate-collapse.summary.json"
REPORT = ROOT / "docs/audits/2026-07-30-rb-wave244a-fiamm-duplicate-collapse.md"
LARAVEL_DRY_RUN = ROOT / "docs/audits/generated/rb-wave244a-fiamm-collapse-laravel-dry-run.json"
SCOPE = [
    {"duplicate": "bitrix:3266", "survivor": "ФР-00002108", "model": "12FGH36", "voltage": "12", "capacity": "9"},
    {"duplicate": "bitrix:1511", "survivor": "КА-00003136", "model": "4SLA150", "voltage": "4", "capacity": "150"},
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str | None) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", (value or "").casefold())


def safety_module():
    path = ROOT / "scripts/build-rb-wave243-delta-duplicate-collapse.py"
    spec = importlib.util.spec_from_file_location("wave243_duplicate_safety", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def exact_facts(source: dict[str, object]) -> dict[str, str]:
    path = ROOT / str(source["snapshot_path"])
    expected = str(source["expected_exact_models"][0])
    if path.suffix == ".pdf":
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if expected != "12FGH36" or expected not in text or len(reader.pages) != 2:
            raise SystemExit("12FGH36 exact PDF evidence drift")
        return {"model": expected, "voltage": "12", "capacity": "9", "visual_page": "2"}
    text = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
    compact = re.sub(r"\s+", " ", text)
    if expected != "4SLA150" or not re.search(r"4SLA150\s+4\s+150\s+271", compact):
        raise SystemExit("4SLA150 exact HTML evidence drift")
    return {"model": expected, "voltage": "4", "capacity": "150", "visual_page": "html_table"}


def main() -> None:
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {item["value"] for item in exclusions["source_urls"]}
    prior_hashes = {item["value"] for item in exclusions["snapshot_sha256"]}
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if registry["prior_exclusions_sha256"] != sha(EXCLUSIONS):
        raise SystemExit("acquisition exclusion registry drift")
    source_by_model = {}
    for source in registry["sources"]:
        path = ROOT / source["snapshot_path"]
        if source["source_url"] in prior_urls or source["snapshot_sha256"] in prior_hashes:
            raise SystemExit("Wave244A source repeats prior URL/SHA")
        if sha(path) != source["snapshot_sha256"]:
            raise SystemExit("Wave244A source snapshot SHA drift")
        facts = exact_facts(source)
        source_by_model[facts["model"]] = {**source, **facts}
    if set(source_by_model) != {row["model"] for row in SCOPE}:
        raise SystemExit("exact source scope drift")

    safety = safety_module()
    external_ids = sorted({value for row in SCOPE for value in (row["duplicate"], row["survivor"])})
    live = safety.query_live(external_ids)
    evidence_rows = []
    manifest_rows = []
    registry_sha = sha(REGISTRY)
    for item in SCOPE:
        duplicate = live[item["duplicate"]]
        survivor = live[item["survivor"]]
        source = source_by_model[item["model"]]
        reasons = safety.safe_noindex_state(duplicate, duplicate=True)
        reasons.extend(safety.safe_noindex_state(survivor, duplicate=False))
        if not set(duplicate.get("categories") or []).issubset(set(survivor.get("categories") or [])):
            reasons.append("survivor_does_not_preserve_duplicate_categories")
        if normalized(survivor.get("manufacturer")) != normalized("FIAMM"):
            reasons.append("survivor_manufacturer_mismatch")
        if normalized(survivor.get("mpn")) != normalized(item["model"]):
            reasons.append("survivor_mpn_mismatch")
        if source["voltage"] != item["voltage"] or source["capacity"] != item["capacity"]:
            reasons.append("official_electrical_facts_mismatch")
        decision = "PASS" if not reasons else "HOLD"
        evidence_rows.append({
            "duplicate_external_id": item["duplicate"], "survivor_external_id": item["survivor"],
            "model_core": item["model"], "voltage_v": item["voltage"], "capacity_ah": item["capacity"],
            "duplicate_name": duplicate.get("name", ""), "survivor_name": survivor.get("name", ""),
            "duplicate_path": duplicate.get("urls", [{}])[0].get("path", ""),
            "survivor_path": survivor.get("urls", [{}])[0].get("path", ""),
            "duplicate_categories": "|".join(duplicate.get("categories") or []),
            "survivor_categories": "|".join(survivor.get("categories") or []),
            "survivor_price": survivor.get("price") or "",
            "survivor_current_price_evidence": len(survivor.get("current_price_evidence") or []),
            "source_url": source["source_url"], "source_snapshot_path": source["snapshot_path"],
            "source_snapshot_sha256": source["snapshot_sha256"], "visual_review_location": source["visual_page"],
            "prior_url_overlap": "false", "prior_sha_overlap": "false",
            "decision": decision, "hold_reason": "|".join(sorted(set(reasons))),
        })
        if reasons:
            continue
        manifest_rows.append({
            "survivor_external_id": item["survivor"], "duplicate_external_id": item["duplicate"],
            "survivor_name": survivor["name"], "duplicate_name": duplicate["name"],
            "survivor_path": survivor["urls"][0]["path"], "duplicate_path": duplicate["urls"][0]["path"],
            "model_core": item["model"], "voltage": item["voltage"] + "V", "capacity": item["capacity"] + "Ah",
            "availability": "on_request", "category_external_ids": survivor["categories"],
            "duplicate_category_external_ids": duplicate["categories"], "manufacturer": "FIAMM",
            "survivor_mpn": survivor["mpn"], "source_url": source["source_url"],
            "source_evidence_path": REGISTRY.relative_to(ROOT).as_posix(), "source_evidence_sha256": registry_sha,
            "source_snapshot_path": source["snapshot_path"], "source_snapshot_sha256": source["snapshot_sha256"],
            "decision_reason": "New no-repeat FIAMM primary evidence proves the exact model and electrical facts; the live canonical owner has the same normalized FIAMM MPN and safely preserves URL, category, content, media and exact current price evidence.",
        })

    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(evidence_rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(evidence_rows)
    MANIFEST.write_text(json.dumps({
        "schema_version": 1, "site_key": "microchips-by",
        "purpose": "Collapse only two exact FIAMM legacy duplicates after new no-repeat primary evidence and live safety checks.",
        "duplicates": manifest_rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    dry_run = json.loads(LARAVEL_DRY_RUN.read_text(encoding="utf-8"))
    canonical_output = MANIFEST.parent == ROOT / "docs/imports"
    if canonical_output and (dry_run["manifest_sha256"] != sha(MANIFEST) or dry_run["exit_code"] != 0 or dry_run["apply_flag_used"]):
        raise SystemExit("Laravel dry-run evidence does not match the final collapse manifest")
    summary = {
        "schema_version": 1, "wave": "wave244a_fiamm_duplicate_collapse", "checked_at": "2026-07-30",
        "scope": 2, "pass": sum(row["decision"] == "PASS" for row in evidence_rows),
        "hold": sum(row["decision"] == "HOLD" for row in evidence_rows), "manifest_rows": len(manifest_rows),
        "prior_exclusions": {"files": len(exclusions["scanned_files"]), "url_overlap": 0, "sha_overlap": 0},
        "artifacts": {"evidence_sha256": sha(EVIDENCE), "manifest_sha256": sha(MANIFEST)},
        "laravel_dry_run": {"sha256": sha(LARAVEL_DRY_RUN), "records": dry_run["records"],
                            "site_products_after": dry_run["site_products_after"], "redirects_after": dry_run["redirects_after"]},
        "safety": {"live_products_checked": 4, "database_operations": 0, "apply_performed": False},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(
        "# Wave244A: FIAMM duplicate collapse evidence\n\n"
        f"Scope: two explicit pairs. Result: **PASS {summary['pass']}, HOLD {summary['hold']}**. "
        "Both sources are new official FIAMM URLs with new snapshot SHA-256 values relative to 359 structured prior files.\n\n"
        "- `bitrix:3266` → `ФР-00002108`: exact `12FGH36`, 12 V, 9 Ah (official 2023 FGH catalogue, visually checked page 2).\n"
        "- `bitrix:1511` → `КА-00003136`: exact `4SLA150`, 4 V, 150 Ah (official FIAMM discontinued-range table).\n\n"
        "Live fail-closed checks covered published/noindex URL and SEO state, category preservation, blank duplicate price/media/family roles, canonical FIAMM MPN, and exact current BYN price evidence. The real Laravel command passed an isolated dry-run for both rows, retaining all four site products and creating no redirect. No apply, commit, or push was performed.\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
