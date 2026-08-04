#!/usr/bin/env python3
"""Acquire immutable, exact-SKU evidence from Schneider Electric product pages.

This is an acquisition boundary, not an enrichment tool: it neither parses
technical facts nor connects to the application database.  A downloaded page
is retained only after the final first-party URL and an exact SKU marker in a
product-bearing page field have both been verified.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

SKU = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{1,63}\Z")
# Locale product pages normally redirect from ``/product/SKU/`` to
# ``/product/SKU/descriptive-slug/``.  The first segment after ``product`` is
# the identity boundary; a later slug is presentation only.
PRODUCT_PATH = re.compile(r"/product/([^/?#]+)(?:/[^?#]*)?/?\Z", re.I)
H_TAG = re.compile(r"<h[12]\b[^>]*>(.*?)</h[12]>", re.I | re.S)
META = re.compile(r"<meta\b[^>]*\bcontent\s*=\s*(['\"])(.*?)\1[^>]*>", re.I | re.S)
JSON_SCRIPT = re.compile(r"<script\b[^>]*\btype\s*=\s*(['\"])application/(?:ld\+json|json)\1[^>]*>(.*?)</script>", re.I | re.S)


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    body: bytes


def is_false(value: str) -> bool:
    return value.strip().casefold() == "false"


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def first_party_product_url(value: str, sku: str) -> bool:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https" or not (host == "se.com" or host.endswith(".se.com"))
        or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
    ):
        return False
    match = PRODUCT_PATH.search(parsed.path)
    return bool(match and normalized(match.group(1)) == normalized(sku))


def exact_sku_evidence(raw: str, sku: str) -> str:
    needle = re.compile(rf"(?<![A-Za-z0-9]){re.escape(sku)}(?![A-Za-z0-9])", re.I)
    for field, pattern in (("h1_or_h2", H_TAG), ("meta", META), ("json", JSON_SCRIPT)):
        for match in pattern.finditer(raw):
            value = match.group(1) if field == "h1_or_h2" else match.group(2)
            if needle.search(text(value)):
                return field
    return ""


def fetch(url: str, timeout: float) -> FetchResult:
    request = Request(url, headers={"User-Agent": "microchips-source-audit/1.0"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310: host is fixed above
        return FetchResult(response.geturl(), response.read())


def load_candidates(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"external_id", "model_token", "safe_to_apply"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing required columns: " + ", ".join(sorted(missing)))
        rows = list(reader)
    ids = [row["external_id"].strip() for row in rows]
    tokens = [row["model_token"].strip() for row in rows]
    if not rows or not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("external_id must be nonblank and unique")
    if not all(SKU.fullmatch(token) for token in tokens) or len({normalized(token) for token in tokens}) != len(tokens):
        raise ValueError("model_token must be a unique exact SKU")
    if any(not is_false(row["safe_to_apply"]) for row in rows):
        raise ValueError("all candidates must explicitly remain safe_to_apply=false")
    return rows


def acquire(
    candidates_path: Path,
    registry_path: Path,
    summary_path: Path,
    snapshot_dir: Path,
    timeout: float = 25.0,
    workers: int = 8,
    fetcher: Callable[[str, float], FetchResult] = fetch,
) -> dict[str, object]:
    candidates = load_candidates(candidates_path)
    if workers < 1:
        raise ValueError("workers must be positive")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    registry: list[dict[str, str]] = []
    rejected: Counter[str] = Counter()

    fetched: dict[str, FetchResult | Exception] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {}
        for candidate in candidates:
            sku = candidate["model_token"].strip()
            # ``ww/en`` is only a country selector and never constitutes a
            # product document. Pin a real English locale for reproducible
            # first-party evidence.
            initial_url = f"https://www.se.com/us/en/product/{quote(sku, safe='')}/"
            jobs[pool.submit(fetcher, initial_url, timeout)] = candidate["external_id"].strip()
        for job in as_completed(jobs):
            external_id = jobs[job]
            try:
                fetched[external_id] = job.result()
            except Exception as error:  # keep exact failure object for the row hold
                fetched[external_id] = error

    for candidate in candidates:
        sku = candidate["model_token"].strip()
        initial_url = f"https://www.se.com/us/en/product/{quote(sku, safe='')}/"
        row = {"external_id": candidate["external_id"].strip(), "model_token": sku, "requested_url": initial_url, "final_url": "", "source_sha256": "", "snapshot_path": "", "page_evidence_field": "", "acquisition_status": "hold", "safe_to_apply": "false"}
        result = fetched[row["external_id"]]
        if isinstance(result, Exception):
            rejected["fetch_failed"] += 1
            row["hold_reason"] = type(result).__name__
            registry.append(row); continue
        # Preserve the observed redirect target even when it is rejected. This
        # is diagnostic evidence, not authorization to use the page.
        row["final_url"] = result.final_url
        if not first_party_product_url(result.final_url, sku):
            rejected["final_url_not_exact_first_party_product"] += 1
            row["hold_reason"] = "final_url_not_exact_first_party_product"
            registry.append(row); continue
        try:
            page = result.body.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            rejected["non_utf8_page"] += 1
            row["hold_reason"] = "non_utf8_page"
            registry.append(row); continue
        evidence_field = exact_sku_evidence(page, sku)
        if not evidence_field:
            rejected["exact_sku_not_in_h1_h2_meta_or_json"] += 1
            row["hold_reason"] = "exact_sku_not_in_h1_h2_meta_or_json"
            registry.append(row); continue
        digest = hashlib.sha256(result.body).hexdigest()
        snapshot = snapshot_dir / f"{digest}.html"
        if snapshot.exists() and snapshot.read_bytes() != result.body:
            raise ValueError("SHA-256 snapshot collision")
        if not snapshot.exists():
            snapshot.write_bytes(result.body)
        row.update({"source_sha256": digest, "snapshot_path": str(snapshot.resolve()), "page_evidence_field": evidence_field, "acquisition_status": "acquired", "hold_reason": ""})
        registry.append(row)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["external_id", "model_token", "requested_url", "final_url", "source_sha256", "snapshot_path", "page_evidence_field", "acquisition_status", "hold_reason", "safe_to_apply"]
    with registry_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(registry)
    summary = {"candidate_path": str(candidates_path), "candidate_sha256": hashlib.sha256(candidates_path.read_bytes()).hexdigest(), "candidate_records": len(candidates), "acquired_records": sum(row["acquisition_status"] == "acquired" for row in registry), "held_records": sum(row["acquisition_status"] != "acquired" for row in registry), "rejected_counts": dict(sorted(rejected.items())), "registry_path": str(registry_path), "registry_sha256": hashlib.sha256(registry_path.read_bytes()).hexdigest(), "snapshot_dir": str(snapshot_dir), "technical_facts_parsed": 0, "automatic_database_mutations": 0, "safe_to_apply_records": 0}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(acquire(
        args.candidates, args.registry, args.summary, args.snapshot_dir,
        args.timeout, args.workers,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
