#!/usr/bin/env python3
"""Build a read-only, fail-closed Fiamm identity candidate bundle for Wave233.

The input is intentionally frozen to blank-manufacturer UPS cards.  A candidate
may enter the manifest only when its literal title MPN occurs as a bounded token
in one of the already-pinned Fiamm snapshots and no other current product owns
that normalized MPN or SKU.  The saved Fiamm Russia material is distributor
evidence, so the emitted manifest is a review candidate, never apply authority.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-wave233-identity-media-gaps.csv"
SOURCE_DIR = ROOT / "docs/audits/sources/wave206-fiamm-bb-csb"
LEDGER = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity-ledger.csv"
LIVE = ROOT / "docs/audits/generated/rb-wave233-fiamm-live-identity-collisions.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave233-fiamm-identity.summary.json"
MANIFEST = ROOT / "docs/imports/rb-fiamm-identity-candidates-wave233-2026-07-29.json"
CHECKED_AT = "2026-07-29"
EXPECTED_ROWS = 106

SOURCES = {
    "fg": {
        "filename": "fiamm-fg-series-2026-07-29.html",
        "url": "https://www.fiamm.ru/equipment/FG-series/",
        "publisher": "FIAMM Russia",
        "source_kind": "official_distributor_series_page",
    },
    "fgh": {
        "filename": "fiamm-fgh-series-2026-07-29.html",
        "url": "https://www.fiamm.ru/equipment/FGH-series/",
        "publisher": "FIAMM Russia",
        "source_kind": "official_distributor_series_page",
    },
    "fgl": {
        "filename": "fiamm-fgl-series-2026-07-29.html",
        "url": "https://www.fiamm.ru/equipment/FGL-series/",
        "publisher": "FIAMM Russia",
        "source_kind": "official_distributor_series_page",
    },
    "flb": {
        "filename": "fiamm-flb-series-2026-07-29.html",
        "url": "https://www.fiamm.ru/equipment/FLB-series/",
        "publisher": "FIAMM Russia",
        "source_kind": "official_distributor_series_page",
    },
    "sla": {
        "filename": "fiamm-sla-series-2026-07-29.html",
        "url": "https://www.fiamm.ru/equipment/SLA-series/",
        "publisher": "FIAMM Russia",
        "source_kind": "official_distributor_series_page",
    },
    "fit": {
        "filename": "fiamm-fit-2022.pdf",
        "url": "https://www.fiamm.ru/data/Catalogue/2022/FIT_web.pdf",
        "publisher": "FIAMM Russia",
        "source_kind": "official_distributor_catalogue",
    },
    "replacement": {
        "filename": "fiamm-replacement-table-2026-07-29.html",
        "url": "https://www.fiamm.ru/services/faq/zaryadit-accumulyator.html",
        "publisher": "FIAMM Russia",
        "source_kind": "official_distributor_registry",
    },
}

FIELDS = [
    "external_id", "current_name", "title_mpn", "normalized_mpn", "partition",
    "source_id", "source_kind", "source_url", "source_snapshot_path",
    "source_snapshot_sha256", "local_exact_text", "current_product_identity",
    "normalized_mpn_sku_conflict_ids", "hold_reason", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value or "").upper())


def sort_key(external_id: str) -> tuple[int, str]:
    match = re.search(r":(\d+)$", external_id)
    return (int(match.group(1)) if match else 10**12, external_id)


def title_mpn(name: str) -> str:
    if "Fiamm" not in name:
        return ""
    tail = name.split("Fiamm", 1)[1]
    # The product name encloses technical text in a parenthesis immediately
    # after the MPN in some rows, with no separating whitespace.
    return re.split(r"\s*(?:\(|для\b)", tail, maxsplit=1, flags=re.I)[0].strip()


def model_pattern(model: str) -> re.Pattern[str]:
    characters = [re.escape(char) for char in unicodedata.normalize("NFKC", model).upper() if char.isalnum()]
    if not characters:
        raise SystemExit(f"MPN has no alphanumeric token: {model!r}")
    return re.compile(r"(?<![A-Z0-9])" + r"[\s,._/-]*".join(characters) + r"(?![A-Z0-9])", re.I)


def source_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8", errors="replace")


def source_priority(model: str) -> list[str]:
    token = normalized(model)
    if token.startswith("12FIT"):
        return ["fit", "replacement"]
    if "FLB" in token:
        return ["flb", "replacement"]
    if "FGL" in token:
        return ["fgl", "replacement"]
    if "FGH" in token:
        return ["fgh", "replacement"]
    if "SLA" in token:
        return ["sla", "replacement"]
    if token.startswith("FG"):
        return ["fg", "replacement"]
    return ["replacement"]


def selected_rows() -> list[dict[str, str]]:
    rows = [
        row for row in read_csv(INPUT)
        if row["category_external_id"] == "seo:batteries-ups"
        and not row["manufacturer"].strip()
        and "Fiamm" in row["name"]
    ]
    ids = [row["external_id"] for row in rows]
    models = [title_mpn(row["name"]) for row in rows]
    if len(rows) != EXPECTED_ROWS or len(ids) != len(set(ids)) or len(models) != len(set(models)) or not all(models):
        raise SystemExit("Wave233 Fiamm frozen target drifted")
    return sorted(rows, key=lambda row: sort_key(row["external_id"]))


def live_products(external_ids: list[str], normalized_mpns: list[str]) -> list[dict[str, object]]:
    # The query is deliberately restricted to the 106 targets plus products
    # that already own a proposed normalized MPN/SKU.  It has no write clause.
    ids = json.dumps(external_ids, ensure_ascii=True)
    tokens = json.dumps(normalized_mpns, ensure_ascii=True)
    php = (
        f"$ids=json_decode('{ids}',true);$tokens=json_decode('{tokens}',true);"
        "$id=app('db');$expr1=$id->raw(\"regexp_replace(upper(coalesce(mpn_normalized,mpn,'')), '[^A-Z0-9]', '', 'g')\");"
        "$expr2=$id->raw(\"regexp_replace(upper(coalesce(sku_normalized,sku,'')), '[^A-Z0-9]', '', 'g')\");"
        "$r=$id->table('products')->select('external_id','name','sku','mpn','manufacturer','sku_normalized','mpn_normalized','status')"
        "->where(function($q)use($ids,$tokens,$expr1,$expr2){$q->whereIn('external_id',$ids)->orWhereIn($expr1,$tokens)->orWhereIn($expr2,$tokens);})"
        "->orderBy('external_id')->get();echo json_encode($r,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )
    encoded = base64.b64encode(php.encode()).decode()
    run = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if run.returncode or not run.stdout.strip().startswith("["):
        raise SystemExit(f"read-only PostgreSQL query failed: {run.stderr.strip() or run.stdout.strip()}")
    return json.loads(run.stdout.strip())


def main() -> None:
    selected = selected_rows()
    models = {row["external_id"]: title_mpn(row["name"]) for row in selected}
    source_cache: dict[str, dict[str, str]] = {}
    for source_id, source in SOURCES.items():
        path = SOURCE_DIR / source["filename"]
        if not path.is_file():
            raise SystemExit(f"Pinned Fiamm source missing: {path}")
        source_cache[source_id] = {
            **source,
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "text": source_text(path),
        }

    live = live_products([row["external_id"] for row in selected], [normalized(model) for model in models.values()])
    by_external_id = {str(row["external_id"]): row for row in live}
    missing = [row["external_id"] for row in selected if row["external_id"] not in by_external_id]
    if missing:
        raise SystemExit(f"current database lacks frozen Fiamm target rows: {missing}")
    drift = [
        row["external_id"] for row in selected
        if str(by_external_id[row["external_id"]].get("name") or "") != row["name"]
        or by_external_id[row["external_id"]].get("manufacturer") not in (None, "")
    ]
    if drift:
        raise SystemExit(f"current database drifted from frozen blank-manufacturer input: {drift}")

    ledger: list[dict[str, str]] = []
    checks: list[dict[str, object]] = []
    for row in selected:
        external_id = row["external_id"]
        model = models[external_id]
        token = normalized(model)
        source = next((source_cache[key] for key in source_priority(model) if model_pattern(model).search(source_cache[key]["text"].upper())), None)
        current = by_external_id[external_id]
        current_values = sorted({
            normalized(str(current.get(key) or ""))
            for key in ("mpn_normalized", "sku_normalized", "mpn", "sku")
            if normalized(str(current.get(key) or ""))
        })
        current_identity = "|".join(current_values)
        conflicts = sorted({
            str(other["external_id"])
            for other in live
            if str(other["external_id"]) != external_id
            and token in {
                normalized(str(other.get(key) or ""))
                for key in ("mpn_normalized", "sku_normalized", "mpn", "sku")
            }
        }, key=sort_key)
        if not source:
            partition, hold = "hold_no_local_exact_source", "exact_title_mpn_absent_from_all_saved_fiamm_snapshots"
        elif conflicts:
            partition, hold = "hold_normalized_mpn_sku_conflict", "another_current_product_already_owns_the_normalized_mpn_or_sku"
        elif current_values and current_values != [token]:
            partition, hold = "hold_current_identity_mismatch", "target_current_mpn_or_sku_is_not_the_exact_title_mpn"
        else:
            partition, hold = "exact_local_text_unique", ""
        safe = partition == "exact_local_text_unique"
        ledger.append({
            "external_id": external_id, "current_name": row["name"], "title_mpn": model,
            "normalized_mpn": token, "partition": partition,
            "source_id": next((key for key, value in source_cache.items() if value is source), "") if source else "",
            "source_kind": source["source_kind"] if source else "",
            "source_url": source["url"] if source else "",
            "source_snapshot_path": source["path"] if source else "",
            "source_snapshot_sha256": source["sha256"] if source else "",
            "local_exact_text": "true" if source else "false",
            "current_product_identity": current_identity,
            "normalized_mpn_sku_conflict_ids": "|".join(conflicts),
            "hold_reason": hold, "safe_to_apply": "true" if safe else "false",
        })
        checks.append({
            "candidate_external_id": external_id, "candidate_mpn_normalized": token,
            "current_target_identifiers": current_values, "conflicting_external_ids": conflicts,
        })

    products = [{
        "external_id": row["external_id"], "current_name": row["current_name"], "manufacturer": "Fiamm",
        "mpn": row["title_mpn"], "source_url": row["source_url"], "source_kind": row["source_kind"],
        "source_publisher": "FIAMM Russia", "checked_at": CHECKED_AT,
        "product_type": "stationary VRLA battery", "source_snapshot_path": "../audits/" + row["source_snapshot_path"].removeprefix("docs/audits/"),
        "source_snapshot_sha256": row["source_snapshot_sha256"],
    } for row in ledger if row["safe_to_apply"] == "true"]
    if len({row["external_id"] for row in products}) != len(products) or len({normalized(row["mpn"]) for row in products}) != len(products):
        raise SystemExit("manifest uniqueness invariant failed")

    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)
    live_payload = {
        "schema_version": 1, "mode": "read_only", "database": "current Docker PostgreSQL",
        "normalizer": "App\\Domain\\Imports\\ProductIdentity::normalize-compatible alphanumeric uppercase",
        "query_rule": "candidate normalized MPN equals another current product normalized MPN or SKU",
        "candidate_rows_checked": len(selected), "candidate_external_ids": [row["external_id"] for row in selected],
        "checks": checks, "collisions": [check for check in checks if check["conflicting_external_ids"]],
        "database_mutations": 0,
    }
    LIVE.write_text(json.dumps(live_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1, "site_key": "microchips-by", "purpose": "review-only Fiamm identity candidates; no database apply authority",
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = Counter(row["partition"] for row in ledger)
    summary = {
        "schema_version": 1, "batch": "wave233_fiamm_blank_manufacturer_identity", "checked_at": CHECKED_AT,
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(selected)},
        "sources": [{key: value for key, value in source.items() if key != "text"} for source in source_cache.values()],
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "live_collision_guard": {"path": LIVE.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE), "candidate_rows_checked": len(selected), "collision_rows": len(live_payload["collisions"]), "database_mutations": 0},
        "partition_counts": dict(sorted(counts.items())),
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(products), "review_only": True},
        "holds": {"rows": len(ledger) - len(products), "no_local_exact_source": counts["hold_no_local_exact_source"], "normalized_mpn_sku_conflict": counts["hold_normalized_mpn_sku_conflict"], "current_identity_mismatch": counts["hold_current_identity_mismatch"]},
        "policy": {"saved_fiamm_distributor_sources_are_identity_evidence_not_apply_authority": True, "network_fetches": 0, "database_mutations": 0, "media_promotions": 0, "price_or_stock_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(ledger), "partitions": dict(counts), "manifest_rows": len(products), "collisions": len(live_payload["collisions"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
