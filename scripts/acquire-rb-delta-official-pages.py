#!/usr/bin/env python3
"""Acquire pinned first-party Delta product pages for the Wave 198 candidates.

The script discovers product URLs only from an allowlisted set of official
series pages, follows redirects only to the Delta host, matches the product H1
to an existing Wave 198 candidate with a decimal-preserving model key, and
writes an auditable source-page registry.  It never touches the application
database.
"""
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
SERIES_SLUGS = ("dt", "dtm", "dtm_l", "ft_m", "fts_x", "hr", "hrl_x", "hrl_w", "stc")
BASE_URL = "https://delta-batt.com/"
EXTRA_DISCOVERY_URLS = (
    "https://delta-batt.com/catalog/akkumulyatory_statsionarnye/filter/series-cgd/general-scope-alternativnaya_energetika/",
)
PRODUCT_PATH = re.compile(r"/products/[a-z0-9_]+/", re.I)
H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
TAG = re.compile(r"<[^>]+>")


def model_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold().replace(",", ".")
    normalized = re.sub(r"(?<=\d)\.(?=\d)", " decimal ", normalized)
    return re.sub(r"[^a-z0-9]+", "", normalized)


def load_candidates(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"external_id", "model_candidate_unverified", "safe_to_apply"}
    if not rows or required - set(rows[0]):
        raise ValueError("candidate manifest is empty or missing required columns")
    by_key: dict[str, dict[str, str]] = {}
    for row in rows:
        key = model_key(row["model_candidate_unverified"])
        if not key or key in by_key:
            raise ValueError("candidate models must have unique nonblank decimal-preserving keys")
        if row["safe_to_apply"].casefold() != "false":
            raise ValueError("acquisition accepts preparation-only candidates")
        by_key[key] = row
    return by_key


def fetch(url: str, timeout: float) -> tuple[str, bytes]:
    request = Request(url, headers={"User-Agent": "microchips.by catalog evidence audit/1.0"})
    with urlopen(request, timeout=timeout) as response:
        final_url = response.geturl()
        parsed = urlparse(final_url)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS:
            raise ValueError(f"redirected outside Delta first-party host: {final_url}")
        return final_url, response.read()


def page_model(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="strict")
    headings = []
    for value in H1.findall(text):
        heading = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", value))).strip()
        heading = re.sub(r"^DELTA\s+", "", heading, flags=re.I)
        if heading and heading not in headings:
            headings.append(heading)
    if len(headings) != 1:
        raise ValueError(f"expected one unique product H1, got {len(headings)}")
    return headings[0]


def acquire(
    candidates_path: Path,
    output_dir: Path,
    registry_path: Path,
    summary_path: Path,
    timeout: float,
    workers: int,
) -> dict[str, object]:
    candidates = load_candidates(candidates_path)
    series_snapshots = []
    product_urls: set[str] = set()
    discovery_urls = [(slug, urljoin(BASE_URL, f"series/{slug}/")) for slug in SERIES_SLUGS]
    discovery_urls += [("cgd-filter", url) for url in EXTRA_DISCOVERY_URLS]
    for slug, source_url in discovery_urls:
        final_url, raw = fetch(source_url, timeout)
        paths = sorted(set(PRODUCT_PATH.findall(raw.decode("utf-8", errors="strict"))))
        if not paths:
            raise ValueError(f"official series page contains no product paths: {final_url}")
        product_urls.update(urljoin(BASE_URL, path) for path in paths)
        series_snapshots.append({
            "series": slug,
            "source_url": final_url,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "product_paths": len(paths),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    fetched: list[tuple[str, str, bytes]] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = {pool.submit(fetch, url, timeout): url for url in sorted(product_urls)}
        for job in as_completed(jobs):
            requested_url = jobs[job]
            try:
                final_url, raw = job.result()
                fetched.append((requested_url, final_url, raw))
            except Exception as error:  # the summary records every network/parser hold
                failures.append({"source_url": requested_url, "reason": str(error)})

    records: list[dict[str, str]] = []
    unmatched: list[dict[str, str]] = []
    matched_keys: set[str] = set()
    for requested_url, final_url, raw in sorted(fetched):
        try:
            model = page_model(raw)
        except Exception as error:
            unmatched.append({"source_url": final_url, "reason": str(error)})
            continue
        key = model_key(model)
        candidate = candidates.get(key)
        if candidate is None:
            unmatched.append({"source_url": final_url, "model": model, "reason": "not_exact_wave198_candidate"})
            continue
        if key in matched_keys:
            raise ValueError(f"multiple official product pages match candidate model: {model}")
        matched_keys.add(key)
        filename = hashlib.sha256(final_url.encode("utf-8")).hexdigest()[:16] + ".html"
        saved_path = output_dir / filename
        saved_path.write_bytes(raw)
        records.append({
            "external_id": candidate["external_id"],
            "model": candidate["model_candidate_unverified"],
            "page_model": model,
            "source_url": final_url,
            "html_path": saved_path.as_posix(),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
        })

    records.sort(key=lambda row: row["external_id"])
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["external_id", "model", "page_model", "source_url", "html_path", "source_sha256"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    summary = {
        "candidate_records": len(candidates),
        "series_snapshots": series_snapshots,
        "discovered_product_urls": len(product_urls),
        "fetched_product_pages": len(fetched),
        "network_failures": failures,
        "exact_candidate_pages": len(records),
        "uncovered_candidates": len(candidates) - len(records),
        "unmatched_product_pages": unmatched,
        "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(),
        "automatic_database_mutations": 0,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    print(json.dumps(acquire(args.candidates, args.output_dir, args.registry, args.summary, args.timeout, args.workers), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
