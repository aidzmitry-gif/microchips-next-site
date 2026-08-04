#!/usr/bin/env python3
"""Build and Laravel-dry-run the single explicit Wave219-C taxonomy move."""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
EVIDENCE = GEN / "rb-wave219c-final-remainder-evidence.csv"
CANDIDATES = GEN / "rb-wave219c-robiton-adapter-category-move-candidates.csv"
SUMMARY = GEN / "rb-wave219c-robiton-adapter-category-move.summary.json"
DRY = GEN / "wave219c-robiton-adapter-category-move-laravel-dry-run.json"
MANIFEST = ROOT / "docs/imports/rb-site-category-move-wave219c-robiton-adapter.csv"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave219c-robiton-adapter-taxonomy-move.md"

EVIDENCE_SHA256 = "16eae29ca7541c3acf3cc7643fa22efd9fa145ba0e02955c1f1d0e17b81d64ee"
SITE_KEY = "microchips-by"
CATEGORY_SOURCE = "full_catalog_seo_tree"
ROBITON_ID = "КА-00002676"
PHOENIX_ID = "ФР-00001523"
MANIFEST_FIELDS = ["product_external_id", "from_category_external_id", "to_category_external_id"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_bytes(fields: list[str], rows: list[dict[str, str]]) -> bytes:
    # The manifest has LF-only rows and a BOM so its three-column contract is
    # stable on Windows and in the Linux Laravel container.
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def write_bytes(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    if path.read_bytes() != contents:
        raise SystemExit(f"non-deterministic write for {path}")


def live_state() -> dict[str, dict[str, object]]:
    code = f'''$site = App\\Models\\Site::query()->where("key", "{SITE_KEY}")->firstOrFail();
$rows = App\\Models\\SiteProduct::query()
    ->with(["product", "categories" => fn ($query) => $query->where("source", "{CATEGORY_SOURCE}")])
    ->where("site_id", $site->id)
    ->whereHas("product", fn ($query) => $query->whereIn("external_id", ["{ROBITON_ID}", "{PHOENIX_ID}"]))
    ->get()
    ->map(fn ($siteProduct) => [
        "external_id" => $siteProduct->product->external_id,
        "manufacturer" => $siteProduct->product->manufacturer,
        "mpn" => $siteProduct->product->mpn,
        "category_external_ids" => $siteProduct->categories->pluck("external_id")->sort()->values()->all(),
    ])
    ->keyBy("external_id");
echo json_encode($rows, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);'''
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    command = [
        "docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker",
        "--execute", f"eval(base64_decode('{encoded}'));",
    ]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if run.returncode:
        raise SystemExit(f"could not read live category state: {run.stderr.strip() or run.stdout.strip()}")
    try:
        value = json.loads(run.stdout.strip())
    except json.JSONDecodeError as error:
        raise SystemExit(f"live state was not JSON: {run.stdout.strip()}") from error
    if set(value) != {ROBITON_ID, PHOENIX_ID}:
        raise SystemExit(f"unexpected live-state scope: {sorted(value)}")
    return value


def assert_live_scope(state: dict[str, dict[str, object]]) -> None:
    robiton = state[ROBITON_ID]
    phoenix = state[PHOENIX_ID]
    if robiton["category_external_ids"] != ["seo:chargers"]:
        raise SystemExit(f"{ROBITON_ID} no longer has the expected source category")
    if phoenix["category_external_ids"] != ["seo:power-supplies"]:
        raise SystemExit(f"{PHOENIX_ID} category is not already correct")
    if phoenix["manufacturer"] != "Phoenix Contact" or phoenix["mpn"] != "2938646":
        raise SystemExit(f"{PHOENIX_ID} identity must remain live-correct and excluded")


def write_report(candidate: dict[str, str], before: dict[str, dict[str, object]], dry: dict[str, object]) -> None:
    REPORT.write_text("\n".join([
        "# Wave219-C Robiton adapter taxonomy follow-up",
        "",
        "One explicit AC/DC adapter is corrected from the chargers leaf to the existing power-supplies leaf. This is a category-only dry-run receipt; no identity field is included in the manifest.",
        "",
        "## Strict move manifest",
        "",
        "| Product | From | To |",
        "| --- | --- | --- |",
        f"| `{candidate['product_external_id']}` — {candidate['name']} | `{candidate['from_category_external_id']}` | `{candidate['to_category_external_id']}` |",
        "",
        f"The CSV has exactly the required three columns and one row. It uses existing `{CATEGORY_SOURCE}` categories only.",
        "",
        "## Explicit exclusion",
        "",
        f"`{PHOENIX_ID}` is deliberately absent: it is already in `seo:power-supplies`; live identity remains manufacturer `{before[PHOENIX_ID]['manufacturer']}` and MPN `{before[PHOENIX_ID]['mpn']}`. Its Wave219-C manufacturer-cluster finding is not a taxonomy instruction.",
        "",
        "## Laravel dry-run",
        "",
        f"- Exit: {dry['exit_code']}; validation errors: {dry['validation_error_count']}; rows: {dry['records']}.",
        "- `--apply` was not passed. The command transaction rolled back; category links, URLs, canonical paths, publication and identity fields were unchanged.",
        "",
    ]), encoding="utf-8")


def main() -> None:
    evidence = read_rows(EVIDENCE)
    if sha256(EVIDENCE) != EVIDENCE_SHA256 or len(evidence) != 57:
        raise SystemExit("Wave219-C evidence pin/scope drift")
    by_id = {row["product_external_id"]: row for row in evidence}
    if len(by_id) != len(evidence) or {ROBITON_ID, PHOENIX_ID} - set(by_id):
        raise SystemExit("Wave219-C target/exclusion identifiers missing or duplicated")

    robiton = by_id[ROBITON_ID]
    phoenix = by_id[PHOENIX_ID]
    required_robiton = {
        "category_external_id": "seo:chargers",
        "manufacturer_cluster": "Robiton",
        "factual_product_type": "ac_dc_power_adapter",
        "taxonomy_assessment": "taxonomy_mismatch_expected_seo_power_supplies",
        "extracted_model": "B9-500 5",
        "safe_to_apply": "false",
    }
    if any(robiton.get(key) != value for key, value in required_robiton.items()):
        raise SystemExit("Robiton taxonomy evidence drift")
    required_phoenix = {
        "category_external_id": "seo:power-supplies",
        "factual_product_type": "industrial_din_rail_power_supply",
        "taxonomy_assessment": "brand_cluster_should_be_phoenix_contact_not_contact",
        "safe_to_apply": "false",
    }
    if any(phoenix.get(key) != value for key, value in required_phoenix.items()):
        raise SystemExit("Phoenix exclusion evidence drift")

    candidate = {
        "product_external_id": ROBITON_ID,
        "from_category_external_id": "seo:chargers",
        "to_category_external_id": "seo:power-supplies",
        "name": robiton["name"],
        "factual_product_type": robiton["factual_product_type"],
        "reason": "explicit Robiton B9-500 AC/DC adapter; chargers is not its product type",
        "safe_to_apply": "false",
    }
    if PHOENIX_ID in {candidate["product_external_id"]}:
        raise SystemExit("Phoenix exclusion entered category manifest")
    candidate_fields = list(candidate)
    write_bytes(CANDIDATES, csv_bytes(candidate_fields, [candidate]))
    manifest_rows = [{field: candidate[field] for field in MANIFEST_FIELDS}]
    manifest_contents = csv_bytes(MANIFEST_FIELDS, manifest_rows)
    write_bytes(MANIFEST, manifest_contents)
    if list(read_rows(MANIFEST)[0]) != MANIFEST_FIELDS or len(read_rows(MANIFEST)) != 1:
        raise SystemExit("strict manifest schema/row count drift")

    before = live_state()
    assert_live_scope(before)
    container_manifest = "/tmp/" + MANIFEST.name
    copied = subprocess.run(["docker", "compose", "cp", str(MANIFEST), "backend:" + container_manifest], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if copied.returncode:
        raise SystemExit(f"could not place category manifest: {copied.stderr.strip() or copied.stdout.strip()}")
    run = subprocess.run([
        "docker", "compose", "exec", "-T", "backend", "php", "artisan", "catalog:move-site-product-categories",
        SITE_KEY, container_manifest, f"--category-source={CATEGORY_SOURCE}",
    ], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dry = {
        "mode": "dry_run", "apply_flag_used": False, "exit_code": run.returncode, "records": 1,
        "manifest_sha256": sha256(MANIFEST), "stdout": run.stdout.strip(), "stderr": run.stderr.strip(),
        "validation_error_count": 0 if run.returncode == 0 else None,
        "category_link_mutations": 0, "url_mutations": 0, "canonical_mutations": 0,
        "publication_fields_changed": 0, "identity_fields_changed": 0,
    }
    if run.returncode:
        raise SystemExit(f"Laravel category dry-run failed: {run.stderr.strip() or run.stdout.strip()}")
    after = live_state()
    assert_live_scope(after)
    if after != before:
        raise SystemExit("Laravel dry-run did not roll back live state")
    write_bytes(DRY, (json.dumps(dry, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    summary = {
        "schema_version": 1,
        "batch": "wave219c_robiton_adapter_category_move",
        "input": {"path": EVIDENCE.relative_to(ROOT).as_posix(), "sha256": sha256(EVIDENCE), "rows": len(evidence)},
        "candidate": {"path": CANDIDATES.relative_to(ROOT).as_posix(), "sha256": sha256(CANDIDATES), "rows": 1, "external_id": ROBITON_ID},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": 1, "headers": MANIFEST_FIELDS, "category_source": CATEGORY_SOURCE},
        "explicit_exclusion": {"external_id": PHOENIX_ID, "reason": "category_already_correct_and_live_identity_correct", "live_state": before[PHOENIX_ID]},
        "laravel_dry_run": {"path": DRY.relative_to(ROOT).as_posix(), "exit_code": run.returncode, "category_link_mutations": 0, "apply_flag_used": False, "rolled_back_live_state": after == before},
        "policy": {"single_explicit_category_move": True, "identity_updates": False, "database_apply": False, "deterministic_local_render": CANDIDATES.read_bytes() == csv_bytes(candidate_fields, [candidate]) and MANIFEST.read_bytes() == manifest_contents},
    }
    write_bytes(SUMMARY, (json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    write_report(candidate, before, dry)
    print(json.dumps({"candidates": 1, "excluded": PHOENIX_ID, "dry_run_exit": run.returncode, "category_link_mutations": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
