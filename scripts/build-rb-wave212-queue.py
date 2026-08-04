#!/usr/bin/env python3
"""Materialize Wave212's pinned, deterministic, no-repeat RB B2B queue.

Planning only: no web requests and no application database calls or mutations.
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
REGISTER_210 = GEN / "rb-b2b-processed-register-wave210.csv"
QUEUE_210 = GEN / "rb-b2b-priority-queue-wave210.csv"
READINESS = GEN / "rb-full-content-readiness-wave172-after.csv"
HOLDS = GEN / "rb-known-hold-products-wave172-cumulative.csv"
REGISTER = GEN / "rb-b2b-processed-register-wave212.csv"
REGISTER_SUMMARY = GEN / "rb-b2b-processed-register-wave212.summary.json"
QUEUE = GEN / "rb-b2b-priority-queue-wave212.csv"
QUEUE_SUMMARY = GEN / "rb-b2b-priority-queue-wave212.summary.json"
BATCH = GEN / "rb-b2b-next-source-batch-wave212.csv"
BATCH_SUMMARY = GEN / "rb-b2b-next-source-batch-wave212.summary.json"
VERIFY = GEN / "rb-b2b-wave212.verification.json"
PRIORITY = ROOT / "scripts/build-rb-b2b-priority-queue.py"
PLANNER = ROOT / "scripts/build-rb-b2b-next-source-batch.py"

PINS = {
    REGISTER_210: (1500, "44a2506aeeff82700988aa93c8df592bec15bb148eb7556183e9a14022057bcc"),
    QUEUE_210: (500, "1e12b8e76b0a9e4cbe9e85985f145333e224a5a8dcf488f9922349737eed3b9e"),
    READINESS: (16415, "a9f683f30ee06adc5cad46a545a4266e74c5175c1244f5a3431b290dcdaa8493"),
    HOLDS: (3003, "a01bc64f7c3aedf025e50b22de0988ff3221b6cf957c654ea7396268a954ab7f"),
}

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def pinned(path: Path) -> list[dict[str, str]]:
    data = rows(path); expected_rows, expected_sha = PINS[path]
    ids = [r.get("product_external_id", "") for r in data]
    if len(data) != expected_rows or sha(path) != expected_sha or not all(ids) or len(ids) != len(set(ids)):
        raise SystemExit(f"pinned input drift or invalid IDs: {path.name}")
    return data
def invoke(command: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode: raise SystemExit(result.stderr or result.stdout)
def render(register_sha: str) -> None:
    invoke([sys.executable, str(PRIORITY), "--input", str(READINESS), "--holds", str(HOLDS), "--processed", str(REGISTER), "--output", str(QUEUE), "--summary", str(QUEUE_SUMMARY), "--expected-input-sha256", PINS[READINESS][1], "--expected-hold-sha256", PINS[HOLDS][1], "--expected-processed-sha256", register_sha, "--expected-records", "16415", "--expected-processed-records", "2000", "--limit", "500"])
    invoke([sys.executable, str(PLANNER), "--readiness", str(READINESS), "--processed", str(REGISTER), "--holds", str(HOLDS), "--priority-script", str(PRIORITY), "--output", str(BATCH), "--summary", str(BATCH_SUMMARY), "--expected-readiness-sha256", PINS[READINESS][1], "--expected-processed-sha256", register_sha, "--expected-holds-sha256", PINS[HOLDS][1], "--expected-readiness-records", "16415", "--expected-processed-records", "2000", "--limit", "500"])

def main() -> None:
    register_210, queue_210 = pinned(REGISTER_210), pinned(QUEUE_210)
    prior_ids, appended_ids = {r["product_external_id"] for r in register_210}, {r["product_external_id"] for r in queue_210}
    overlap = sorted(prior_ids & appended_ids)
    if overlap: raise SystemExit(f"wave210 register/queue overlap: {overlap[:5]}")
    pinned(READINESS); pinned(HOLDS)
    fields = list(register_210[0]); merged = register_210 + [{key: row.get(key, "") for key in fields} for row in queue_210]
    merged_ids = [r["product_external_id"] for r in merged]
    if len(merged) != 2000 or len(set(merged_ids)) != 2000: raise SystemExit("Wave212 register must be 2000 unique rows")
    def write_register() -> None:
        with REGISTER.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(merged)
    write_register()
    register_summary = {"schema_version": 1, "wave": "wave212", "input_records": {"wave210_processed": 1500, "wave210_priority": 500}, "input_sha256": {"wave210_processed": sha(REGISTER_210), "wave210_priority": sha(QUEUE_210)}, "input_overlap_records": 0, "processed_records": 2000, "unique_product_external_ids": 2000, "output_sha256": sha(REGISTER), "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0}
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render(sha(REGISTER))
    artifacts = (REGISTER, REGISTER_SUMMARY, QUEUE, QUEUE_SUMMARY, BATCH, BATCH_SUMMARY)
    first = {p.name: p.read_bytes() for p in artifacts}
    write_register(); REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); render(sha(REGISTER))
    identical = {p.name: first[p.name] == p.read_bytes() for p in artifacts}
    if not all(identical.values()): raise SystemExit(f"non-deterministic rerun: {identical}")
    planned, batch = rows(QUEUE), rows(BATCH)
    planned_ids, batch_ids = {r["product_external_id"] for r in planned}, {r["product_external_id"] for r in batch}
    if len(planned) != len(planned_ids) != 500 or planned_ids & set(merged_ids): raise SystemExit("Wave212 priority no-repeat invariant failed")
    if len(batch) != len(batch_ids) != 500 or batch_ids != planned_ids: raise SystemExit("Wave212 planner selection invariant failed")
    queue_summary, batch_summary = json.loads(QUEUE_SUMMARY.read_text(encoding="utf-8")), json.loads(BATCH_SUMMARY.read_text(encoding="utf-8"))
    if batch_summary["automotive_excluded"] != 0 or batch_summary["electronics_excluded"] != 0: raise SystemExit("Wave212 category exclusion invariant failed")
    verification = {"schema_version": 1, "wave": "wave212", "inputs": {p.name: {"rows": PINS[p][0], "sha256": sha(p)} for p in PINS}, "register": {"rows": 2000, "unique_ids": 2000, "overlap_with_wave210_processed": 0, "output_sha256": sha(REGISTER)}, "priority": {"rows": len(planned), "unique_ids": len(planned_ids), "overlap_with_processed_register": len(planned_ids & set(merged_ids)), "output_sha256": sha(QUEUE)}, "source_planner": {"rows": len(batch), "overlap_with_processed_register": len(batch_ids & set(merged_ids)), "automotive_excluded": batch_summary["automotive_excluded"], "electronics_excluded": batch_summary["electronics_excluded"], "output_sha256": sha(BATCH)}, "byte_identical_rerun": identical, "safe_to_apply_records": queue_summary["safe_to_apply_records"], "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0}
    VERIFY.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"register": 2000, "priority": len(planned), "batch": len(batch), "rerun": all(identical.values())}))
if __name__ == "__main__": main()
