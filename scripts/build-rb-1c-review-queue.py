#!/usr/bin/env python3
"""Build a conservative RB 1C-to-Bitrix review queue.

This is a read-only gate over the matcher output. It does not approve products,
publish catalog entries, or call the importer. Every selected row remains a
human-review candidate.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence


RULE_VERSION = "rb-1c-review-v1"
REQUIRED_COLUMNS = (
    "Bitrix ID",
    "1С-код",
    "brand_ok",
    "confidence",
    "method",
)
QUEUE_COLUMNS = ("queue_status", "review_required", "selection_rule_version")
EXCLUSION_COLUMNS = ("exclusion_reasons", "selection_rule_version")


class GateError(RuntimeError):
    """Raised when inputs or checked artifacts violate the gate contract."""


def read_csv_bytes(
    content: bytes, source_name: str
) -> tuple[list[str], list[dict[str, str]]]:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise GateError(f"Input CSV is not UTF-8: {source_name}") from error
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    fieldnames = reader.fieldnames or []
    if len(fieldnames) != len(set(fieldnames)):
        raise GateError(f"Duplicate column names in {source_name}")
    missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
    if missing:
        raise GateError(
            f"Missing required columns in {source_name}: {', '.join(missing)}"
        )
    rows = [
        {key: (value or "").strip() for key, value in row.items()}
        for row in reader
    ]
    return fieldnames, rows


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        return read_csv_bytes(path.read_bytes(), str(path))
    except FileNotFoundError as error:
        raise GateError(f"Input CSV not found: {path}") from error


def is_exact_confidence(value: str) -> bool:
    try:
        return Decimal(value.strip().replace(",", ".")) == Decimal("0.95")
    except (InvalidOperation, AttributeError):
        return False


def evaluate_rows(
    fieldnames: Sequence[str], rows: Sequence[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], Counter[str]]:
    """Return review candidates, exclusions, and exclusion-reason counts."""

    one_c_to_bitrix: dict[str, set[str]] = defaultdict(set)
    bitrix_to_one_c: dict[str, set[str]] = defaultdict(set)
    pair_counts: Counter[tuple[str, str]] = Counter()

    for row in rows:
        bitrix_id = row["Bitrix ID"]
        one_c_code = row["1С-код"]
        if bitrix_id and one_c_code:
            one_c_to_bitrix[one_c_code].add(bitrix_id)
            bitrix_to_one_c[bitrix_id].add(one_c_code)
            pair_counts[(bitrix_id, one_c_code)] += 1

    candidates: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
    reason_counts: Counter[str] = Counter()

    for row in rows:
        bitrix_id = row["Bitrix ID"]
        one_c_code = row["1С-код"]
        reasons: list[str] = []

        if not bitrix_id:
            reasons.append("missing_bitrix_id")
        if not one_c_code:
            reasons.append("missing_1c_code")
        if not is_exact_confidence(row["confidence"]):
            reasons.append("confidence_not_0_95")
        if row["brand_ok"].casefold() != "yes":
            reasons.append("brand_not_confirmed")
        if "generic" in row["method"].casefold():
            reasons.append("generic_match_method")

        if bitrix_id and one_c_code:
            if len(one_c_to_bitrix[one_c_code]) != 1:
                reasons.append("one_c_code_maps_multiple_bitrix_ids")
            # The source currently has one row per site item. Keep this guard so
            # a future matcher cannot place one Bitrix card in the queue twice.
            if len(bitrix_to_one_c[bitrix_id]) != 1:
                reasons.append("bitrix_id_maps_multiple_1c_codes")
            if pair_counts[(bitrix_id, one_c_code)] != 1:
                reasons.append("duplicate_source_pair")

        if reasons:
            excluded = {name: row.get(name, "") for name in fieldnames}
            excluded["exclusion_reasons"] = ";".join(reasons)
            excluded["selection_rule_version"] = RULE_VERSION
            exclusions.append(excluded)
            reason_counts.update(reasons)
            continue

        candidate = {name: row.get(name, "") for name in fieldnames}
        candidate["queue_status"] = "review_candidate"
        candidate["review_required"] = "yes"
        candidate["selection_rule_version"] = RULE_VERSION
        candidates.append(candidate)

    return candidates, exclusions, reason_counts


def render_csv(fieldnames: Iterable[str], rows: Iterable[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fieldnames), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def build_artifacts(
    fieldnames: Sequence[str], rows: Sequence[dict[str, str]]
) -> tuple[bytes, bytes, dict[str, object]]:
    overlap = set(fieldnames) & (set(QUEUE_COLUMNS) | set(EXCLUSION_COLUMNS))
    if overlap:
        raise GateError(
            "Input already contains gate-owned columns: " + ", ".join(sorted(overlap))
        )

    candidates, exclusions, reason_counts = evaluate_rows(fieldnames, rows)
    queue_bytes = render_csv([*fieldnames, *QUEUE_COLUMNS], candidates)
    exclusion_bytes = render_csv([*fieldnames, *EXCLUSION_COLUMNS], exclusions)
    summary: dict[str, object] = {
        "selection_rule_version": RULE_VERSION,
        "source_rows": len(rows),
        "review_candidates": len(candidates),
        "excluded_rows": len(exclusions),
        "exclusion_reason_counts": dict(sorted(reason_counts.items())),
        "status": "review_candidates_only",
    }
    return queue_bytes, exclusion_bytes, summary


def expected_artifacts(
    input_path: Path,
) -> tuple[bytes, bytes, dict[str, object]]:
    fieldnames, rows = read_csv(input_path)
    return build_artifacts(fieldnames, rows)


def assert_artifact_content(
    actual: bytes | None, expected: bytes, path: Path
) -> None:
    if actual is None:
        raise GateError(f"Expected artifact is missing: {path}")
    if actual != expected:
        raise GateError(f"Artifact is stale or was edited manually: {path}")


def write_or_check(path: Path, expected: bytes, check: bool) -> None:
    if check:
        assert_artifact_content(path.read_bytes() if path.exists() else None, expected, path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)


def run_gate(input_path: Path, queue_path: Path, exclusions_path: Path, check: bool) -> dict[str, object]:
    queue_bytes, exclusions_bytes, summary = expected_artifacts(input_path)
    write_or_check(queue_path, queue_bytes, check)
    write_or_check(exclusions_path, exclusions_bytes, check)
    summary["mode"] = "check" if check else "build"
    summary["queue_csv"] = str(queue_path)
    summary["exclusions_csv"] = str(exclusions_path)
    return summary


def render_synthetic_csv(rows: Sequence[dict[str, str]]) -> bytes:
    fieldnames = [
        "Bitrix ID",
        "Название сайта",
        "1С-код",
        "brand_ok",
        "confidence",
        "method",
    ]
    return render_csv(fieldnames, rows)


def run_self_test() -> None:
    base = {"Название сайта": "Synthetic item"}

    def row(bitrix_id: str, code: str, brand: str = "yes", confidence: str = "0.95", method: str = "sig+brand") -> dict[str, str]:
        return {
            **base,
            "Bitrix ID": bitrix_id,
            "1С-код": code,
            "brand_ok": brand,
            "confidence": confidence,
            "method": method,
        }

    rows = [
        row("101", "C-1"),
        row("102", "C-2"),
        row("103", "C-2"),
        row("104", "C-3", method="sig+brand+generic"),
        row("105", "C-4", confidence="0.85"),
        row("106", "C-5", brand="no"),
        row("", "C-6"),
        row("107", ""),
        row("108", "C-8"),
        row("108", "C-8"),
        row("109", "C-9"),
        row("109", "C-10"),
    ]

    source_bytes = render_synthetic_csv(rows)
    fieldnames, parsed_rows = read_csv_bytes(source_bytes, "synthetic.csv")
    queue_bytes, exclusions_bytes, summary = build_artifacts(fieldnames, parsed_rows)
    assert summary["source_rows"] == 12
    assert summary["review_candidates"] == 1
    assert summary["excluded_rows"] == 11

    _, candidate_rows = read_csv_bytes(queue_bytes, "synthetic-queue.csv")
    assert [item["Bitrix ID"] for item in candidate_rows] == ["101"]
    assert candidate_rows[0]["queue_status"] == "review_candidate"
    assert candidate_rows[0]["review_required"] == "yes"

    _, excluded_rows = read_csv_bytes(exclusions_bytes, "synthetic-exclusions.csv")
    reasons_by_id: dict[str, list[str]] = defaultdict(list)
    for item in excluded_rows:
        reasons_by_id[item["Bitrix ID"]].append(item["exclusion_reasons"])
    assert all("one_c_code_maps_multiple_bitrix_ids" in reason for reason in reasons_by_id["102"] + reasons_by_id["103"])
    assert "generic_match_method" in reasons_by_id["104"][0]
    assert "confidence_not_0_95" in reasons_by_id["105"][0]
    assert "brand_not_confirmed" in reasons_by_id["106"][0]
    assert "missing_bitrix_id" in reasons_by_id[""][0]
    assert "missing_1c_code" in reasons_by_id["107"][0]
    assert all("duplicate_source_pair" in reason for reason in reasons_by_id["108"])
    assert all("bitrix_id_maps_multiple_1c_codes" in reason for reason in reasons_by_id["109"])

    assert_artifact_content(queue_bytes, queue_bytes, Path("synthetic-queue.csv"))
    try:
        assert_artifact_content(
            queue_bytes + b"stale", queue_bytes, Path("synthetic-queue.csv")
        )
    except GateError as error:
        assert "stale or was edited manually" in str(error)
    else:
        raise AssertionError("check mode did not detect a stale artifact")

    print("self-test: PASS (strict selection, collision rejection, stale-artifact check)")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    imports = repo_root / "docs" / "imports"
    parser = argparse.ArgumentParser(
        description="Build/check a conservative 1C-to-Bitrix human-review queue."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=imports / "rb-1c-match-v2-matched.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=imports / "rb-1c-review-candidates.csv",
    )
    parser.add_argument(
        "--exclusions",
        type=Path,
        default=imports / "rb-1c-review-exclusions.csv",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated artifacts are missing, stale, or manually edited.",
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.self_test:
            run_self_test()
            return 0
        summary = run_gate(args.input, args.output, args.exclusions, args.check)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("NOTICE: output rows are review candidates, not verified or approved products.")
        return 0
    except (GateError, AssertionError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
