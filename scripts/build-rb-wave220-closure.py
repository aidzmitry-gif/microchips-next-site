#!/usr/bin/env python3
"""Close the fixed RB B2B research universe without web, DB, or apply work."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
PROCESSED_3500 = GEN / "rb-b2b-processed-register-wave218.csv"
WAVE219_A = GEN / "rb-wave219a-final-remainder-evidence.csv"
WAVE219_B = GEN / "rb-wave219b-high-source-evidence.csv"
WAVE219_C = GEN / "rb-wave219c-final-remainder-evidence.csv"
HISTORICAL_READINESS = GEN / "rb-full-content-readiness-wave172-after.csv"
LIVE_READINESS = GEN / "rb-full-content-readiness-wave221-after.csv"
HOLDS = GEN / "rb-known-hold-products-wave172-cumulative.csv"
REGISTER = GEN / "rb-b2b-processed-register-wave220.csv"
REGISTER_SUMMARY = GEN / "rb-b2b-processed-register-wave220.summary.json"
QUEUE = GEN / "rb-b2b-priority-queue-wave220.csv"
QUEUE_SUMMARY = GEN / "rb-b2b-priority-queue-wave220.summary.json"
VERIFY = GEN / "rb-b2b-wave220-closure.verification.json"
RECONCILIATION = GEN / "rb-b2b-wave220-live-collapse-reconciliation.csv"
REPORT = ROOT / "docs/audits/2026-07-29-wave220-research-universe-closure.md"
PRIORITY = ROOT / "scripts/build-rb-b2b-priority-queue.py"

PINS = {
    PROCESSED_3500: (3500, "36397da35ec4d8b796bbf5a1ac3287a9905ef30dc372e232d02a80f0dec4c214"),
    WAVE219_A: (277, "87387b02acfa6e207f45daf8acfb632875cc1c19f065188f9b4a34d9a54a35bb"),
    WAVE219_B: (60, "cbc975fcb67d41b2d4eeb383671ced52b1240236af18ecdc20c4d3d5665b5a00"),
    WAVE219_C: (57, "16eae29ca7541c3acf3cc7643fa22efd9fa145ba0e02955c1f1d0e17b81d64ee"),
    HISTORICAL_READINESS: (16415, "a9f683f30ee06adc5cad46a545a4266e74c5175c1244f5a3431b290dcdaa8493"),
    LIVE_READINESS: (16816, "6992ea926b7007e61b1ec0d818d5a1866ef01ea8591c31cc2b5227d2938ad06b"),
    HOLDS: (3003, "a01bc64f7c3aedf025e50b22de0988ff3221b6cf957c654ea7396268a954ab7f"),
}
EXPECTED_UNIVERSE_ROWS = 3894
EXPECTED_INCOMPLETE_B2B_ROWS = 3903
EXPECTED_HOLDS_IN_UNIVERSE = 9
EXPECTED_LIVE_HISTORICAL_IDS = 3888
EXPECTED_LIVE_B2B_ROWS = 4337
EXPECTED_LIVE_B2B_OUTSIDE_HISTORICAL_LEDGER = 449

HONEYWELL_LINKS = ROOT / "docs/imports/rb-family-duplicate-collapse-honeywell-bat-eda50k-1-wave174.csv"
HONEYWELL_FAMILY = ROOT / "docs/imports/rb-product-families-honeywell-bat-eda50k-1-wave174-2026-07-29.json"
WAVE202_DUPLICATES = ROOT / "docs/imports/rb-reviewed-noindex-duplicates-motorola-symbol-wave202-2026-07-29.json"
WAVE201_DUPLICATES = ROOT / "docs/imports/rb-reviewed-noindex-duplicates-cameron-sino-wave201-2026-07-29.json"
COLLAPSE_PINS = {
    HONEYWELL_LINKS: "0a9b5506dc839352a851282c31e3869e0ab23dd9ff2d20310597888f58f6aafa",
    HONEYWELL_FAMILY: "e396ff9149da289e0803a8d89d372d05fee01ffd567c7275941137cb96d95cad",
    WAVE202_DUPLICATES: "1e72f3ab220f4ae396c163175102c0ece7e6a9ebae71298c04cd77f986712f7c",
    WAVE201_DUPLICATES: "ab9a8eaf1dadfe8bee42d9a525f2ea4a6e2dd56500253ecf8f840ba063e73822",
}
EXPECTED_COLLAPSES = {
    "bitrix:12270": ("bitrix:12116", "wave174_honeywell_family", HONEYWELL_FAMILY),
    "bitrix:24006": ("bitrix:12130", "wave202_strict_duplicate", WAVE202_DUPLICATES),
    "bitrix:24007": ("bitrix:12146", "wave202_strict_duplicate", WAVE202_DUPLICATES),
    "bitrix:24008": ("bitrix:12139", "wave202_strict_duplicate", WAVE202_DUPLICATES),
    "bitrix:24009": ("bitrix:12142", "wave202_strict_duplicate", WAVE202_DUPLICATES),
    "bitrix:24052": ("bitrix:12149", "wave201_strict_duplicate", WAVE201_DUPLICATES),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pinned_rows(path: Path) -> list[dict[str, str]]:
    result = read_rows(path)
    expected_rows, expected_hash = PINS[path]
    ids = [row.get("product_external_id", "") for row in result]
    if len(result) != expected_rows or sha256(path) != expected_hash:
        raise SystemExit(f"pinned input drift: {path.name}")
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise SystemExit(f"invalid external-id uniqueness: {path.name}")
    return result


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load local module: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_register(entries: list[tuple[str, str, str]]) -> None:
    with REGISTER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "processed_wave", "source_artifact"], lineterminator="\n")
        writer.writeheader()
        writer.writerows({"product_external_id": external_id, "processed_wave": wave, "source_artifact": artifact} for external_id, wave, artifact in entries)


def run_zero_queue(register_hash: str) -> None:
    command = [
        sys.executable, str(PRIORITY),
        "--input", str(HISTORICAL_READINESS), "--holds", str(HOLDS), "--processed", str(REGISTER),
        "--output", str(QUEUE), "--summary", str(QUEUE_SUMMARY),
        "--expected-input-sha256", PINS[HISTORICAL_READINESS][1],
        "--expected-hold-sha256", PINS[HOLDS][1],
        "--expected-processed-sha256", register_hash,
        "--expected-records", str(PINS[HISTORICAL_READINESS][0]),
        "--expected-processed-records", str(EXPECTED_UNIVERSE_ROWS), "--limit", "500",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise SystemExit(result.stderr.strip() or result.stdout.strip())


def validate_collapse_evidence(live_b2b_ids: set[str]) -> list[dict[str, str]]:
    if any(sha256(path) != digest for path, digest in COLLAPSE_PINS.items()):
        raise SystemExit("collapse evidence pin drift")
    honeywell_links = read_rows(HONEYWELL_LINKS)
    if honeywell_links != [{"duplicate_external_id": "bitrix:12270", "survivor_external_id": "bitrix:12116"}]:
        raise SystemExit("Honeywell collapse link drift")
    honeywell = json.loads(HONEYWELL_FAMILY.read_text(encoding="utf-8"))
    families = honeywell.get("families")
    if honeywell.get("purpose", "").find("without losing its legacy URL") < 0 or not isinstance(families, list) or len(families) != 1:
        raise SystemExit("Honeywell family redirect evidence drift")
    family = families[0]
    if family.get("canonical_external_id") != "bitrix:12116" or family.get("model_core") != "BAT-EDA50K-1":
        raise SystemExit("Honeywell canonical survivor drift")
    variants = family.get("variants")
    if not isinstance(variants, list) or len(variants) != 1:
        raise SystemExit("Honeywell retired variant cardinality drift")
    variant = variants[0]
    if variant.get("external_id") != "bitrix:12270" or variant.get("variant_key") != "duplicate-bitrix-12270" or variant.get("source_url") != family.get("source_url") or variant.get("attributes") != {} or variant.get("retire_paths") != ["/catalog/industrial-batteries/batteries-industrial/legacy-bitrix-12270"]:
        # Avoid accepting a different retirement path. The localized label is
        # not semantic evidence and is deliberately not normalized.
        raise SystemExit("Honeywell retired variant/legacy path drift")

    def duplicate_records(path: Path, expected_ids: set[str], required_redirect_phrase: str) -> dict[str, dict]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if required_redirect_phrase not in payload.get("purpose", ""):
            raise SystemExit(f"redirect purpose drift: {path.name}")
        records = payload.get("duplicates")
        if not isinstance(records, list) or {row.get("duplicate_external_id") for row in records} != expected_ids:
            raise SystemExit(f"duplicate manifest scope drift: {path.name}")
        for row in records:
            duplicate = row["duplicate_external_id"]
            survivor = row.get("survivor_external_id", "")
            if not survivor or row.get("duplicate_path") != f"/catalog/industrial-batteries/batteries-industrial/legacy-{duplicate.replace('bitrix:', 'bitrix-')}" or row.get("survivor_path") != f"/catalog/industrial-batteries/batteries-industrial/legacy-{survivor.replace('bitrix:', 'bitrix-')}" or not row.get("evidence_refs"):
                raise SystemExit(f"redirect path/evidence drift: {duplicate}")
            for reference in row["evidence_refs"]:
                if not (ROOT / reference).is_file():
                    raise SystemExit(f"missing authoritative evidence ref: {reference}")
        return {row["duplicate_external_id"]: row for row in records}

    wave202 = duplicate_records(WAVE202_DUPLICATES, {"bitrix:24006", "bitrix:24007", "bitrix:24008", "bitrix:24009"}, "permanent redirects")
    wave201 = duplicate_records(WAVE201_DUPLICATES, {"bitrix:24052"}, "301 path")
    evidence = {
        "bitrix:12270": {"survivor_external_id": "bitrix:12116", "collapse_kind": "wave174_honeywell_family", "manifest_path": HONEYWELL_FAMILY.relative_to(ROOT).as_posix(), "retired_path": "/catalog/industrial-batteries/batteries-industrial/legacy-bitrix-12270", "survivor_path": "/catalog/industrial-batteries/batteries-industrial/legacy-bitrix-12116"},
        **{external_id: {"survivor_external_id": record["survivor_external_id"], "collapse_kind": "wave202_strict_duplicate", "manifest_path": WAVE202_DUPLICATES.relative_to(ROOT).as_posix(), "retired_path": record["duplicate_path"], "survivor_path": record["survivor_path"]} for external_id, record in wave202.items()},
        "bitrix:24052": {"survivor_external_id": wave201["bitrix:24052"]["survivor_external_id"], "collapse_kind": "wave201_strict_duplicate", "manifest_path": WAVE201_DUPLICATES.relative_to(ROOT).as_posix(), "retired_path": wave201["bitrix:24052"]["duplicate_path"], "survivor_path": wave201["bitrix:24052"]["survivor_path"]},
    }
    if set(evidence) != set(EXPECTED_COLLAPSES):
        raise SystemExit("collapse evidence did not cover the authoritative six")
    rows = []
    for external_id in sorted(evidence):
        record = evidence[external_id]
        expected_survivor, expected_kind, expected_manifest = EXPECTED_COLLAPSES[external_id]
        if record["survivor_external_id"] != expected_survivor or record["collapse_kind"] != expected_kind or record["manifest_path"] != expected_manifest.relative_to(ROOT).as_posix() or expected_survivor not in live_b2b_ids:
            raise SystemExit(f"collapse survivor is invalid or absent from live B2B: {external_id}")
        rows.append({"historical_external_id": external_id, **record})
    return rows


def write_reconciliation(rows: list[dict[str, str]]) -> None:
    with RECONCILIATION.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["historical_external_id", "survivor_external_id", "collapse_kind", "manifest_path", "retired_path", "survivor_path"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_report() -> None:
    REPORT.write_text(
        "# Wave220 fixed research-universe closure\n\n"
        "Wave220 extends the 3,500-ID Wave218 register with the three disjoint Wave219 ledgers: A 277, B 60 and C 57. The resulting historical research ledger has 3,894 unique IDs and exactly equals the fixed Wave172 incomplete, non-held B2B research universe.\n\n"
        "Wave221 is a live-state reconciliation, not the historical universe. Its B2B footprint contains 3,888 of the 3,894 historical IDs. The exact six absent IDs are all accounted for by pinned duplicate-collapse manifests, with each canonical survivor still present in the Wave221 B2B state and each retired legacy path recorded by the authoritative manifest. Wave221 also contains live B2B rows outside this historical ledger; they are deliberately not silently folded into the historical closure.\n\n"
        "The header-only queue remains a verification of the pinned historical Wave172 universe, not a claim about all Wave221 live B2B products. No web request, database query, database mutation, or apply action occurs. Two local renderings are byte-identical.\n",
        encoding="utf-8",
    )


def main() -> None:
    prior, wave_a, wave_b, wave_c, historical_readiness, live_readiness, holds = (pinned_rows(path) for path in PINS)
    priority = load_module(PRIORITY, "rb_wave220_priority")
    planner = load_module(ROOT / "scripts/build-rb-b2b-next-source-batch.py", "rb_wave220_planner")

    lineages = [prior, wave_a, wave_b, wave_c]
    lineage_sets = [{row["product_external_id"] for row in source} for source in lineages]
    pairwise_overlap = sorted({external_id for left, left_ids in enumerate(lineage_sets) for right, right_ids in enumerate(lineage_sets) if left < right for external_id in left_ids & right_ids})
    if pairwise_overlap:
        raise SystemExit(f"processed lineage overlap: {pairwise_overlap[:5]}")

    entries = [(row["product_external_id"], row["processed_wave"], row["source_artifact"]) for row in prior]
    entries += [(row["product_external_id"], "wave219a", WAVE219_A.name) for row in wave_a]
    entries += [(row["product_external_id"], "wave219b", WAVE219_B.name) for row in wave_b]
    entries += [(row["product_external_id"], "wave219c", WAVE219_C.name) for row in wave_c]
    processed_ids = {entry[0] for entry in entries}
    if len(entries) != EXPECTED_UNIVERSE_ROWS or len(processed_ids) != EXPECTED_UNIVERSE_ROWS:
        raise SystemExit("Wave220 register must contain exactly 3894 unique IDs")

    readiness_by_id = {row["product_external_id"]: row for row in historical_readiness}
    incomplete = {
        row["product_external_id"]
        for row in historical_readiness
        if row["category_external_id"] in priority.B2B_CATEGORY_PRIORITY and row["readiness_class"] != "strict_content_ready"
    }
    hold_ids = {row["product_external_id"] for row in holds}
    universe = incomplete - hold_ids
    missing = sorted(universe - processed_ids)
    extra = sorted(processed_ids - universe)
    if len(incomplete) != EXPECTED_INCOMPLETE_B2B_ROWS or len(hold_ids & incomplete) != EXPECTED_HOLDS_IN_UNIVERSE or len(universe) != EXPECTED_UNIVERSE_ROWS:
        raise SystemExit("fixed research universe drift")
    if missing or extra:
        raise SystemExit(f"closure mismatch: missing={missing[:5]}, extra={extra[:5]}")
    if any(external_id not in readiness_by_id for external_id in processed_ids):
        raise SystemExit("processed ID absent from historical readiness input")

    leaked_automotive = sorted(external_id for external_id in processed_ids if planner.AUTOMOTIVE.search(readiness_by_id[external_id]["name"]))
    leaked_electronics = sorted(external_id for external_id in processed_ids if planner.ELECTRONICS.search(readiness_by_id[external_id]["name"]))
    leaked_non_b2b = sorted(external_id for external_id in processed_ids if readiness_by_id[external_id]["category_external_id"] not in priority.B2B_CATEGORY_PRIORITY)
    if leaked_automotive or leaked_electronics or leaked_non_b2b:
        raise SystemExit("automotive/electronics/non-B2B scope leak")

    live_b2b_ids = {row["product_external_id"] for row in live_readiness if row["category_external_id"] in priority.B2B_CATEGORY_PRIORITY}
    live_historical_ids = processed_ids & live_b2b_ids
    missing_from_live = sorted(processed_ids - live_b2b_ids)
    live_outside_historical = sorted(live_b2b_ids - processed_ids)
    if len(live_b2b_ids) != EXPECTED_LIVE_B2B_ROWS or len(live_historical_ids) != EXPECTED_LIVE_HISTORICAL_IDS or len(live_outside_historical) != EXPECTED_LIVE_B2B_OUTSIDE_HISTORICAL_LEDGER:
        raise SystemExit("Wave221 live B2B scope drift")
    if missing_from_live != sorted(EXPECTED_COLLAPSES):
        raise SystemExit(f"unexplained historical IDs absent from live state: {missing_from_live}")
    collapse_rows = validate_collapse_evidence(live_b2b_ids)
    write_reconciliation(collapse_rows)

    write_register(entries)
    register_summary = {
        "schema_version": 1,
        "wave": "wave220",
        "processed_records": EXPECTED_UNIVERSE_ROWS,
        "unique_product_external_ids": EXPECTED_UNIVERSE_ROWS,
        "lineage": {"wave218_register": 3500, "wave219a": 277, "wave219b": 60, "wave219c": 57, "wave219_disjoint_union": 394, "lineage_overlap_records": 0},
        "input_sha256": {path.name: sha256(path) for path in (PROCESSED_3500, WAVE219_A, WAVE219_B, WAVE219_C)},
        "automatic_web_requests": 0,
        "automatic_database_queries": 0,
        "automatic_database_mutations": 0,
    }
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_zero_queue(sha256(REGISTER))

    queue = read_rows(QUEUE)
    queue_summary = json.loads(QUEUE_SUMMARY.read_text(encoding="utf-8"))
    if queue or queue_summary["eligible_unreviewed_unprocessed"] != 0 or queue_summary["selected_records"] != 0:
        raise SystemExit("Wave220 must leave a zero-record queue")
    artifacts = (REGISTER, REGISTER_SUMMARY, QUEUE, QUEUE_SUMMARY, RECONCILIATION)
    first = {path.name: path.read_bytes() for path in artifacts}
    write_register(entries)
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_zero_queue(sha256(REGISTER))
    write_reconciliation(collapse_rows)
    identical = {path.name: first[path.name] == path.read_bytes() for path in artifacts}
    if not all(identical.values()):
        raise SystemExit(f"non-deterministic rerun: {identical}")

    verify = {
        "schema_version": 1,
        "wave": "wave220",
        "inputs": {path.name: {"rows": PINS[path][0], "sha256": sha256(path)} for path in PINS},
        "lineage": {"processed3500": 3500, "wave219a": 277, "wave219b": 60, "wave219c": 57, "wave219_total": 394, "pairwise_overlap_ids": []},
        "historical_research_universe": {"source": HISTORICAL_READINESS.relative_to(ROOT).as_posix(), "incomplete_b2b_rows": len(incomplete), "hold_rows_in_universe": len(hold_ids & incomplete), "rows": len(universe)},
        "historical_closure": {"processed_rows": len(entries), "unique_processed_ids": len(processed_ids), "missing_ids": missing, "extra_ids": extra, "duplicate_ids": [], "equals_fixed_research_universe": processed_ids == universe},
        "historical_remaining_queue": {"source": HISTORICAL_READINESS.relative_to(ROOT).as_posix(), "path": QUEUE.relative_to(ROOT).as_posix(), "rows": len(queue), "eligible_unreviewed_unprocessed": queue_summary["eligible_unreviewed_unprocessed"], "selected_records": queue_summary["selected_records"], "output_sha256": sha256(QUEUE)},
        "live_wave221_reconciliation": {"source": LIVE_READINESS.relative_to(ROOT).as_posix(), "live_b2b_rows": len(live_b2b_ids), "historical_ledger_ids_present": len(live_historical_ids), "historical_ledger_ids_absent": missing_from_live, "live_b2b_ids_outside_historical_ledger": len(live_outside_historical), "historical_ledger_is_live_universe": False, "collapse_reconciliation_path": RECONCILIATION.relative_to(ROOT).as_posix(), "collapse_reconciliation_sha256": sha256(RECONCILIATION)},
        "scope": {"automotive_leak_ids": leaked_automotive, "electronics_leak_ids": leaked_electronics, "non_b2b_leak_ids": leaked_non_b2b},
        "byte_identical_rerun": identical,
        "automatic_web_requests": 0,
        "automatic_database_queries": 0,
        "automatic_database_mutations": 0,
        "apply_performed": False,
    }
    VERIFY.write_text(json.dumps(verify, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report()
    print(json.dumps({"historical_processed": len(processed_ids), "historical_missing": len(missing), "historical_extra": len(extra), "historical_remaining_queue": len(queue), "live_historical_ids": len(live_historical_ids), "collapsed_absences": len(missing_from_live), "rerun": all(identical.values())}))


if __name__ == "__main__":
    main()
