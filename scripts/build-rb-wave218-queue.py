#!/usr/bin/env python3
"""Materialize Wave218's deterministic final no-repeat research queue.

Local-only planning: Wave216's 3,000 IDs plus the disjoint Wave217 A/B/C
evidence ledgers form a 3,500-ID register.  The fixed 3,894-card research
universe consequently has exactly 394 remaining cards.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
PROCESSED = GEN / "rb-b2b-processed-register-wave216.csv"
WAVE217_A = GEN / "rb-wave217a-unresolved-evidence.csv"
WAVE217_B = GEN / "rb-wave217b-devices-evidence.csv"
WAVE217_C = GEN / "rb-wave217c-replacement-radio-industrial-evidence.csv"
READINESS = GEN / "rb-full-content-readiness-wave172-after.csv"
HOLDS = GEN / "rb-known-hold-products-wave172-cumulative.csv"
REGISTER = GEN / "rb-b2b-processed-register-wave218.csv"
REGISTER_SUMMARY = GEN / "rb-b2b-processed-register-wave218.summary.json"
QUEUE = GEN / "rb-b2b-priority-queue-wave218.csv"
QUEUE_SUMMARY = GEN / "rb-b2b-priority-queue-wave218.summary.json"
BATCH = GEN / "rb-b2b-next-source-batch-wave218.csv"
BATCH_SUMMARY = GEN / "rb-b2b-next-source-batch-wave218.summary.json"
VERIFY = GEN / "rb-b2b-wave218.verification.json"
REPORT = ROOT / "docs/audits/2026-07-29-wave218-no-repeat-queue.md"
PRIORITY = ROOT / "scripts/build-rb-b2b-priority-queue.py"
PLANNER = ROOT / "scripts/build-rb-b2b-next-source-batch.py"
PINS = {
    PROCESSED: (3000, "b46c8375d4cbc63d0fa4e9be5564e278b4875ac96106a0260d036d3d9a668c71"),
    WAVE217_A: (395, "9124e384c1eb4e45f270dc4901566583bd4e246420cb6a251c2f9bcbbf9d009f"),
    WAVE217_B: (56, "51d31be9f423c95d21f0dd6b7aecac659733947b0f92f0045ff6021da2d46abe"),
    WAVE217_C: (49, "27c704b541a753f89e4842aae21458b564426dfbd8dd18ecf54d4050face500c"),
    READINESS: (16415, "a9f683f30ee06adc5cad46a545a4266e74c5175c1244f5a3431b290dcdaa8493"),
    HOLDS: (3003, "a01bc64f7c3aedf025e50b22de0988ff3221b6cf957c654ea7396268a954ab7f"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pin(path: Path) -> list[dict[str, str]]:
    data = rows(path); count, digest = PINS[path]
    ids = [row.get("product_external_id", "") for row in data]
    if len(data) != count or sha(path) != digest or not all(ids) or len(ids) != len(set(ids)):
        raise SystemExit(f"pinned input drift: {path.name}")
    return data


def invoke(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stderr or result.stdout)


def write_register(entries: list[tuple[str, str, str]]) -> None:
    with REGISTER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "processed_wave", "source_artifact"], lineterminator="\n")
        writer.writeheader()
        writer.writerows({"product_external_id": external_id, "processed_wave": wave, "source_artifact": artifact} for external_id, wave, artifact in entries)


def render(register_hash: str) -> None:
    common = ["--input", str(READINESS), "--holds", str(HOLDS), "--processed", str(REGISTER), "--expected-input-sha256", PINS[READINESS][1], "--expected-hold-sha256", PINS[HOLDS][1], "--expected-processed-sha256", register_hash, "--expected-records", "16415", "--expected-processed-records", "3500", "--limit", "500"]
    invoke([sys.executable, str(PRIORITY), *common, "--output", str(QUEUE), "--summary", str(QUEUE_SUMMARY)])
    invoke([sys.executable, str(PLANNER), "--readiness", str(READINESS), "--processed", str(REGISTER), "--holds", str(HOLDS), "--priority-script", str(PRIORITY), "--output", str(BATCH), "--summary", str(BATCH_SUMMARY), "--expected-readiness-sha256", PINS[READINESS][1], "--expected-processed-sha256", register_hash, "--expected-holds-sha256", PINS[HOLDS][1], "--expected-readiness-records", "16415", "--expected-processed-records", "3500", "--limit", "500"])


def main() -> None:
    previous, wave_a, wave_b, wave_c = (pin(path) for path in (PROCESSED, WAVE217_A, WAVE217_B, WAVE217_C))
    readiness, holds = pin(READINESS), pin(HOLDS)
    sets = [{row["product_external_id"] for row in data} for data in (previous, wave_a, wave_b, wave_c)]
    if any(sets[left] & sets[right] for left in range(4) for right in range(left + 1, 4)):
        raise SystemExit("Wave218 lineage overlap")
    entries = [(row["product_external_id"], "wave216", PROCESSED.name) for row in previous]
    entries += [(row["product_external_id"], "wave217a", WAVE217_A.name) for row in wave_a]
    entries += [(row["product_external_id"], "wave217b", WAVE217_B.name) for row in wave_b]
    entries += [(row["product_external_id"], "wave217c", WAVE217_C.name) for row in wave_c]
    processed_ids = {row[0] for row in entries}
    if len(entries) != 3500 or len(processed_ids) != 3500:
        raise SystemExit("Wave218 register must contain exactly 3500 unique IDs")
    spec = importlib.util.spec_from_file_location("rb_priority", PRIORITY)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load priority rules")
    priority = importlib.util.module_from_spec(spec); spec.loader.exec_module(priority)
    incomplete = {row["product_external_id"] for row in readiness if row.get("category_external_id") in priority.B2B_CATEGORY_PRIORITY and row.get("readiness_class") != "strict_content_ready"}
    hold_ids = {row["product_external_id"] for row in holds}
    universe = incomplete - hold_ids
    if len(incomplete) != 3903 or len(universe) != 3894 or not processed_ids <= universe:
        raise SystemExit("Wave218 research universe drift")
    if len(universe - processed_ids) != 394:
        raise SystemExit("Wave218 must leave exactly 394 eligible cards")
    summary = {"schema_version": 1, "wave": "wave218", "processed_records": 3500, "unique_product_external_ids": 3500,
        "lineage": {"wave216_register": 3000, "wave217a": 395, "wave217b": 56, "wave217c": 49, "wave217_disjoint_union": 500, "lineage_overlap_records": 0},
        "input_sha256": {path.name: sha(path) for path in (PROCESSED, WAVE217_A, WAVE217_B, WAVE217_C)},
        "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0}
    write_register(entries); summary["output_sha256"] = sha(REGISTER)
    REGISTER_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render(sha(REGISTER))
    artifacts = (REGISTER, REGISTER_SUMMARY, QUEUE, QUEUE_SUMMARY, BATCH, BATCH_SUMMARY)
    first = {path.name: path.read_bytes() for path in artifacts}
    write_register(entries); REGISTER_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); render(sha(REGISTER))
    identical = {path.name: first[path.name] == path.read_bytes() for path in artifacts}
    if not all(identical.values()):
        raise SystemExit(f"non-deterministic rerun: {identical}")
    queue, batch = rows(QUEUE), rows(BATCH)
    queue_ids, batch_ids = {row["product_external_id"] for row in queue}, {row["product_external_id"] for row in batch}
    if len(queue) != len(queue_ids) or len(queue) != 394 or queue_ids & processed_ids:
        raise SystemExit("Wave218 priority no-repeat invariant failed")
    if len(batch) != len(batch_ids) or len(batch) != 394 or batch_ids != queue_ids:
        raise SystemExit("Wave218 source batch invariant failed")
    queue_summary, batch_summary = json.loads(QUEUE_SUMMARY.read_text(encoding="utf-8")), json.loads(BATCH_SUMMARY.read_text(encoding="utf-8"))
    if batch_summary["automotive_excluded"] or batch_summary["electronics_excluded"] or queue_summary["safe_to_apply_records"]:
        raise SystemExit("Wave218 scope/safety invariant failed")
    verify = {"schema_version": 1, "wave": "wave218", "inputs": {path.name: {"rows": PINS[path][0], "sha256": sha(path)} for path in PINS},
        "research_universe": {"incomplete_b2b_rows": 3903, "hold_rows_in_universe": 9, "rows": 3894, "processed_rows": 3500, "eligible_after_processed": 394},
        "register": {"rows": 3500, "unique_ids": 3500, "overlap_with_wave217": 0, "output_sha256": sha(REGISTER)},
        "priority": {"rows": 394, "unique_ids": 394, "overlap_with_processed_register": 0, "output_sha256": sha(QUEUE)},
        "source_planner": {"rows": 394, "overlap_with_processed_register": 0, "automotive_excluded": 0, "electronics_excluded": 0, "output_sha256": sha(BATCH)},
        "byte_identical_rerun": identical, "safe_to_apply_records": 0, "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0}
    VERIFY.write_text(json.dumps(verify, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("# Wave218 final no-repeat research queue\n\n"
                      "Wave218 extends the 3,000-row Wave216 register with the disjoint Wave217 A/B/C ledgers (395/56/49), producing exactly 3,500 unique processed IDs. The fixed 3,894-card incomplete non-held B2B research universe therefore has 394 remaining records; the requested limit of 500 does not pad or repeat them.\n\n"
                      "The priority queue and source batch each contain the same 394 IDs, have zero processed overlap, exclude automotive and electronic-component scope, and retain `safe_to_apply=false`. Two local renderings are byte-identical. No web, database, or application mutation occurs.\n", encoding="utf-8")
    print(json.dumps({"register": 3500, "research_universe": 3894, "remaining": 394, "rerun": all(identical.values())}))


if __name__ == "__main__":
    main()
