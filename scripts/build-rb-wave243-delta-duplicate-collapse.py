#!/usr/bin/env python3
"""Build a strict no-repeat collapse manifest for official Delta duplicates.

Wave242 deliberately held exact identities when another live RB product already
owned the normalized manufacturer+MPN.  This builder turns only the subset with
new, SHA-pinned, exact official source rows into redirect-safe duplicate plans.
It never mutates the database.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/audits/generated/rb-wave242-delta-hold-research-ledger.csv"
EVIDENCE = ROOT / "docs/audits/generated/rb-wave243-delta-duplicate-collapse-evidence.csv"
MANIFEST = ROOT / "docs/imports/rb-reviewed-delta-duplicates-wave243-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave243-delta-duplicate-collapse.summary.json"
SITE_KEY = "microchips-by"

EVIDENCE_FIELDS = [
    "duplicate_external_id", "duplicate_name", "survivor_external_id",
    "survivor_name", "manufacturer", "mpn", "voltage_v", "capacity_ah",
    "source_url", "source_snapshot_path", "source_snapshot_sha256",
    "duplicate_path", "survivor_path", "duplicate_category_external_ids",
    "survivor_category_external_ids", "survivor_price",
    "survivor_current_price_evidence", "decision", "hold_reason",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalized(value: str | None) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", (value or "").casefold())


def decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def php_query(external_ids: list[str]) -> str:
    encoded_ids = ",".join("'" + value.replace("'", "''") + "'" for value in external_ids)
    site = SITE_KEY.replace("'", "''")
    return (
        f"$site=App\\Models\\Site::where('key','{site}')->sole();"
        f"$ids=[{encoded_ids}];$out=[];"
        "foreach($ids as $externalId){"
        "$p=App\\Models\\Product::where('external_id',$externalId)->first();"
        "if(!$p){$out[]=['external_id'=>$externalId,'missing'=>true];continue;}"
        "$siteProducts=App\\Models\\SiteProduct::where('site_id',$site->id)->where('product_id',$p->id)->get();"
        "$sp=$siteProducts->first();"
        "$urls=$sp?App\\Models\\SiteUrl::where('site_id',$site->id)->where('target_type','product')->where('target_id',$sp->id)->get(['path','is_indexable'])->toArray():[];"
        "$seos=$sp?App\\Models\\SiteSeo::where('site_id',$site->id)->where('resource_type','product')->where('resource_id',$sp->id)->get(['is_indexable','schema'])->toArray():[];"
        "$categories=$sp?$sp->categories()->pluck('site_categories.external_id')->filter()->sort()->values()->all():[];"
        "$priceEvidence=$sp?$sp->priceEvidences()->where('is_current',true)->get(['calculated_price','currency'])->toArray():[];"
        "$verifiedMedia=App\\Models\\ProductMedia::where('product_id',$p->id)->where('verification_status','verified')->where('is_published',true)->count();"
        "$familyRoles=App\\Models\\ProductFamily::where('site_id',$site->id)->where('canonical_product_id',$p->id)->count()+App\\Models\\ProductVariant::where('product_id',$p->id)->whereHas('family',fn($q)=>$q->where('site_id',$site->id))->count();"
        "$out[]=['external_id'=>$externalId,'missing'=>false,'name'=>$p->name,'manufacturer'=>$p->manufacturer,'mpn'=>$p->mpn,'site_product_count'=>$siteProducts->count(),'site_product_id'=>$sp?->id,'is_published'=>(bool)($sp?->is_published),'availability'=>$sp?->availability,'price'=>$sp?->price,'price_evidence_total'=>$sp?$sp->priceEvidences()->count():0,'current_price_evidence'=>$priceEvidence,'verified_media'=>$verifiedMedia,'family_roles'=>$familyRoles,'urls'=>$urls,'seos'=>$seos,'categories'=>$categories];"
        "}echo json_encode($out,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);"
    )


def query_live(external_ids: list[str]) -> dict[str, dict]:
    encoded = base64.b64encode(php_query(external_ids).encode()).decode()
    expression = f"eval(base64_decode('{encoded}'));"
    process = subprocess.run(
        ["docker", "compose", "exec", "-T", "backend", "php", "artisan", "tinker", f"--execute={expression}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    payload = process.stdout.strip()
    if process.returncode != 0 or not payload.startswith("["):
        raise SystemExit(f"Live query failed: {payload or process.stderr.strip()}")
    rows = json.loads(payload)
    if len(rows) != len(external_ids) or len({row["external_id"] for row in rows}) != len(rows):
        raise SystemExit("Live query cardinality drift")
    return {row["external_id"]: row for row in rows}


def safe_noindex_state(row: dict, *, duplicate: bool) -> list[str]:
    reasons: list[str] = []
    if row.get("missing") or row.get("site_product_count") != 1 or not row.get("is_published"):
        reasons.append("missing_or_non_unique_published_site_product")
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
        evidence = row.get("current_price_evidence") or []
        price = row.get("price")
        if price is None:
            if evidence:
                reasons.append("survivor_has_evidence_without_price")
        elif len(evidence) != 1 or decimal(evidence[0].get("calculated_price")) != decimal(price) or evidence[0].get("currency") != "BYN":
            reasons.append("survivor_price_evidence_mismatch")
    return reasons


def main() -> None:
    source_rows = read_csv(SOURCE)
    targets = [row for row in source_rows if "LIVE_DUPLICATE_OWNERSHIP_CONFLICT" in row["hold_reason"]]
    if len(targets) != 23:
        raise SystemExit(f"Wave242 duplicate scope drift: expected 23, got {len(targets)}")
    duplicate_ids = {row["external_id"] for row in targets}
    owner_ids = {row["live_duplicate_owner_external_ids"] for row in targets if "|" not in row["live_duplicate_owner_external_ids"]}
    live = query_live(sorted(duplicate_ids | owner_ids))
    source_hash = sha256(SOURCE)

    evidence_rows: list[dict[str, object]] = []
    manifest_rows: list[dict[str, object]] = []
    seen_survivors: set[str] = set()
    for source in targets:
        duplicate_id = source["external_id"]
        survivor_id = source["live_duplicate_owner_external_ids"]
        reasons: list[str] = []
        if not survivor_id or "|" in survivor_id or survivor_id in duplicate_ids:
            reasons.append("owner_is_missing_ambiguous_or_in_collapse_chain")
        duplicate = live.get(duplicate_id, {"missing": True, "external_id": duplicate_id})
        survivor = live.get(survivor_id, {"missing": True, "external_id": survivor_id})
        reasons.extend(safe_noindex_state(duplicate, duplicate=True))
        reasons.extend(safe_noindex_state(survivor, duplicate=False))
        duplicate_categories = set(duplicate.get("categories") or [])
        survivor_categories = set(survivor.get("categories") or [])
        if not duplicate_categories.issubset(survivor_categories):
            reasons.append("survivor_does_not_preserve_duplicate_categories")
        if normalized(survivor.get("manufacturer")) != normalized("Delta"):
            reasons.append("survivor_manufacturer_mismatch")
        if normalized(survivor.get("mpn")) != normalized(source["mpn"]):
            reasons.append("survivor_mpn_mismatch")
        if normalized(source["source_offered_model"]) != normalized(source["mpn"]):
            reasons.append("official_exact_model_missing")
        if decimal(source["source_voltage_v"]) != decimal(source["title_voltage_v"]):
            reasons.append("official_voltage_mismatch")
        if decimal(source["source_capacity_ah"]) != decimal(source["title_capacity_ah"]):
            reasons.append("official_capacity_mismatch")
        snapshot_value = source["source_snapshot_path"].strip()
        snapshot = ROOT / snapshot_value if snapshot_value else ROOT / "__missing__"
        if not snapshot.is_file() or sha256(snapshot) != source["source_snapshot_sha256"].lower():
            reasons.append("official_snapshot_missing_or_sha_drift")
        if not source["source_url"].startswith("https://"):
            reasons.append("official_source_url_missing")
        if survivor_id in seen_survivors:
            reasons.append("survivor_reused_in_batch")
        if not reasons:
            seen_survivors.add(survivor_id)
            manifest_rows.append({
                "survivor_external_id": survivor_id,
                "duplicate_external_id": duplicate_id,
                "survivor_name": survivor["name"],
                "duplicate_name": duplicate["name"],
                "survivor_path": survivor["urls"][0]["path"],
                "duplicate_path": duplicate["urls"][0]["path"],
                "model_core": source["mpn"],
                "voltage": f"{source['title_voltage_v']}V",
                "capacity": f"{source['title_capacity_ah']}Ah",
                "availability": "on_request",
                "category_external_ids": survivor["categories"],
                "duplicate_category_external_ids": duplicate["categories"],
                "manufacturer": "Delta",
                "survivor_mpn": survivor["mpn"],
                "source_url": source["source_url"],
                "source_evidence_path": relative(SOURCE),
                "source_evidence_sha256": source_hash,
                "source_snapshot_path": snapshot_value,
                "source_snapshot_sha256": source["source_snapshot_sha256"].lower(),
                "decision_reason": "Wave242 exact official Delta model and electrical row matches the legacy title; the canonical live owner has the same normalized Delta MPN and preserves the market URL, content and commercial evidence.",
            })
        evidence_rows.append({
            "duplicate_external_id": duplicate_id,
            "duplicate_name": duplicate.get("name", ""),
            "survivor_external_id": survivor_id,
            "survivor_name": survivor.get("name", ""),
            "manufacturer": survivor.get("manufacturer", ""),
            "mpn": survivor.get("mpn", ""),
            "voltage_v": source["title_voltage_v"],
            "capacity_ah": source["title_capacity_ah"],
            "source_url": source["source_url"],
            "source_snapshot_path": snapshot_value,
            "source_snapshot_sha256": source["source_snapshot_sha256"],
            "duplicate_path": (duplicate.get("urls") or [{}])[0].get("path", ""),
            "survivor_path": (survivor.get("urls") or [{}])[0].get("path", ""),
            "duplicate_category_external_ids": "|".join(duplicate.get("categories") or []),
            "survivor_category_external_ids": "|".join(survivor.get("categories") or []),
            "survivor_price": survivor.get("price") or "",
            "survivor_current_price_evidence": len(survivor.get("current_price_evidence") or []),
            "decision": "PASS" if not reasons else "HOLD",
            "hold_reason": "|".join(sorted(set(reasons))),
        })

    if not manifest_rows:
        raise SystemExit("No exact safe duplicate collapse rows")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVIDENCE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(evidence_rows)
    manifest = {
        "schema_version": 1,
        "site_key": SITE_KEY,
        "purpose": "Collapse only Wave242 official-source exact Delta legacy duplicates into their existing canonical RB owner.",
        "duplicates": manifest_rows,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    decisions = Counter(row["decision"] for row in evidence_rows)
    summary = {
        "schema_version": 1,
        "wave": "wave243_delta_duplicate_collapse",
        "checked_at": "2026-07-29",
        "source": {"path": relative(SOURCE), "sha256": source_hash, "rows": len(source_rows)},
        "scope": {"duplicate_conflict_rows": len(targets), "unique_live_products_queried": len(live)},
        "result": {"decision_counts": dict(sorted(decisions.items())), "manifest_rows": len(manifest_rows)},
        "artifacts": {
            "evidence": {"path": relative(EVIDENCE), "sha256": sha256(EVIDENCE)},
            "manifest": {"path": relative(MANIFEST), "sha256": sha256(MANIFEST)},
        },
        "policy": {"official_exact_model_required": True, "exact_live_owner_required": True, "database_operations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
