#!/usr/bin/env python3
"""Materialize the deterministic Wave216 no-repeat RB B2B research queue.

Wave216 treats the Wave214 2,500-card register plus the three disjoint
Wave215 ledgers as the authoritative 3,000-card processed set.  It is local
planning only: no web request, database query, or database mutation occurs.
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
PROCESSED_2500 = GEN / "rb-b2b-processed-register-wave214.csv"
WAVE215_A = GEN / "rb-wave215a-power-evidence.csv"
WAVE215_B = GEN / "rb-wave215b-traction-evidence.csv"
WAVE215_C = GEN / "rb-wave215c-medical-ups-evidence.csv"
READINESS = GEN / "rb-full-content-readiness-wave172-after.csv"
HOLDS = GEN / "rb-known-hold-products-wave172-cumulative.csv"
REGISTER = GEN / "rb-b2b-processed-register-wave216.csv"
REGISTER_SUMMARY = GEN / "rb-b2b-processed-register-wave216.summary.json"
QUEUE = GEN / "rb-b2b-priority-queue-wave216.csv"
QUEUE_SUMMARY = GEN / "rb-b2b-priority-queue-wave216.summary.json"
BATCH = GEN / "rb-b2b-next-source-batch-wave216.csv"
BATCH_SUMMARY = GEN / "rb-b2b-next-source-batch-wave216.summary.json"
VERIFY = GEN / "rb-b2b-wave216.verification.json"
REPORT = ROOT / "docs/audits/2026-07-29-wave216-no-repeat-queue.md"
PRIORITY = ROOT / "scripts/build-rb-b2b-priority-queue.py"
PLANNER = ROOT / "scripts/build-rb-b2b-next-source-batch.py"

PINS = {
    PROCESSED_2500: (2500, "f24d930d1cd500a097fda112eca026efbf25fdcaaead2f03bdc22139040eadaa"),
    WAVE215_A: (359, "656c0393223afe37f9f633bbaa8aa6e4429a585a25a9132ee3a40e3b58becbae"),
    WAVE215_B: (115, "a3dc3df4f9953c024410b21aeed2ee1cd955292c2b4440adc4b8f4bffccfb140"),
    WAVE215_C: (26, "122ff2d6298c62ffbbb9f8c49734196a848415b4347ce69ba49962928d24e5fd"),
    READINESS: (16415, "a9f683f30ee06adc5cad46a545a4266e74c5175c1244f5a3431b290dcdaa8493"),
    HOLDS: (3003, "a01bc64f7c3aedf025e50b22de0988ff3221b6cf957c654ea7396268a954ab7f"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pin(path: Path) -> list[dict[str, str]]:
    data = rows(path)
    expected_rows, expected_sha = PINS[path]
    ids = [row.get("product_external_id", "") for row in data]
    if len(data) != expected_rows or sha(path) != expected_sha or not all(ids) or len(ids) != len(set(ids)):
        raise SystemExit(f"pinned input drift: {path.name}")
    return data


def invoke(args: list[str]) -> None:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stderr or result.stdout)


def write_register(processed: list[tuple[str, str, str]]) -> None:
    with REGISTER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "processed_wave", "source_artifact"], lineterminator="\n")
        writer.writeheader()
        writer.writerows({"product_external_id": external_id, "processed_wave": wave, "source_artifact": artifact} for external_id, wave, artifact in processed)


def render(register_sha: str) -> None:
    invoke([
        sys.executable, str(PRIORITY), "--input", str(READINESS), "--holds", str(HOLDS), "--processed", str(REGISTER),
        "--output", str(QUEUE), "--summary", str(QUEUE_SUMMARY), "--expected-input-sha256", PINS[READINESS][1],
        "--expected-hold-sha256", PINS[HOLDS][1], "--expected-processed-sha256", register_sha,
        "--expected-records", "16415", "--expected-processed-records", "3000", "--limit", "500",
    ])
    invoke([
        sys.executable, str(PLANNER), "--readiness", str(READINESS), "--processed", str(REGISTER), "--holds", str(HOLDS),
        "--priority-script", str(PRIORITY), "--output", str(BATCH), "--summary", str(BATCH_SUMMARY),
        "--expected-readiness-sha256", PINS[READINESS][1], "--expected-processed-sha256", register_sha,
        "--expected-holds-sha256", PINS[HOLDS][1], "--expected-readiness-records", "16415",
        "--expected-processed-records", "3000", "--limit", "500",
    ])


def write_report(queue_summary: dict, verification: dict) -> None:
    lines = [
        "# Wave216 no-repeat queue", "",
        "Wave216 deterministically builds the next 500-card RB B2B research queue from the same 3,894-card incomplete, non-held research universe.",
        "The authoritative processed set is exactly 3,000 unique cards: 2,500 from the prior aggregate register and the disjoint 359/115/26 Wave215 A/B/C ledgers.", "",
        "## Guards", "",
        "- Processed IDs are unique and all belong to the current incomplete, non-held B2B universe.",
        "- Queue and source batch each contain 500 unique IDs, equal to one another, and have zero overlap with the processed register.",
        "- Automotive and electronic-component exclusions are both zero for the selected research batch.",
        "- All selected rows retain `safe_to_apply=false`; this planner makes no web request, database query, or database mutation.", "",
        "## Counts", "",
        f"- Research universe: {verification['research_universe']['rows']}.",
        f"- Remaining after processed exclusion: {verification['research_universe']['eligible_after_processed']}.",
        f"- Queue categories: {queue_summary['category_counts']}.",
        f"- Byte-identical second rendering: {all(verification['byte_identical_rerun'].values())}.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    previous, wave215a, wave215b, wave215c = (pin(path) for path in (PROCESSED_2500, WAVE215_A, WAVE215_B, WAVE215_C))
    readiness, holds = pin(READINESS), pin(HOLDS)
    prior_ids = {row["product_external_id"] for row in previous}
    wave215_sets = [{row["product_external_id"] for row in rows_} for rows_ in (wave215a, wave215b, wave215c)]
    if any(prior_ids & subset for subset in wave215_sets) or wave215_sets[0] & wave215_sets[1] or wave215_sets[0] & wave215_sets[2] or wave215_sets[1] & wave215_sets[2]:
        raise SystemExit("processed lineage overlap")
    processed = ([(row["product_external_id"], "wave207_209_211_213", PROCESSED_2500.name) for row in previous]
                 + [(row["product_external_id"], "wave215a", WAVE215_A.name) for row in wave215a]
                 + [(row["product_external_id"], "wave215b", WAVE215_B.name) for row in wave215b]
                 + [(row["product_external_id"], "wave215c", WAVE215_C.name) for row in wave215c])
    processed_ids = [row[0] for row in processed]
    if len(processed) != 3000 or len(set(processed_ids)) != 3000:
        raise SystemExit("Wave216 register must contain exactly 3000 unique IDs")

    hold_ids = {row["product_external_id"] for row in holds}
    # Same research universe as the previous queue: incomplete B2B cards with
    # cumulative holds removed.  Its fixed size proves no quiet scope drift.
    import importlib.util
    spec = importlib.util.spec_from_file_location("wave216_priority", PRIORITY)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load priority rules")
    priority = importlib.util.module_from_spec(spec); spec.loader.exec_module(priority)
    incomplete = {row["product_external_id"] for row in readiness if row.get("category_external_id") in priority.B2B_CATEGORY_PRIORITY and row.get("readiness_class") != "strict_content_ready"}
    universe = incomplete - hold_ids
    if len(incomplete) != 3903 or len(universe) != 3894 or not set(processed_ids) <= universe:
        raise SystemExit("Wave216 3894-card research universe drift")
    if len(universe - set(processed_ids)) != 894:
        raise SystemExit("Wave216 eligible research-universe count drift")

    register_summary = {
        "schema_version": 1, "wave": "wave216", "processed_records": 3000, "unique_product_external_ids": 3000,
        "lineage": {"wave207_209_211_213_aggregate": 2500, "wave215a": 359, "wave215b": 115, "wave215c": 26, "wave215_disjoint_union": 500, "lineage_overlap_records": 0},
        "input_sha256": {path.name: sha(path) for path in (PROCESSED_2500, WAVE215_A, WAVE215_B, WAVE215_C)},
        "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0,
    }
    write_register(processed)
    register_summary["output_sha256"] = sha(REGISTER)
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render(sha(REGISTER))
    artifacts = (REGISTER, REGISTER_SUMMARY, QUEUE, QUEUE_SUMMARY, BATCH, BATCH_SUMMARY)
    first = {path.name: path.read_bytes() for path in artifacts}
    write_register(processed)
    REGISTER_SUMMARY.write_text(json.dumps(register_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render(sha(REGISTER))
    identical = {path.name: first[path.name] == path.read_bytes() for path in artifacts}
    if not all(identical.values()):
        raise SystemExit(f"non-deterministic rerun: {identical}")
    queue, batch = rows(QUEUE), rows(BATCH)
    queue_ids, batch_ids = {row["product_external_id"] for row in queue}, {row["product_external_id"] for row in batch}
    if len(queue) != len(queue_ids) or len(queue) != 500 or queue_ids & set(processed_ids):
        raise SystemExit("Wave216 priority no-repeat invariant failed")
    if len(batch) != len(batch_ids) or len(batch) != 500 or batch_ids != queue_ids:
        raise SystemExit("Wave216 source planner invariant failed")
    queue_summary, batch_summary = json.loads(QUEUE_SUMMARY.read_text(encoding="utf-8")), json.loads(BATCH_SUMMARY.read_text(encoding="utf-8"))
    if batch_summary["automotive_excluded"] != 0 or batch_summary["electronics_excluded"] != 0 or queue_summary["safe_to_apply_records"] != 0:
        raise SystemExit("Wave216 scope/safety invariant failed")
    verification = {
        "schema_version": 1, "wave": "wave216", "inputs": {path.name: {"rows": PINS[path][0], "sha256": sha(path)} for path in PINS},
        "research_universe": {"incomplete_b2b_rows": 3903, "hold_rows_in_universe": 9, "rows": 3894, "processed_rows": 3000, "eligible_after_processed": 894},
        "register": {"rows": 3000, "unique_ids": 3000, "overlap_with_wave215": 0, "output_sha256": sha(REGISTER)},
        "priority": {"rows": 500, "unique_ids": 500, "overlap_with_processed_register": 0, "output_sha256": sha(QUEUE)},
        "source_planner": {"rows": 500, "overlap_with_processed_register": 0, "automotive_excluded": 0, "electronics_excluded": 0, "output_sha256": sha(BATCH)},
        "byte_identical_rerun": identical, "safe_to_apply_records": queue_summary["safe_to_apply_records"],
        "automatic_web_requests": 0, "automatic_database_queries": 0, "automatic_database_mutations": 0,
    }
    VERIFY.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(queue_summary, verification)
    print(json.dumps({"register": 3000, "research_universe": 3894, "priority": 500, "batch": 500, "rerun": all(identical.values())}))


if __name__ == "__main__":
    main()
