#!/usr/bin/env python3
"""Promote only exact FIAMM identities backed by an authorised catalogue.

Wave233 already performed the expensive 106-row title and collision review.
This builder does not repeat that work: it consumes only Wave233's 79 unique,
collision-free candidates and requires the exact model to occur in a newly
pinned catalogue PDF.  The authority chain is independently hash-pinned.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity-ledger.csv"
ACQUISITION = ROOT / "docs/audits/generated/rb-wave237-fiamm-primary-acquisition.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave237-fiamm-authorized-identity-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave237-fiamm-authorized-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave237-fiamm-2026-07-29.json"
CHECKED_AT = "2026-07-29"
EXPECTED_INPUT_ROWS = 106
EXPECTED_REVIEWED_CANDIDATES = 79
AUTHORITY_STATEMENT = (
    "официальный авторизованный дистрибьютор промышленных стационарных аккумуляторов "
    "производства итальянской компании FIAMM Energy Technology S.p.A"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value or "").upper())


def model_pattern(model: str) -> re.Pattern[str]:
    chars = [re.escape(char) for char in unicodedata.normalize("NFKC", model).upper() if char.isalnum()]
    if not chars:
        raise SystemExit(f"model has no alphanumeric token: {model!r}")
    return re.compile(r"(?<![A-Z0-9])" + r"[\s,._/-]*".join(chars) + r"(?![A-Z0-9])", re.I)


def source_id(model: str) -> str | None:
    token = normalized(model)
    if token.startswith("12FIT"):
        return "fit"
    if "FLB" in token:
        return "flb"
    if "FGL" in token:
        return "fgl"
    if "FGH" in token:
        return "fgh"
    if "SLA" in token:
        return "sla"
    if token.startswith("FG"):
        return "fg"
    return None


def main() -> None:
    acquisition = json.loads(ACQUISITION.read_text(encoding="utf-8"))
    authority = acquisition["authority"]
    authority_path = ROOT / authority["path"]
    if sha256(authority_path) != authority["sha256"]:
        raise SystemExit("FIAMM authority snapshot drifted")
    authority_raw = authority_path.read_text(encoding="utf-8", errors="replace")
    if AUTHORITY_STATEMENT.casefold() not in authority_raw.casefold():
        raise SystemExit("FIAMM authority statement is absent from the pinned snapshot")

    documents: dict[str, dict[str, str]] = {}
    for row in acquisition["documents"]:
        path = ROOT / row["path"]
        if sha256(path) != row["sha256"]:
            raise SystemExit(f"FIAMM {row['series']} catalogue drifted")
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
        if "FIAMM" not in text.upper() or row["series"].upper() not in text.upper():
            raise SystemExit(f"FIAMM {row['series']} catalogue lacks publisher/series markers")
        documents[row["series"]] = {**row, "text": text}

    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        reviewed = list(csv.DictReader(handle))
    if len(reviewed) != EXPECTED_INPUT_ROWS:
        raise SystemExit("Wave233 FIAMM ledger row count drifted")
    candidates = [row for row in reviewed if row["partition"] == "exact_local_text_unique"]
    if len(candidates) != EXPECTED_REVIEWED_CANDIDATES:
        raise SystemExit("Wave233 FIAMM reviewed-candidate partition drifted")

    ledger: list[dict[str, str]] = []
    products: list[dict[str, str]] = []
    for row in candidates:
        series = source_id(row["title_mpn"])
        document = documents.get(series or "")
        exact = bool(document and model_pattern(row["title_mpn"]).search(document["text"]))
        partition = "exact_authorized_catalogue_unique" if exact else "hold_no_exact_authorized_catalogue"
        ledger.append(
            {
                "external_id": row["external_id"],
                "current_name": row["current_name"],
                "mpn": row["title_mpn"],
                "normalized_mpn": normalized(row["title_mpn"]),
                "series": series or "",
                "partition": partition,
                "source_url": document["url"] if exact else "",
                "source_snapshot_path": document["path"] if exact else "",
                "source_snapshot_sha256": document["sha256"] if exact else "",
                "authority_url": authority["url"],
                "authority_snapshot_path": authority["path"],
                "authority_snapshot_sha256": authority["sha256"],
                "hold_reason": "" if exact else "exact model absent from pinned authorised catalogue PDF",
            }
        )
        if exact:
            products.append(
                {
                    "external_id": row["external_id"],
                    "current_name": row["current_name"],
                    "manufacturer": "Fiamm",
                    "mpn": row["title_mpn"],
                    "source_url": document["url"],
                    "source_kind": "official_authorized_distributor_catalogue",
                    "source_publisher": "FIAMM Industrial RUS",
                    "checked_at": CHECKED_AT,
                    "product_type": "stationary VRLA battery",
                    "source_snapshot_path": "../audits/" + document["path"].removeprefix("docs/audits/"),
                    "source_snapshot_sha256": document["sha256"],
                    "authority_url": authority["url"],
                    "authority_snapshot_path": "../audits/" + authority["path"].removeprefix("docs/audits/"),
                    "authority_snapshot_sha256": authority["sha256"],
                    "authority_statement": AUTHORITY_STATEMENT,
                }
            )

    if not products:
        raise SystemExit("no FIAMM identities met the authorised-catalogue gate")
    if len({row["external_id"] for row in products}) != len(products):
        raise SystemExit("FIAMM manifest repeats an external ID")
    if len({normalized(row["mpn"]) for row in products}) != len(products):
        raise SystemExit("FIAMM manifest repeats a normalized MPN")

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    manifest = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "purpose": "exact FIAMM identity backed by a hash-pinned authorised-distributor catalogue and authority page",
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = Counter(row["partition"] for row in ledger)
    summary = {
        "schema_version": 1,
        "batch": "wave237_fiamm_authorized_identity",
        "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(reviewed)},
        "no_repeat_rule": "consume only Wave233 exact_local_text_unique rows",
        "reviewed_candidates": len(candidates),
        "partition_counts": dict(sorted(counts.items())),
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(products)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "authority": authority,
        "database_mutations": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reviewed": len(candidates), "manifest_rows": len(products), "partitions": dict(counts)}))


if __name__ == "__main__":
    main()
