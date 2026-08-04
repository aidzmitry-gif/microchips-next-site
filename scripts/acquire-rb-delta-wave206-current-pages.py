#!/usr/bin/env python3
"""Acquire current first-party Delta pages for the Wave206 Delta partition."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


HOSTS = {"delta-batt.com", "www.delta-batt.com"}
BASE = "https://www.delta-batt.com"
CATALOG = BASE + "/catalog/"
CT_URL = BASE + "/catalog/dlya-mototekhniki/ct/"
HREF = re.compile(r'''href=["']([^"']+)["']''', re.I)
H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")
PROPERTY = r"{label}.*?js-prop-value[^>]*>\s*([0-9]+(?:[.,][0-9]+)?)"


def model_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace(",", ".")
    result: list[str] = []
    for index, char in enumerate(value):
        if "a" <= char <= "z" or "0" <= char <= "9":
            result.append(char)
        elif char == "." and index > 0 and index + 1 < len(value) and value[index - 1].isdigit() and value[index + 1].isdigit():
            result.append(char)
    return "".join(result)


def fetch(url: str, timeout: float) -> tuple[str, bytes]:
    request = Request(url, headers={"User-Agent": "microchips.by catalogue evidence audit/1.0"})
    with urlopen(request, timeout=timeout) as response:
        final = response.geturl()
        parsed = urlparse(final)
        if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in HOSTS:
            raise ValueError(f"redirect outside official Delta host: {final}")
        return final, response.read()


def links(raw: bytes) -> set[str]:
    decoded = raw.decode("utf-8", errors="strict")
    return {html.unescape(value) for value in HREF.findall(decoded)}


def page_model(raw: bytes) -> str:
    decoded = raw.decode("utf-8", errors="strict")
    values = []
    for inner in H1.findall(decoded):
        value = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", inner))).strip()
        value = re.sub(r"^DELTA\s+", "", value, flags=re.I)
        if value and value not in values:
            values.append(value)
    if len(values) != 1:
        raise ValueError(f"expected one unique H1, got {len(values)}")
    return values[0]


def property_value(raw: bytes, label: str) -> str:
    decoded = raw.decode("utf-8", errors="strict")
    pattern = re.compile(PROPERTY.format(label=re.escape(label)), re.I | re.S)
    values = {value.replace(",", ".") for value in pattern.findall(decoded)}
    if len(values) != 1:
        raise ValueError(f"expected one {label!r} value, got {sorted(values)}")
    return next(iter(values))


def load_candidates(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"external_id", "model_candidate_unverified", "safe_to_apply"}
    if not rows or required - set(rows[0]):
        raise ValueError("invalid acquisition candidate schema")
    result = {}
    for row in rows:
        key = model_key(row["model_candidate_unverified"])
        if not key or key in result or row["safe_to_apply"].casefold() != "false":
            raise ValueError("candidates require unique exact model keys and safe_to_apply=false")
        result[key] = row
    return result


def current_product_url(model: str) -> str | None:
    """Return only a deterministic current-series candidate URL.

    A 404 remains a recorded hold.  We intentionally do not map legacy FTS,
    FT-without-M, HRL-without-X, or CT names to a similar current variant.
    """
    upper = model.upper()
    if upper.startswith("DTM "):
        series = "dtm-l" if upper.endswith(" L") else "dtm"
    elif upper.startswith("DT "):
        series = "dt"
    elif upper.startswith("HRL "):
        series = "hrl-x"
    elif upper.startswith("HR "):
        series = "hr"
    elif upper.startswith("FT "):
        series = "ft-m"
    else:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", model.casefold()).strip("-")
    return f"{BASE}/catalog/statsionarnye/{series}/{slug}/"


def acquire(candidates_path: Path, output_dir: Path, registry: Path, summary_path: Path, timeout: float, workers: int) -> dict:
    candidates = load_candidates(candidates_path)
    requested_by_url = {
        url: row for row in candidates.values()
        if (url := current_product_url(row["model_candidate_unverified"])) is not None
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    fetched = []
    failures = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = {pool.submit(fetch, url, timeout): url for url in sorted(requested_by_url)}
        for job in as_completed(jobs):
            requested = jobs[job]
            try:
                final, raw = job.result()
                fetched.append((final, raw))
            except Exception as error:
                failures.append({"source_url": requested, "reason": str(error)})

    rows = []
    matched = set()
    for final, raw in sorted(fetched):
        try:
            model = page_model(raw)
            key = model_key(model)
        except Exception:
            continue
        candidate = candidates.get(key)
        if candidate is None:
            continue
        if key in matched:
            raise ValueError(f"multiple current pages for exact model {model}")
        voltage = property_value(raw, "Напряжение, В")
        capacity = property_value(raw, "Емкость, Ач")
        matched.add(key)
        filename = hashlib.sha256(final.encode("utf-8")).hexdigest()[:16] + ".html"
        snapshot = output_dir / filename
        snapshot.write_bytes(raw)
        rows.append({
            "external_id": candidate["external_id"], "model": candidate["model_candidate_unverified"],
            "source_url": final, "source_snapshot_path": snapshot.resolve().relative_to(Path.cwd().resolve()).as_posix(),
            "source_sha256": hashlib.sha256(raw).hexdigest(), "content_model_key": key,
            "voltage_v": voltage, "capacity_ah": capacity, "evidence_kind": "exact_product_page",
            "publisher": "DELTA Battery / ENERGON", "safe_to_apply": "false",
        })

    ct_final, ct_raw = fetch(CT_URL, timeout)
    ct_path = output_dir / "delta-ct-series-current.html"
    ct_path.write_bytes(ct_raw)
    ct_text = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", ct_raw.decode("utf-8", errors="strict"))))
    required_ct_tokens = ["DELTA CT", "мотоцикл", "скутер"]
    if not all(token.casefold() in ct_text.casefold() for token in required_ct_tokens):
        raise ValueError("current CT snapshot lacks required scope tokens")

    rows.sort(key=lambda row: row["external_id"])
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(rows[0]) if rows else ["external_id", "model", "source_url", "source_snapshot_path", "source_sha256", "content_model_key", "voltage_v", "capacity_ah", "evidence_kind", "publisher", "safe_to_apply"]
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "candidate_records": len(candidates), "targeted_product_urls": len(requested_by_url),
        "fetched_product_pages": len(fetched),
        "network_failures": failures, "exact_candidate_pages": len(rows),
        "uncovered_candidates": len(candidates) - len(rows),
        "ct_scope_snapshot": {"source_url": ct_final, "snapshot_path": ct_path.resolve().relative_to(Path.cwd().resolve()).as_posix(), "snapshot_sha256": hashlib.sha256(ct_raw).hexdigest(), "required_tokens": required_ct_tokens},
        "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest(), "automatic_database_mutations": 0,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(acquire(args.candidates, args.output_dir, args.registry, args.summary, args.timeout, args.workers), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
