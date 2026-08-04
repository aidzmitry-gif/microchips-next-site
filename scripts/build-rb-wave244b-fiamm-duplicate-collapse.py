#!/usr/bin/env python3
"""Build fail-closed collapse evidence for two exact FIAMM duplicates."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "docs/audits/generated/rb-wave243b-fiamm-panasonic-description-ledger.csv"
SOURCE_DIR = ROOT / "docs/audits/sources/wave244b-fiamm-duplicates"
ACQUISITION = SOURCE_DIR / "acquisition.json"
LIVE_SNAPSHOT = SOURCE_DIR / "live-db-safety-snapshot.json"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave244b-fiamm-duplicate-collapse-evidence.csv"
MANIFEST = ROOT / "docs/imports/rb-reviewed-fiamm-duplicates-wave244b-2026-07-30.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave244b-fiamm-duplicate-collapse.summary.json"
SITE_KEY = "microchips-by"
CHECKED_AT = "2026-07-30"

PINS = {
    DISCOVERY: "1e1c7e1dc846cd24207009f797b3645f807e821b8772cfd297b414e638d22eba",
    ACQUISITION: "a64d89415fa4cf650a20089f66b47da8f287ad02bd097a3362f2ccc0e44022ac",
}

PAIRS = (
    {"duplicate": "bitrix:1488", "survivor": "ФР-00001439", "mpn": "FG21202", "capacity": "12"},
    {"duplicate": "bitrix:1542", "survivor": "ФР-00001513", "mpn": "FG21803", "capacity": "18"},
)

EVIDENCE_FIELDS = [
    "duplicate_external_id", "duplicate_name", "survivor_external_id", "survivor_name",
    "manufacturer", "mpn", "voltage_v", "capacity_ah", "source_row",
    "source_url", "source_snapshot_path", "source_snapshot_sha256",
    "duplicate_path", "survivor_path", "duplicate_category_external_ids",
    "survivor_category_external_ids", "survivor_price", "survivor_current_price_evidence",
    "decision", "hold_reason",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def php_query(external_ids: list[str]) -> str:
    ids = ",".join("'" + value.replace("'", "''") + "'" for value in external_ids)
    return (
        f"$site=App\\Models\\Site::where('key','{SITE_KEY}')->sole();$ids=[{ids}];$out=[];"
        "foreach($ids as $externalId){$p=App\\Models\\Product::where('external_id',$externalId)->first();"
        "if(!$p){$out[]=['external_id'=>$externalId,'missing'=>true];continue;}"
        "$siteProducts=App\\Models\\SiteProduct::where('site_id',$site->id)->where('product_id',$p->id)->get();$sp=$siteProducts->first();"
        "$urls=$sp?App\\Models\\SiteUrl::where('site_id',$site->id)->where('target_type','product')->where('target_id',$sp->id)->get(['path','is_indexable'])->toArray():[];"
        "$seos=$sp?App\\Models\\SiteSeo::where('site_id',$site->id)->where('resource_type','product')->where('resource_id',$sp->id)->get(['is_indexable','schema'])->toArray():[];"
        "$categories=$sp?$sp->categories()->pluck('site_categories.external_id')->filter()->sort()->values()->all():[];"
        "$priceEvidence=$sp?$sp->priceEvidences()->where('is_current',true)->get(['calculated_price','currency'])->toArray():[];"
        "$verifiedMedia=App\\Models\\ProductMedia::where('product_id',$p->id)->where('verification_status','verified')->where('is_published',true)->count();"
        "$familyRoles=App\\Models\\ProductFamily::where('site_id',$site->id)->where('canonical_product_id',$p->id)->count()+App\\Models\\ProductVariant::where('product_id',$p->id)->whereHas('family',fn($q)=>$q->where('site_id',$site->id))->count();"
        "$out[]=['external_id'=>$externalId,'missing'=>false,'name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,'status'=>$p->status,"
        "'site_product_count'=>$siteProducts->count(),'site_product_id'=>$sp?->id,'is_published'=>(bool)($sp?->is_published),'availability'=>$sp?->availability,'price'=>$sp?->price,"
        "'price_evidence_total'=>$sp?$sp->priceEvidences()->count():0,'current_price_evidence'=>$priceEvidence,'verified_media'=>$verifiedMedia,'family_roles'=>$familyRoles,'urls'=>$urls,'seos'=>$seos,'categories'=>$categories];}"
        "echo json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )


def query_live(external_ids: list[str]) -> dict[str, dict]:
    encoded = base64.b64encode(php_query(external_ids).encode()).decode()
    process = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute=eval(base64_decode('{encoded}'));"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    payload = process.stdout.strip()
    if process.returncode != 0 or not payload.startswith("["):
        raise RuntimeError(f"Live query failed: {payload or process.stderr.strip()}")
    rows = json.loads(payload)
    if len(rows) != len(external_ids) or len({row["external_id"] for row in rows}) != len(rows):
        raise RuntimeError("Live query cardinality drift")
    return {row["external_id"]: row for row in rows}


def safety_reasons(row: dict, *, duplicate: bool) -> list[str]:
    reasons = []
    expected_status = "draft" if duplicate else "active"
    if row.get("missing") or row.get("status") != expected_status or row.get("site_product_count") != 1 or not row.get("is_published"):
        reasons.append("missing_or_non_unique_expected_status_published_site_product")
    if row.get("availability") != "on_request":
        reasons.append("availability_drift")
    urls = row.get("urls") or []
    if len(urls) != 1 or urls[0].get("is_indexable"):
        reasons.append("requires_one_noindex_url")
    seos = row.get("seos") or []
    if not seos or any(item.get("is_indexable") or item.get("schema") is not None for item in seos):
        reasons.append("seo_state_not_closed")
    if not row.get("categories"):
        reasons.append("missing_category")
    if duplicate:
        if row.get("price") is not None or row.get("price_evidence_total") != 0:
            reasons.append("duplicate_has_commercial_price")
        if row.get("verified_media") != 0:
            reasons.append("duplicate_has_verified_media")
        if row.get("family_roles") != 0:
            reasons.append("duplicate_has_family_role")
    else:
        current = row.get("current_price_evidence") or []
        price = row.get("price")
        if price is None:
            if current:
                reasons.append("survivor_has_evidence_without_price")
        elif len(current) != 1 or decimal(current[0].get("calculated_price")) != decimal(price) or current[0].get("currency") != "BYN":
            reasons.append("survivor_price_evidence_mismatch")
    return reasons


def assert_no_repeat(url: str, source_sha: str) -> None:
    for path in (ROOT / "docs/audits/sources").rglob("*.pdf"):
        if SOURCE_DIR in path.parents:
            continue
        if sha256(path) == source_sha:
            raise RuntimeError(f"Official snapshot SHA already used: {relative(path)}")
    collisions = []
    for base in (ROOT / "docs/audits", ROOT / "docs/imports"):
        for path in base.rglob("*"):
            normalized_path = path.as_posix().lower()
            if (
                not path.is_file()
                or "wave244b" in normalized_path
                or "prior-source-exclusions" in normalized_path
                or path.suffix.lower() not in {".json", ".csv", ".md", ".txt"}
            ):
                continue
            try:
                if url in path.read_text(encoding="utf-8", errors="ignore"):
                    collisions.append(relative(path))
            except OSError:
                continue
    if collisions:
        raise RuntimeError(f"Official URL already used: {collisions}")


def exact_rows(snapshot: Path) -> dict[str, dict[str, str]]:
    with pdfplumber.open(snapshot) as document:
        if len(document.pages) != 2:
            raise RuntimeError("FIAMM FG catalogue page count drift")
        text = document.pages[1].extract_text() or ""
    rows = {}
    pattern = re.compile(
        r"^(FG21202|FG21803)\*\s+(12)\s+([0-9,]+)\s+(12|18)\s+(.+)$", re.MULTILINE
    )
    for match in pattern.finditer(text):
        model, voltage, _ten_hour, capacity, remainder = match.groups()
        rows[model] = {
            "model": model, "voltage": voltage, "capacity": capacity,
            "row": " ".join(match.group(0).split()), "remainder": remainder,
        }
    if set(rows) != {"FG21202", "FG21803"}:
        raise RuntimeError(f"Expected two exact bounded FIAMM rows, got {sorted(rows)}")
    if not rows["FG21202"]["remainder"].endswith("Faston 6.3") or not rows["FG21803"]["remainder"].endswith("Flag Ø5.5"):
        raise RuntimeError("FIAMM terminal membership drift")
    return rows


def main() -> int:
    for path, expected in PINS.items():
        if sha256(path) != expected:
            raise RuntimeError(f"Input SHA mismatch for {relative(path)}")
    acquisition = json.loads(ACQUISITION.read_text(encoding="utf-8"))
    snapshot = ROOT / acquisition["snapshot_path"]
    if sha256(snapshot) != acquisition["snapshot_sha256"]:
        raise RuntimeError("Official FIAMM snapshot SHA drift")
    assert_no_repeat(acquisition["source_url"], acquisition["snapshot_sha256"])
    source_rows = exact_rows(snapshot)

    with DISCOVERY.open(encoding="utf-8-sig", newline="") as stream:
        discovery = {row["external_id"]: row for row in csv.DictReader(stream)}
    for pair in PAIRS:
        row = discovery.get(pair["duplicate"])
        if row is None or row["mpn_candidate"] != pair["mpn"] or row["partition"] != "hold_legacy_canonical_duplicate" or row["legacy_duplicate_external_ids"] != pair["survivor"]:
            raise RuntimeError(f"Wave243B duplicate discovery drift for {pair['duplicate']}")

    ids = sorted({value for pair in PAIRS for value in (pair["duplicate"], pair["survivor"])})
    live = query_live(ids)
    LIVE_SNAPSHOT.write_text(json.dumps({"checked_at": CHECKED_AT, "site_key": SITE_KEY, "products": [live[value] for value in ids]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    evidence_rows = []
    planned = []
    for pair in PAIRS:
        duplicate = live[pair["duplicate"]]
        survivor = live[pair["survivor"]]
        official = source_rows[pair["mpn"]]
        reasons = safety_reasons(duplicate, duplicate=True) + safety_reasons(survivor, duplicate=False)
        if normalized(survivor.get("manufacturer")) != "FIAMM" or normalized(survivor.get("mpn")) != pair["mpn"]:
            reasons.append("survivor_exact_identity_mismatch")
        if normalized(pair["mpn"]) not in normalized(duplicate.get("name")) or normalized(pair["mpn"]) not in normalized(survivor.get("name")):
            reasons.append("bounded_model_missing_from_name")
        if official["voltage"] != "12" or official["capacity"] != pair["capacity"]:
            reasons.append("official_electrical_row_mismatch")
        duplicate_categories = set(duplicate.get("categories") or [])
        survivor_categories = set(survivor.get("categories") or [])
        if not duplicate_categories.issubset(survivor_categories):
            reasons.append("survivor_does_not_preserve_duplicate_categories")
        evidence_rows.append({
            "duplicate_external_id": pair["duplicate"], "duplicate_name": duplicate.get("name", ""),
            "survivor_external_id": pair["survivor"], "survivor_name": survivor.get("name", ""),
            "manufacturer": survivor.get("manufacturer", ""), "mpn": survivor.get("mpn", ""),
            "voltage_v": official["voltage"], "capacity_ah": official["capacity"], "source_row": official["row"],
            "source_url": acquisition["source_url"], "source_snapshot_path": acquisition["snapshot_path"], "source_snapshot_sha256": acquisition["snapshot_sha256"],
            "duplicate_path": duplicate["urls"][0]["path"] if duplicate.get("urls") else "", "survivor_path": survivor["urls"][0]["path"] if survivor.get("urls") else "",
            "duplicate_category_external_ids": "|".join(duplicate.get("categories") or []), "survivor_category_external_ids": "|".join(survivor.get("categories") or []),
            "survivor_price": survivor.get("price") or "", "survivor_current_price_evidence": len(survivor.get("current_price_evidence") or []),
            "decision": "PASS" if not reasons else "HOLD", "hold_reason": "|".join(sorted(set(reasons))),
        })
        if not reasons:
            planned.append((pair, duplicate, survivor, official))

    if len(planned) != 2:
        raise RuntimeError(f"Fail-closed Wave244B requires both rows safe; PASS={len(planned)}")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=EVIDENCE_FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(evidence_rows)
    evidence_sha = sha256(EVIDENCE)
    manifest_rows = []
    for pair, duplicate, survivor, official in planned:
        manifest_rows.append({
            "survivor_external_id": pair["survivor"], "duplicate_external_id": pair["duplicate"],
            "survivor_name": survivor["name"], "duplicate_name": duplicate["name"],
            "survivor_path": survivor["urls"][0]["path"], "duplicate_path": duplicate["urls"][0]["path"],
            "model_core": pair["mpn"], "voltage": official["voltage"] + "V", "capacity": official["capacity"] + "Ah", "availability": "on_request",
            "category_external_ids": survivor["categories"], "duplicate_category_external_ids": duplicate["categories"],
            "manufacturer": "FIAMM", "survivor_mpn": survivor["mpn"], "source_url": acquisition["source_url"],
            "source_evidence_path": relative(EVIDENCE), "source_evidence_sha256": evidence_sha,
            "source_snapshot_path": acquisition["snapshot_path"], "source_snapshot_sha256": acquisition["snapshot_sha256"],
            "decision_reason": "New FIAMM manufacturer catalogue Rev. 04.2026 proves the exact FG model and electrical row; live canonical owner has the same normalized FIAMM MPN and safely preserves categories and commercial evidence.",
        })
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": SITE_KEY, "purpose": "Wave244B fail-closed collapse of two exact FIAMM noindex duplicates into priced 1C survivors.", "duplicates": manifest_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1, "wave": "wave244b-fiamm-duplicate-collapse", "checked_at": CHECKED_AT,
        "scope": {"pairs": 2, "live_products_queried": 4}, "result": {"PASS": 2, "HOLD": 0, "manifest_rows": 2},
        "source": {**acquisition, "prior_url_collisions": 0, "prior_sha_collisions": 0, "exact_rows": 2},
        "live_snapshot": {"path": relative(LIVE_SNAPSHOT), "sha256": sha256(LIVE_SNAPSHOT)},
        "evidence": {"path": relative(EVIDENCE), "sha256": evidence_sha}, "manifest": {"path": relative(MANIFEST), "sha256": sha256(MANIFEST)},
        "policy": {"fail_closed_both_pairs_required": True, "database_operations": 0, "apply_requested": False},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
