#!/usr/bin/env python3
"""Materialize the deterministic Wave214 no-repeat RB B2B planning queue.

This is a local planning step.  It only consumes SHA-pinned CSV inputs and
uses the existing priority builder/source planner; it makes no web or DB call.
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
PRIOR = GEN / "rb-b2b-processed-register-wave212.csv"
APPEND = GEN / "rb-b2b-priority-queue-wave212.csv"
READINESS = GEN / "rb-full-content-readiness-wave172-after.csv"
HOLDS = GEN / "rb-known-hold-products-wave172-cumulative.csv"
REGISTER = GEN / "rb-b2b-processed-register-wave214.csv"
REGISTER_SUMMARY = GEN / "rb-b2b-processed-register-wave214.summary.json"
QUEUE = GEN / "rb-b2b-priority-queue-wave214.csv"
QUEUE_SUMMARY = GEN / "rb-b2b-priority-queue-wave214.summary.json"
BATCH = GEN / "rb-b2b-next-source-batch-wave214.csv"
BATCH_SUMMARY = GEN / "rb-b2b-next-source-batch-wave214.summary.json"
VERIFY = GEN / "rb-b2b-wave214.verification.json"
PRIORITY = ROOT / "scripts/build-rb-b2b-priority-queue.py"
PLANNER = ROOT / "scripts/build-rb-b2b-next-source-batch.py"
PINS = {
    PRIOR: (2000, "4477f1b33fac62a06d0bd5d804447ab1e18238b106f48f7ebbb5d88e57a72d08"),
    APPEND: (500, "9cac22a7751ad2d945b771b75031f3c466dd57dc908c91856316e5a0e4d77bd9"),
    READINESS: (16415, "a9f683f30ee06adc5cad46a545a4266e74c5175c1244f5a3431b290dcdaa8493"),
    HOLDS: (3003, "a01bc64f7c3aedf025e50b22de0988ff3221b6cf957c654ea7396268a954ab7f"),
}

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f: return list(csv.DictReader(f))
def pin(path: Path) -> list[dict[str, str]]:
    data = rows(path); count, digest = PINS[path]; ids = [row.get("product_external_id", "") for row in data]
    if len(data) != count or sha(path) != digest or not all(ids) or len(ids) != len(set(ids)):
        raise SystemExit(f"pinned input drift: {path.name}")
    return data
def invoke(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode: raise SystemExit(result.stderr or result.stdout)
def render(register_sha: str) -> None:
    invoke([sys.executable, str(PRIORITY), "--input", str(READINESS), "--holds", str(HOLDS), "--processed", str(REGISTER), "--output", str(QUEUE), "--summary", str(QUEUE_SUMMARY), "--expected-input-sha256", PINS[READINESS][1], "--expected-hold-sha256", PINS[HOLDS][1], "--expected-processed-sha256", register_sha, "--expected-records", "16415", "--expected-processed-records", "2500", "--limit", "500"])
    invoke([sys.executable, str(PLANNER), "--readiness", str(READINESS), "--processed", str(REGISTER), "--holds", str(HOLDS), "--priority-script", str(PRIORITY), "--output", str(BATCH), "--summary", str(BATCH_SUMMARY), "--expected-readiness-sha256", PINS[READINESS][1], "--expected-processed-sha256", register_sha, "--expected-holds-sha256", PINS[HOLDS][1], "--expected-readiness-records", "16415", "--expected-processed-records", "2500", "--limit", "500"])

def main() -> None:
    prior, append = pin(PRIOR), pin(APPEND)
    readiness, holds = pin(READINESS), pin(HOLDS)
    prior_ids, append_ids = {row["product_external_id"] for row in prior}, {row["product_external_id"] for row in append}
    if prior_ids & append_ids: raise SystemExit("Wave214 input register/queue overlap")
    fields = list(prior[0]); merged = prior + [{field: row.get(field, "") for field in fields} for row in append]
    merged_ids = [row["product_external_id"] for row in merged]
    if len(merged) != 2500 or len(set(merged_ids)) != 2500: raise SystemExit("Wave214 register must contain 2500 unique IDs")
    def write_register() -> None:
        with REGISTER.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(merged)
    write_register()
    register_summary = {"schema_version": 1, "wave": "wave214", "input_records": {"wave212_processed": 2000, "wave212_priority": 500}, "input_sha256": {"wave212_processed": sha(PRIOR), "wave212_priority": sha(APPEND)}, "input_overlap_records": 0, "processed_records": 2500, "unique_product_external_ids": 2500, "output_sha256": sha(REGISTER), "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0}
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render(sha(REGISTER))
    artifacts = (REGISTER, REGISTER_SUMMARY, QUEUE, QUEUE_SUMMARY, BATCH, BATCH_SUMMARY)
    first = {path.name: path.read_bytes() for path in artifacts}
    write_register(); REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); render(sha(REGISTER))
    identical = {path.name: first[path.name] == path.read_bytes() for path in artifacts}
    if not all(identical.values()): raise SystemExit(f"non-deterministic rerun: {identical}")
    queue, batch = rows(QUEUE), rows(BATCH)
    queue_ids, batch_ids = {row["product_external_id"] for row in queue}, {row["product_external_id"] for row in batch}
    if len(queue) != len(queue_ids) or len(queue) != 500 or queue_ids & set(merged_ids): raise SystemExit("Wave214 priority no-repeat invariant failed")
    if len(batch) != len(batch_ids) or len(batch) != 500 or batch_ids != queue_ids: raise SystemExit("Wave214 source planner invariant failed")
    queue_summary, batch_summary = json.loads(QUEUE_SUMMARY.read_text(encoding="utf-8")), json.loads(BATCH_SUMMARY.read_text(encoding="utf-8"))
    if batch_summary["automotive_excluded"] != 0 or batch_summary["electronics_excluded"] != 0: raise SystemExit("Wave214 scope exclusion failed")
    verify = {"schema_version": 1, "wave": "wave214", "inputs": {path.name: {"rows": PINS[path][0], "sha256": sha(path)} for path in PINS}, "register": {"rows": 2500, "unique_ids": 2500, "overlap_with_wave212_processed": 0, "output_sha256": sha(REGISTER)}, "priority": {"rows": 500, "unique_ids": 500, "overlap_with_processed_register": 0, "output_sha256": sha(QUEUE)}, "source_planner": {"rows": 500, "overlap_with_processed_register": 0, "automotive_excluded": 0, "electronics_excluded": 0, "output_sha256": sha(BATCH)}, "byte_identical_rerun": identical, "safe_to_apply_records": queue_summary["safe_to_apply_records"], "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0}
    VERIFY.write_text(json.dumps(verify, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"register": 2500, "priority": 500, "batch": 500, "rerun": all(identical.values())}))

if __name__ == "__main__": main()
