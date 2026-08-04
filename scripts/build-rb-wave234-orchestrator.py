#!/usr/bin/env python3
"""Partition the remaining Wave233 B2B identity/media gaps without overlap."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
INPUT = GEN / "rb-wave233-identity-media-gaps.csv"
LANE_A = GEN / "rb-wave234-a-panasonic-mnb.csv"
LANE_B = GEN / "rb-wave234-b-apc-enersys.csv"
LANE_C = GEN / "rb-wave234-c-remaining-ups-batteries.csv"
PRIOR = GEN / "rb-wave234-prior-reviewed-wave233.csv"
NON_B2B = GEN / "rb-wave234-non-b2b-exclusions.csv"
VERIFY = GEN / "rb-wave234-orchestration.verification.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave234-orchestration.md"

INPUT_SHA256 = "20ce250c041b5c54441d0dad2d6d76c80b7936c82dcf8bbe76e537641f4eba68"
PRIOR_PREFIXES = ("Delta", "Fiamm", "Leoch", "Marathon", "CSB")
EXPECTED = {"input": 611, "b2b": 553, "prior": 389, "A": 56, "B": 34, "C": 74, "non_b2b": 58}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def has_prefix(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(re.match(rf"^Аккумулятор\s+{re.escape(prefix)}(?:\s|$)", name, re.I) for prefix in prefixes)


def build() -> dict[str, object]:
    if sha256(INPUT) != INPUT_SHA256:
        raise SystemExit("Wave233 gap input pin drift")
    fields, rows = read_rows(INPUT)
    ids = [row["external_id"] for row in rows]
    if len(rows) != EXPECTED["input"] or len(ids) != len(set(ids)) or any(not value for value in ids):
        raise SystemExit("Wave233 gap count/identity drift")
    b2b = [row for row in rows if row["category_external_id"] == "seo:batteries-ups"]
    non_b2b = [row for row in rows if row["category_external_id"] != "seo:batteries-ups"]
    prior = [row for row in b2b if has_prefix(row["name"], PRIOR_PREFIXES)]
    remaining = [row for row in b2b if row not in prior]
    lane_a = [row for row in remaining if has_prefix(row["name"], ("Panasonic", "MNB"))]
    lane_b = [
        row for row in remaining
        if has_prefix(row["name"], ("APC", "EnerSys"))
        or re.match(r"^Аккумулятор\s+APCRBC[0-9]", row["name"], re.I)
    ]
    selected = {row["external_id"] for row in lane_a + lane_b}
    lane_c = [row for row in remaining if row["external_id"] not in selected]
    partitions = {"prior": prior, "A": lane_a, "B": lane_b, "C": lane_c, "non_b2b": non_b2b}
    counts = {key: len(value) for key, value in partitions.items()}
    for key, expected in EXPECTED.items():
        actual = len(rows) if key == "input" else len(b2b) if key == "b2b" else counts[key]
        if actual != expected:
            raise SystemExit(f"Wave234 {key} partition drift: {actual} != {expected}")
    id_sets = {key: {row["external_id"] for row in value} for key, value in partitions.items()}
    keys = list(id_sets)
    if any(id_sets[left] & id_sets[right] for index, left in enumerate(keys) for right in keys[index + 1 :]):
        raise SystemExit("Wave234 partition overlap")
    if set().union(*id_sets.values()) != set(ids):
        raise SystemExit("Wave234 did not cover every Wave233 gap")
    if any(row["category_external_id"] != "seo:batteries-ups" for row in lane_a + lane_b + lane_c):
        raise SystemExit("Wave234 research lane contains a non-B2B category")

    destinations = {LANE_A: lane_a, LANE_B: lane_b, LANE_C: lane_c, PRIOR: prior, NON_B2B: non_b2b}
    for path, data in destinations.items():
        write_rows(path, fields, data)
    first = {path: path.read_bytes() for path in destinations}
    for path, data in destinations.items():
        write_rows(path, fields, data)
    if any(path.read_bytes() != first[path] for path in destinations):
        raise SystemExit("Wave234 output is not byte deterministic")

    result = {
        "schema_version": 1,
        "wave": "wave234_orchestration",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(rows), "unique_ids": len(ids)},
        "partition": {
            "b2b_ups_batteries": len(b2b),
            "prior_wave233_reviewed": len(prior),
            "lane_a_panasonic_mnb": len(lane_a),
            "lane_b_apc_enersys": len(lane_b),
            "lane_c_remaining": len(lane_c),
            "non_b2b_excluded": len(non_b2b),
            "overlap_ids": [],
            "unpartitioned_ids": [],
        },
        "lane_c_prefix_counts": dict(sorted(Counter(row["name"].split()[1] if len(row["name"].split()) > 1 else "(other)" for row in lane_c).items())),
        "outputs": {path.relative_to(ROOT).as_posix(): {"rows": len(data), "sha256": sha256(path)} for path, data in destinations.items()},
        "policy": {"database_queries": 0, "database_mutations": 0, "network_requests": 0, "commercial_changes": 0, "publication_changes": 0},
    }
    VERIFY.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave234 orchestration\n\n"
        "The pinned 611-row Wave233 identity/media-gap registry is partitioned without overlap. "
        "The 389 Delta/Fiamm/Leoch/Marathon/CSB rows already reviewed in Wave233 are excluded from repeated research. "
        "The remaining 164 B2B UPS-battery cards are split into lanes A=56 Panasonic/MNB, B=34 APC/EnerSys and C=74 residual manufacturers. "
        "Fifty-eight non-B2B rows remain outside this cycle. No database, network, commercial or publication action is performed by this orchestrator.\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
