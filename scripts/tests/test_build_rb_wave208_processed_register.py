from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave208-processed-register.py"
WAVE174 = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave174.csv"
WAVE205 = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave205.csv"
OUTPUT = ROOT / "docs/audits/generated/rb-b2b-processed-register-wave208.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-b2b-processed-register-wave208.summary.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, ids: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id"])
        writer.writeheader()
        writer.writerows({"product_external_id": value} for value in ids)


def run(tmp_path: Path, first: Path, second: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--wave174", str(first),
            "--wave205", str(second),
            "--output", str(tmp_path / "processed.csv"),
            "--summary", str(tmp_path / "summary.json"),
            "--expected-wave174-sha256", sha(first),
            "--expected-wave205-sha256", sha(second),
            "--expected-each-records", "2",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_rejects_overlap(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    write_csv(first, ["bitrix:1", "bitrix:2"])
    write_csv(second, ["bitrix:2", "bitrix:3"])
    result = run(tmp_path, first, second)
    assert result.returncode != 0
    assert "overlap" in result.stderr


def test_rejects_unpinned_input(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    write_csv(first, ["bitrix:1", "bitrix:2"])
    write_csv(second, ["bitrix:3", "bitrix:4"])
    command = [
        sys.executable,
        str(SCRIPT),
        "--wave174", str(first),
        "--wave205", str(second),
        "--output", str(tmp_path / "processed.csv"),
        "--summary", str(tmp_path / "summary.json"),
        "--expected-wave174-sha256", "0" * 64,
        "--expected-wave205-sha256", sha(second),
        "--expected-each-records", "2",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert "SHA-256 mismatch" in result.stderr


def test_real_processed_register_is_exact_and_pinned() -> None:
    first = read_csv(WAVE174)
    second = read_csv(WAVE205)
    output = read_csv(OUTPUT)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    output_ids = [row["product_external_id"] for row in output]

    assert len(first) == len(second) == 500
    assert len(output) == len(set(output_ids)) == 1000
    assert {row["product_external_id"] for row in first}.isdisjoint(
        row["product_external_id"] for row in second
    )
    assert summary["processed_records"] == 1000
    assert summary["unique_product_external_ids"] == 1000
    assert summary["input_overlap_records"] == 0
    assert summary["output_sha256"] == sha(OUTPUT)
    assert summary["automatic_database_mutations"] == 0
