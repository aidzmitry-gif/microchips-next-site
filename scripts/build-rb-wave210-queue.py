#!/usr/bin/env python3
"""Materialize the deterministic, no-repeat Wave210 RB B2B research queue.

This is a planning-only orchestration: it writes generated audit artifacts and
does not request the web or call the application database.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
REGISTER_208 = GEN / "rb-b2b-processed-register-wave208.csv"
QUEUE_208 = GEN / "rb-b2b-priority-queue-wave208.csv"
READINESS = GEN / "rb-full-content-readiness-wave172-after.csv"
HOLDS = GEN / "rb-known-hold-products-wave172-cumulative.csv"
REGISTER_210 = GEN / "rb-b2b-processed-register-wave210.csv"
REGISTER_SUMMARY = GEN / "rb-b2b-processed-register-wave210.summary.json"
QUEUE_210 = GEN / "rb-b2b-priority-queue-wave210.csv"
QUEUE_SUMMARY = GEN / "rb-b2b-priority-queue-wave210.summary.json"
BATCH_210 = GEN / "rb-b2b-next-source-batch-wave210.csv"
BATCH_SUMMARY = GEN / "rb-b2b-next-source-batch-wave210.summary.json"
VERIFY = GEN / "rb-b2b-wave210.verification.json"
PRIORITY = ROOT / "scripts/build-rb-b2b-priority-queue.py"
PLANNER = ROOT / "scripts/build-rb-b2b-next-source-batch.py"

PINS = {
    REGISTER_208: (1000, "059cb210edd42041e88c0c68adb15d7133012f7b87932d9d3ef0708ab2978cd4"),
    QUEUE_208: (500, "2511f0853acbf21227e339743c1668371a5e3f49e15fbb1c3f8400936cfea74b"),
    READINESS: (16415, "a9f683f30ee06adc5cad46a545a4266e74c5175c1244f5a3431b290dcdaa8493"),
    HOLDS: (3003, "a01bc64f7c3aedf025e50b22de0988ff3221b6cf957c654ea7396268a954ab7f"),
}

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def assert_pinned(path: Path) -> list[dict[str, str]]:
    expected_rows, expected_hash = PINS[path]
    result = rows(path)
    if len(result) != expected_rows or sha(path) != expected_hash:
        raise SystemExit(f"pinned input drift: {path.name}")
    ids = [r.get("product_external_id", "") for r in result]
    if not all(ids) or len(ids) != len(set(ids)): raise SystemExit(f"invalid IDs: {path.name}")
    return result
def invoke(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode: raise SystemExit(result.stderr or result.stdout)

def run_priority_and_planner(register: Path, queue: Path, queue_summary: Path, batch: Path, batch_summary: Path) -> None:
    invoke([sys.executable, str(PRIORITY), "--input", str(READINESS), "--holds", str(HOLDS), "--processed", str(register), "--output", str(queue), "--summary", str(queue_summary), "--expected-input-sha256", PINS[READINESS][1], "--expected-hold-sha256", PINS[HOLDS][1], "--expected-processed-sha256", sha(register), "--expected-records", "16415", "--expected-processed-records", "1500", "--limit", "500"])
    invoke([sys.executable, str(PLANNER), "--readiness", str(READINESS), "--processed", str(register), "--holds", str(HOLDS), "--priority-script", str(PRIORITY), "--output", str(batch), "--summary", str(batch_summary), "--expected-readiness-sha256", PINS[READINESS][1], "--expected-processed-sha256", sha(register), "--expected-holds-sha256", PINS[HOLDS][1], "--expected-readiness-records", "16415", "--expected-processed-records", "1500", "--limit", "500"])

def main() -> None:
    register_rows, queue_rows = assert_pinned(REGISTER_208), assert_pinned(QUEUE_208)
    prior_ids = {r["product_external_id"] for r in register_rows}; next_ids = {r["product_external_id"] for r in queue_rows}
    overlap = sorted(prior_ids & next_ids)
    if overlap: raise SystemExit(f"wave208 register/queue overlap: {overlap[:5]}")
    readiness_rows, hold_rows = assert_pinned(READINESS), assert_pinned(HOLDS)
    fieldnames = list(register_rows[0])
    appended = [{key: row.get(key, "") for key in fieldnames} for row in queue_rows]
    merged = register_rows + appended
    merged_ids = [r["product_external_id"] for r in merged]
    if len(merged) != 1500 or len(set(merged_ids)) != 1500: raise SystemExit("Wave210 register must be 1500 unique rows")
    with REGISTER_210.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n"); writer.writeheader(); writer.writerows(merged)
    register_summary = {"schema_version": 1, "wave": "wave210", "input_records": {"wave208_processed": 1000, "wave208_priority": 500}, "input_sha256": {"wave208_processed": sha(REGISTER_208), "wave208_priority": sha(QUEUE_208)}, "input_overlap_records": 0, "processed_records": 1500, "unique_product_external_ids": 1500, "output_sha256": sha(REGISTER_210), "automatic_web_requests": 0, "automatic_database_mutations": 0}
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_priority_and_planner(REGISTER_210, QUEUE_210, QUEUE_SUMMARY, BATCH_210, BATCH_SUMMARY)
    first = {p.name: p.read_bytes() for p in (REGISTER_210, REGISTER_SUMMARY, QUEUE_210, QUEUE_SUMMARY, BATCH_210, BATCH_SUMMARY)}
    # Re-run existing builders against the identical pinned inputs; the register is re-rendered identically.
    with REGISTER_210.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n"); writer.writeheader(); writer.writerows(merged)
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_priority_and_planner(REGISTER_210, QUEUE_210, QUEUE_SUMMARY, BATCH_210, BATCH_SUMMARY)
    byte_identical = {name: first[name] == (GEN / name).read_bytes() for name in first}
    if not all(byte_identical.values()): raise SystemExit(f"non-deterministic rerun: {byte_identical}")
    planned, source_batch = rows(QUEUE_210), rows(BATCH_210)
    planned_ids = {r["product_external_id"] for r in planned}; batch_ids = {r["product_external_id"] for r in source_batch}
    if len(planned) != 500 or len(planned_ids) != 500 or planned_ids & set(merged_ids): raise SystemExit("Wave210 priority no-repeat invariant failed")
    if len(source_batch) != 500 or batch_ids != planned_ids: raise SystemExit("Wave210 planner must preserve priority selection")
    queue_report, batch_report = json.loads(QUEUE_SUMMARY.read_text(encoding="utf-8")), json.loads(BATCH_SUMMARY.read_text(encoding="utf-8"))
    verification = {"schema_version": 1, "wave": "wave210", "inputs": {p.name: {"rows": PINS[p][0], "sha256": sha(p)} for p in PINS}, "register": {"rows": 1500, "unique_ids": 1500, "overlap_with_wave208_processed": 0, "output_sha256": sha(REGISTER_210)}, "priority": {"rows": len(planned), "unique_ids": len(planned_ids), "overlap_with_processed_register": len(planned_ids & set(merged_ids)), "output_sha256": sha(QUEUE_210)}, "source_planner": {"rows": len(source_batch), "overlap_with_processed_register": len(batch_ids & set(merged_ids)), "automotive_excluded": batch_report["automotive_excluded"], "electronics_excluded": batch_report["electronics_excluded"], "output_sha256": sha(BATCH_210)}, "byte_identical_rerun": byte_identical, "safe_to_apply_records": queue_report["safe_to_apply_records"], "automatic_web_requests": 0, "automatic_database_mutations": 0}
    VERIFY.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"register": 1500, "priority": len(planned), "batch": len(source_batch), "rerun": all(byte_identical.values())}, ensure_ascii=False))
if __name__ == "__main__": main()
