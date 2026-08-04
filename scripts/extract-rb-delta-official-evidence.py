#!/usr/bin/env python3
"""Extract fail-closed exact-model Delta evidence from saved first-party pages.

The acquisition step is intentionally separate: ``--source-pages`` points to
locally saved HTML files. This keeps the extractor reproducible and makes the
URL/SHA-256 evidence boundary auditable. It never writes to the application
database and never turns a candidate into an apply-safe record.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

HOSTS = {"delta-batt.com", "www.delta-batt.com"}
PUBLISHER = "DELTA Battery / ENERGON"
PRODUCT_PAGE_PATH = re.compile(r"/products/[a-z0-9][a-z0-9._-]*/?", re.I)
# Numeric codepoints avoid Windows console/source-encoding corruption.
def letters(*codepoints: int) -> str:
    return "".join(chr(point) for point in codepoints)


VOLTAGE_LABEL = letters(0x041D, 0x0430, 0x043F, 0x0440, 0x044F, 0x0436, 0x0435, 0x043D, 0x0438, 0x0435)
CAPACITY_LABEL = "(?:" + letters(0x0415, 0x043C, 0x043A, 0x043E, 0x0441, 0x0442, 0x044C) + "|" + letters(0x0401, 0x043C, 0x043A, 0x043E, 0x0441, 0x0442, 0x044C) + ")"
# Delta's Russian product cards usually render units before the value
# (``Напряжение, В 12`` / ``Емкость, Ач 17``).  The unit can also follow the
# value in saved first-party pages, so retain only values in the corresponding
# labelled field and collect every distinct value before accepting a page.
VOLTAGE = re.compile(
    rf"{VOLTAGE_LABEL}[^0-9]{{0,40}}(?:{letters(0x0412)}[^0-9]{{0,20}})?(\d+(?:[.,]\d+)?)(?:\s*{letters(0x0412)}\b)?",
    re.I,
)
CAPACITY = re.compile(
    rf"{CAPACITY_LABEL}[^0-9]{{0,40}}(?:{letters(0x0410, 0x0447)}[^0-9]{{0,20}})?(\d+(?:[.,]\d+)?)(?:\s*{letters(0x0410, 0x0447)}\b)?",
    re.I,
)


def model_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    result: list[str] = []
    for index, char in enumerate(normalized):
        if "a" <= char <= "z" or "0" <= char <= "9":
            result.append(char)
        elif (
            char in {".", ","}
            and index > 0
            and index + 1 < len(normalized)
            and normalized[index - 1].isdigit()
            and normalized[index + 1].isdigit()
        ):
            result.append(".")
    return "".join(result)


def unique_h1_model(raw: str) -> str:
    values = []
    for inner in re.findall(r"<h1\b[^>]*>(.*?)</h1>", raw, flags=re.I | re.S):
        value = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        value = re.sub(r"^DELTA\s+", "", value, flags=re.I)
        if value and value not in values:
            values.append(value)
    if len(values) != 1:
        raise ValueError("expected exactly one unique product H1")
    return values[0]


def primary_product_text(raw: str) -> str:
    start = raw.find('<div class="product-page__info"')
    if start < 0:
        raise ValueError("primary product info container is missing")
    end = raw.find("Показать все характеристики", start)
    if end < 0:
        raise ValueError("primary product properties boundary is missing")
    segment = raw[start:end]
    if '<div class="product-page__info"' in raw[end:]:
        raise ValueError("multiple primary product info containers")
    return text_from_html(segment)


def text_from_html(raw: str) -> str:
    raw = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", raw, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def unique_values(pattern: re.Pattern[str], text: str) -> list[str]:
    values = []
    for value in pattern.findall(text):
        value = value.replace(",", ".")
        if value not in values:
            values.append(value)
    return values


def load(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        return list(reader)


def build(candidates_path: Path, source_pages_path: Path, output: Path, summary_path: Path, expected_candidates: int) -> dict[str, object]:
    candidates = load(candidates_path, {"external_id", "model_candidate_unverified", "safe_to_apply"})
    if len(candidates) != expected_candidates or len({row["external_id"] for row in candidates}) != len(candidates):
        raise ValueError("candidate count or external_id uniqueness mismatch")
    pages = load(source_pages_path, {"external_id", "model", "page_model", "source_url", "html_path", "source_sha256"})
    candidate_by_key = {model_key(row["model_candidate_unverified"]): row for row in candidates}
    if len(candidate_by_key) != len(candidates):
        raise ValueError("candidate model keys are not unique")
    results: dict[str, dict[str, str]] = {}
    rejected = Counter()
    for page in pages:
        key = model_key(page["model"])
        if key not in candidate_by_key:
            rejected["not_a_wave198_candidate"] += 1; continue
        if key in results:
            rejected["duplicate_source_page_for_model"] += 1; continue
        parsed = urlparse(page["source_url"])
        try:
            port = parsed.port
        except ValueError:
            rejected["non_first_party_url"] += 1; continue
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").casefold() not in HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or port not in {None, 443}
            or parsed.query
            or parsed.fragment
            or PRODUCT_PAGE_PATH.fullmatch(parsed.path) is None
        ):
            rejected["non_first_party_url"] += 1; continue
        file_path = Path(page["html_path"])
        if not file_path.is_file():
            rejected["missing_saved_page"] += 1; continue
        raw = file_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != page["source_sha256"].casefold():
            rejected["source_sha256_mismatch"] += 1; continue
        try:
            decoded = raw.decode("utf-8", errors="strict")
            h1_model = unique_h1_model(decoded)
            text = primary_product_text(decoded)
        except (UnicodeDecodeError, ValueError):
            rejected["invalid_or_non_product_page"] += 1; continue
        model = candidate_by_key[key]["model_candidate_unverified"]
        if page["external_id"] != candidate_by_key[key]["external_id"] or model_key(page["page_model"]) != key or model_key(h1_model) != key:
            rejected["exact_model_not_in_page_h1"] += 1; continue
        volts, capacities = unique_values(VOLTAGE, text), unique_values(CAPACITY, text)
        if len(volts) != 1 or len(capacities) != 1:
            rejected["ambiguous_or_missing_voltage_capacity"] += 1; continue
        results[key] = {
            "external_id": candidate_by_key[key]["external_id"], "model": model,
            "source_url": page["source_url"], "source_snapshot_path": str(file_path.resolve()),
            "source_sha256": hashlib.sha256(raw).hexdigest(), "content_model_key": key,
            "voltage_v": volts[0], "capacity_ah": capacities[0],
            "evidence_kind": "exact_product_page", "publisher": PUBLISHER, "safe_to_apply": "false",
        }
    output_rows = [results[key] for key in sorted(results)]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "external_id", "model", "source_url", "source_snapshot_path", "source_sha256", "content_model_key",
            "voltage_v", "capacity_ah", "evidence_kind", "publisher", "safe_to_apply",
        ])
        writer.writeheader(); writer.writerows(output_rows)
    summary = {"candidate_path": str(candidates_path), "candidate_sha256": hashlib.sha256(candidates_path.read_bytes()).hexdigest(), "source_pages_path": str(source_pages_path), "source_pages_sha256": hashlib.sha256(source_pages_path.read_bytes()).hexdigest(), "output_path": str(output), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "candidate_records": len(candidates), "source_page_rows": len(pages), "exact_evidence_records": len(output_rows), "uncovered_candidates": len(candidates) - len(output_rows), "rejected_source_pages": dict(sorted(rejected.items())), "automatic_database_mutations": 0, "safe_to_apply_records": 0}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True); parser.add_argument("--source-pages", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--summary", type=Path, required=True); parser.add_argument("--expected-candidates", type=int, default=130)
    args = parser.parse_args()
    print(json.dumps(build(args.candidates, args.source_pages, args.output, args.summary, args.expected_candidates), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
