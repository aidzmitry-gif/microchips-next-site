from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-b2b-priority-queue.py"
WAVE174 = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave174.csv"
WAVE205 = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave205.csv"
WAVE205_SUMMARY = ROOT / "docs/audits/generated/rb-b2b-priority-queue-wave205.summary.json"


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    readiness = tmp_path / "readiness.csv"
    holds = tmp_path / "holds.csv"
    processed = tmp_path / "processed.csv"
    fields = [
        "product_external_id",
        "name",
        "category_external_id",
        "readiness_class",
        "identity_ready",
        "has_applied_description",
        "technical_fact_count",
        "has_displayable_preview_image",
        "has_verified_published_image",
        "manufacturer",
        "sku",
        "mpn",
    ]
    rows = []
    for number in range(1, 5):
        rows.append(
            {
                "product_external_id": f"bitrix:{number}",
                "name": f"Battery MODEL-{number}",
                "category_external_id": "seo:batteries-industrial",
                "readiness_class": "legacy_text_only",
                "identity_ready": "false",
                "has_applied_description": "false",
                "technical_fact_count": "0",
                "has_displayable_preview_image": "false",
                "has_verified_published_image": "false",
                "manufacturer": "",
                "sku": "",
                "mpn": "",
            }
        )
    write_csv(readiness, rows, fields)
    write_csv(holds, [{"product_external_id": "bitrix:1"}], ["product_external_id"])
    write_csv(processed, [{"product_external_id": "bitrix:2"}], ["product_external_id"])
    return readiness, holds, processed


def run_builder(
    tmp_path: Path,
    readiness: Path,
    holds: Path,
    processed: Path,
    *,
    processed_sha: str | None = None,
    processed_records: int = 1,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(readiness),
            "--holds",
            str(holds),
            "--processed",
            str(processed),
            "--output",
            str(tmp_path / "queue.csv"),
            "--summary",
            str(tmp_path / "summary.json"),
            "--expected-input-sha256",
            sha(readiness),
            "--expected-hold-sha256",
            sha(holds),
            "--expected-processed-sha256",
            processed_sha or sha(processed),
            "--expected-processed-records",
            str(processed_records),
            "--expected-records",
            "4",
            "--limit",
            "2",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_excludes_pinned_processed_ids_and_is_deterministic(tmp_path: Path) -> None:
    readiness, holds, processed = fixture(tmp_path)
    first = run_builder(tmp_path, readiness, holds, processed)
    assert first.returncode == 0, first.stderr
    first_queue = (tmp_path / "queue.csv").read_bytes()

    second = run_builder(tmp_path, readiness, holds, processed)
    assert second.returncode == 0, second.stderr
    assert (tmp_path / "queue.csv").read_bytes() == first_queue

    rows = list(csv.DictReader(first_queue.decode("utf-8-sig").splitlines()))
    assert [row["product_external_id"] for row in rows] == ["bitrix:3", "bitrix:4"]
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["processed_records"] == 1
    assert summary["already_processed_skipped"] == 1
    assert summary["eligible_unreviewed_unprocessed"] == 2


def test_rejects_unpinned_or_wrong_processed_input(tmp_path: Path) -> None:
    readiness, holds, processed = fixture(tmp_path)
    result = run_builder(tmp_path, readiness, holds, processed, processed_sha="0" * 64)
    assert result.returncode != 0
    assert "processed exclusion SHA-256" in result.stderr


def test_rejects_duplicate_processed_ids(tmp_path: Path) -> None:
    readiness, holds, processed = fixture(tmp_path)
    write_csv(
        processed,
        [
            {"product_external_id": "bitrix:2"},
            {"product_external_id": "bitrix:2"},
        ],
        ["product_external_id"],
    )
    result = run_builder(
        tmp_path,
        readiness,
        holds,
        processed,
        processed_records=2,
    )
    assert result.returncode != 0
    assert "repeats product_external_id" in result.stderr


def test_rejects_processed_id_absent_from_readiness(tmp_path: Path) -> None:
    readiness, holds, processed = fixture(tmp_path)
    write_csv(processed, [{"product_external_id": "bitrix:999"}], ["product_external_id"])
    result = run_builder(tmp_path, readiness, holds, processed)
    assert result.returncode != 0
    assert "absent from readiness input" in result.stderr


def test_rejects_partial_processed_contract(tmp_path: Path) -> None:
    readiness, holds, processed = fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(readiness),
            "--holds",
            str(holds),
            "--processed",
            str(processed),
            "--output",
            str(tmp_path / "queue.csv"),
            "--summary",
            str(tmp_path / "summary.json"),
            "--expected-input-sha256",
            sha(readiness),
            "--expected-hold-sha256",
            sha(holds),
            "--expected-records",
            "4",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "requires --processed" in result.stderr


def test_rejects_hold_and_processed_overlap(tmp_path: Path) -> None:
    readiness, holds, processed = fixture(tmp_path)
    write_csv(processed, [{"product_external_id": "bitrix:1"}], ["product_external_id"])
    result = run_builder(tmp_path, readiness, holds, processed)
    assert result.returncode != 0
    assert "hold and processed exclusion inputs overlap" in result.stderr


def test_wave205_artifact_is_exactly_500_unique_and_disjoint_from_wave174() -> None:
    prior = list(csv.DictReader(WAVE174.read_text(encoding="utf-8-sig").splitlines()))
    current = list(csv.DictReader(WAVE205.read_text(encoding="utf-8-sig").splitlines()))
    prior_ids = {row["product_external_id"] for row in prior}
    current_ids = [row["product_external_id"] for row in current]

    assert len(prior) == 500
    assert len(current) == 500
    assert len(set(current_ids)) == 500
    assert not (set(current_ids) & prior_ids)
    assert all(row["safe_to_apply"] == "false" for row in current)

    summary = json.loads(WAVE205_SUMMARY.read_text(encoding="utf-8"))
    assert summary["processed_records"] == 500
    assert summary["already_processed_skipped"] == 500
    assert summary["selected_records"] == 500
    assert summary["processed_sha256"] == sha(WAVE174)
    assert summary["output_sha256"] == sha(WAVE205)
