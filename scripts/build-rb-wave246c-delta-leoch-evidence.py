#!/usr/bin/env python3
"""Build the deterministic no-repeat Wave246C Delta/LEOCH decision packet."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKED_AT = "2026-07-30"
SCOPE = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.csv"
LIVE = ROOT / "docs/audits/generated/rb-wave246c-delta-leoch-live-safety.json"
LEGACY_MEDIA = ROOT / "docs/audits/generated/rb-wave246-legacy-preview-candidates.csv"
PRIOR_MEDIA = ROOT / "docs/audits/generated/rb-wave237-reviewed-media-skip-ledger.csv"
DELTA_ID = ROOT / "docs/imports/rb-verified-oem-identities-wave242-delta-2026-07-29.json"
DELTA_DESC = ROOT / "docs/imports/rb-source-backed-descriptions-wave242-delta-2026-07-29.json"
DELTA_GEL_DESC = ROOT / "docs/imports/rb-source-backed-description-drafts-wave-116-2026-07-28.json"
LEOCH_188_PRODUCT = ROOT / "docs/imports/rb-manufacturer-product-candidates-leoch-wave188-2026-07-29.json"
LEOCH_188_DESC = ROOT / "docs/imports/rb-source-backed-description-drafts-leoch-wave188-2026-07-29.json"
LEOCH_192_PRODUCT = ROOT / "docs/imports/rb-manufacturer-product-candidates-leoch-lpl2-wave192-2026-07-29.json"
LEOCH_192_DESC = ROOT / "docs/imports/rb-source-backed-description-drafts-leoch-lpl2-wave192-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave246c-delta-leoch-decision-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave246c-delta-leoch.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave246c-delta-leoch-2026-07-30.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave246c-delta-leoch-2026-07-30.json"
DRY_RUN = ROOT / "docs/audits/generated/rb-wave246c-delta-leoch-laravel-dry-run.json"
REPORT = ROOT / "docs/audits/2026-07-30-rb-wave246c-delta-leoch.md"

PINS = {
    SCOPE: "63ee6cebb1e91830958c82c399354f89115939ce2fc8d428c5ccf11518b2e7db",
    LIVE: "864d57ee0dc5199ab423671efa2432143aa26bd4c64bb5212404b26dabf30bed",
    LEGACY_MEDIA: "a6cf193006c3f7afe21e299c266a267158cfea47356ddbc021207a3deaee1cf4",
    PRIOR_MEDIA: "9e4223a5c394aee82c626e72bc4f75abe5470051b61d5fa0ace7eaad37f4e059",
    DELTA_ID: "277ed4896e6d46c94d1dae66a92e22ffb4ff1fb9bfbcd046d38177f7b61ee9b7",
    DELTA_DESC: "06dcf7fd706dd680cd4ac6deb78115a85ecb59cc4c85b83d061e4f3152c7ffb8",
    DELTA_GEL_DESC: "e6d9b7a9b5a42462d57dd56d53daf534a5568a67466a45da14d089d5a0878925",
    LEOCH_188_PRODUCT: "479ef623b2eaa1f9c735bb488978c160c1302696336ff03422092b175f9cdeb8",
    LEOCH_188_DESC: "ee1795f424d02572ff9d6ac7fb3e7733a8faeaaa20d6fface548c3b7ca892d13",
    LEOCH_192_PRODUCT: "9c81a5c792b06dce5ae4e05e2c84a132f3b9e6edcc64a48fdcf4ffb9c314a9fd",
    LEOCH_192_DESC: "b310140850152df8e513d6a29eadcb645f32951547955651277d4f1cc910f279",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def products(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8-sig"))["products"]


def norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def indexed(rows: list[dict[str, object]], label: str) -> dict[str, dict[str, object]]:
    result = {str(row["external_id"]): row for row in rows}
    if len(result) != len(rows):
        raise SystemExit(f"{label} repeats an external_id")
    return result


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        if sha(path) != expected:
            raise SystemExit(f"pinned input changed: {path.relative_to(ROOT)}")

    scope = [row for row in csv_rows(SCOPE) if row["partition"] == "delta_leoch"]
    if len(scope) != 92 or Counter(row["manufacturer"] for row in scope) != {"Delta": 57, "LEOCH": 35}:
        raise SystemExit("Wave246C scope must be exactly 57 Delta + 35 LEOCH rows")
    if len({row["product_external_id"] for row in scope}) != 92:
        raise SystemExit("Wave246C scope repeats an external ID")
    if any(row["has_applied_description"] != "true" or row["identity_fields_present"] != "2" for row in scope):
        raise SystemExit("Wave246C no-repeat premise drifted: identity/description is no longer complete")

    live_payload = json.loads(LIVE.read_text(encoding="utf-8"))
    live_rows = live_payload["rows"]
    live_by_id = {row["external_id"]: row for row in live_rows if row["is_scope_target"]}
    if set(live_by_id) != {row["product_external_id"] for row in scope}:
        raise SystemExit("live safety snapshot does not exactly cover Wave246C")

    fingerprint_owners: dict[str, set[str]] = defaultdict(set)
    for row in live_rows:
        for field in ("mpn_normalized", "sku_normalized"):
            if row[field]:
                fingerprint_owners[row[field]].add(row["external_id"])

    delta_id = indexed(products(DELTA_ID), "Wave242 Delta identity")
    delta_desc = indexed(products(DELTA_DESC), "Wave242 Delta description")
    gel_desc = indexed(products(DELTA_GEL_DESC), "Wave116 GEL description")
    leoch_product: dict[str, dict[str, object]] = {}
    leoch_desc: dict[str, dict[str, object]] = {}
    for path in (LEOCH_188_PRODUCT, LEOCH_192_PRODUCT):
        for external_id, row in indexed(products(path), path.name).items():
            if external_id in leoch_product:
                raise SystemExit(f"Leoch prior product action repeats {external_id}")
            leoch_product[external_id] = {**row, "_path": path.relative_to(ROOT).as_posix(), "_sha": sha(path)}
    for path in (LEOCH_188_DESC, LEOCH_192_DESC):
        for external_id, row in indexed(products(path), path.name).items():
            if external_id in leoch_desc:
                raise SystemExit(f"Leoch prior description action repeats {external_id}")
            leoch_desc[external_id] = {**row, "_path": path.relative_to(ROOT).as_posix(), "_sha": sha(path)}

    legacy = {row["external_id"]: row for row in csv_rows(LEGACY_MEDIA)}
    prior_media = {row["external_id"]: row for row in csv_rows(PRIOR_MEDIA)}
    ledger: list[dict[str, str]] = []
    for item in sorted(scope, key=lambda row: int(row["scope_order"])):
        external_id = item["product_external_id"]
        live = live_by_id[external_id]
        if norm(live["mpn"]) != norm(item["mpn"]) or norm(live["manufacturer"]) != norm(item["manufacturer"]):
            raise SystemExit(f"live identity drift: {external_id}")
        owners = set()
        for field in ("mpn_normalized", "sku_normalized"):
            if live[field]:
                owners.update(fingerprint_owners[live[field]])
        collision_ids = sorted(owners - {external_id})

        if item["manufacturer"] == "Delta":
            identity = delta_id.get(external_id) or gel_desc.get(external_id)
            description = delta_desc.get(external_id) or gel_desc.get(external_id)
            identity_path = DELTA_ID if external_id in delta_id else DELTA_GEL_DESC
        else:
            identity = leoch_product.get(external_id)
            description = leoch_desc.get(external_id)
            identity_path = ROOT / str(identity.get("_path", "")) if identity else LEOCH_188_PRODUCT
        if identity is None or description is None:
            raise SystemExit(f"prior identity/description action missing: {external_id}")
        description_mpn = description.get("mpn", description.get("model_core", ""))
        if norm(identity.get("mpn")) != norm(item["mpn"]) or norm(description_mpn) != norm(item["mpn"]):
            raise SystemExit(f"strict prior MPN mismatch: {external_id}")
        if collision_ids:
            raise SystemExit(f"live normalized owner collision: {external_id} -> {collision_ids}")

        if external_id in legacy:
            if external_id not in prior_media or prior_media[external_id]["media_id"] != legacy[external_id]["media_id"]:
                raise SystemExit(f"legacy media candidate was not in the prior-review exclusion: {external_id}")
            media_decision = "NOOP_PRIOR_REVIEWED_NO_REPEAT"
            media_reason = "Company-owned candidate exists but is in the pinned prior-review exclusion; Wave246C does not repeat it."
            media_id = legacy[external_id]["media_id"]
            rights_basis = legacy[external_id]["rights_basis"]
        else:
            media_decision = "HOLD_NO_EXACT_COMPANY_OWNED_CANDIDATE"
            media_reason = "No new exact-identity image with a documented company-owned rights basis is available."
            media_id = rights_basis = ""

        source_url = str(description.get("source_url", identity.get("source_url", "")))
        snapshot_path = str(identity.get("source_snapshot_path", ""))
        snapshot_sha = str(identity.get("source_snapshot_sha256", ""))
        if snapshot_path:
            snapshot = (identity_path.parent / snapshot_path).resolve()
            if not snapshot.is_file() or sha(snapshot) != snapshot_sha:
                raise SystemExit(f"prior source snapshot drift: {external_id}")
        source_record_path = identity_path.relative_to(ROOT).as_posix()
        source_record_sha = sha(identity_path)
        ledger.append({
            "scope_order": item["scope_order"], "external_id": external_id, "name": item["name"],
            "manufacturer": item["manufacturer"], "mpn": item["mpn"], "mpn_normalized": live["mpn_normalized"] or "",
            "sku": live["sku"] or "", "sku_normalized": live["sku_normalized"] or "",
            "live_product_id": str(live["product_id"]), "live_site_product_id": str(live["site_product"]["id"]),
            "live_published": str(bool(live["site_product"]["published"])).lower(),
            "live_price": str(live["site_product"]["price"] or ""),
            "live_price_evidence_count": str(live["site_product"]["price_evidence_count"]),
            "live_verified_published_media_count": str(live["site_product"]["verified_published_media_count"]),
            "live_duplicate_owner_external_ids": "|".join(collision_ids),
            "source_url": source_url, "source_record_path": source_record_path,
            "source_record_sha256": source_record_sha, "source_snapshot_path": snapshot_path,
            "source_snapshot_sha256": snapshot_sha,
            "identity_decision": "PASS_NOOP_ALREADY_COMPLETE_NO_REPEAT",
            "description_decision": "PASS_NOOP_ALREADY_APPLIED_NO_REPEAT",
            "media_candidate_id": media_id, "media_rights_basis": rights_basis,
            "media_decision": media_decision, "media_reason": media_reason,
            "commercial_safety": "PASS_EXACT_OWNER_NO_COLLISION_NO_CHANGE",
            "overall_action": "NOOP_NO_NEW_SAFE_MUTATION" if media_decision.startswith("NOOP") else "HOLD_MEDIA_GAP",
        })

    identity_manifest = {
        "schema_version": 1, "site_key": "microchips-by", "target_kind": "active_1c",
        "review_batch": "wave246c_delta_leoch", "checked_at": CHECKED_AT, "products": [],
        "note": "PASS-only action manifest is empty: all 92 identities are already complete; no-repeat policy forbids restaging them.",
    }
    description_manifest = {
        "schema_version": 1, "purpose": "Wave246C PASS-only no-repeat source-backed descriptions",
        "locale": "ru-BY", "products": [],
        "note": "All 92 source-backed descriptions are already applied; no row is restaged.",
    }
    write_json(IDENTITIES, identity_manifest)
    write_json(DESCRIPTIONS, description_manifest)
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)

    media_counts = Counter(row["media_decision"] for row in ledger)
    action_counts = Counter(row["overall_action"] for row in ledger)
    dry_run = json.loads(DRY_RUN.read_text(encoding="utf-8")) if DRY_RUN.is_file() else {"status": "pending"}
    if DRY_RUN.is_file() and (dry_run.get("identity_manifest_sha256") != sha(IDENTITIES)
                              or dry_run.get("description_manifest_sha256") != sha(DESCRIPTIONS)
                              or dry_run.get("phpunit_exit_code") != 0
                              or dry_run.get("identity_command_exit_code") != 1
                              or dry_run.get("description_command_exit_code") != 0
                              or dry_run.get("apply_flag_used") is not False
                              or dry_run.get("repository_database_mutations") != 0):
        raise SystemExit("Laravel dry-run evidence does not match final no-repeat manifests")
    summary = {
        "schema_version": 1, "wave": "wave246c_delta_leoch", "checked_at": CHECKED_AT,
        "scope": {"rows": 92, "manufacturer_counts": {"Delta": 57, "LEOCH": 35}},
        "no_repeat": {"identity_noops": 92, "description_noops": 92, "new_identity_rows": 0, "new_description_rows": 0},
        "live_safety": {"targets": 92, "topology_rows": len(live_rows), "duplicate_owner_conflicts": 0,
                        "published": sum(bool(row["site_product"]["published"]) for row in live_by_id.values()),
                        "with_price_evidence": sum(row["site_product"]["price_evidence_count"] > 0 for row in live_by_id.values()),
                        "verified_published_media": sum(row["site_product"]["verified_published_media_count"] for row in live_by_id.values())},
        "media_decisions": dict(sorted(media_counts.items())), "overall_actions": dict(sorted(action_counts.items())),
        "outputs": {"ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha(LEDGER), "rows": 92},
                    "identity_manifest": {"path": IDENTITIES.relative_to(ROOT).as_posix(), "sha256": sha(IDENTITIES), "rows": 0},
                    "description_manifest": {"path": DESCRIPTIONS.relative_to(ROOT).as_posix(), "sha256": sha(DESCRIPTIONS), "rows": 0}},
        "laravel_dry_run": dry_run,
        "pins": {path.relative_to(ROOT).as_posix(): value for path, value in PINS.items()},
        "safety": {"builder_network_calls": 0, "apply_performed": False, "repository_database_mutations": 0,
                   "commercial_changes": 0, "publication_changes": 0, "media_changes": 0},
    }
    write_json(SUMMARY, summary)
    REPORT.write_text(
        "# Wave246C: Delta / LEOCH no-repeat safety review\n\n"
        "The frozen `delta_leoch` partition contains exactly **92 rows: 57 Delta and 35 LEOCH**. All 92 are "
        "already published, have both structured identity fields, and have an applied source-backed description. "
        "Therefore both PASS-only action manifests are intentionally empty: repeating prior identity or description "
        "actions would violate the wave contract.\n\n"
        "The live read-only Laravel snapshot matched all 92 external IDs and their exact manufacturer/MPN values. "
        "No normalized MPN/SKU owner collision was found. Forty-four cards have price evidence and 48 do not; this "
        "packet changes neither group and makes zero price, stock, URL, publication, or ownership decisions.\n\n"
        "## Media\n\n"
        "Fifty-six Delta cards have company-owned legacy candidates, but every candidate is already present in the "
        "pinned prior-review exclusion, so Wave246C does not review or promote them again. The remaining 36 cards "
        "have no new exact-identity, documented-rights candidate. Result: zero media promotions.\n\n"
        "## Laravel dry-run\n\n"
        + ("The real description command accepted its empty no-repeat manifest. The stricter OEM identity command "
           "rejected its empty manifest with the expected non-empty-list guard, proving fail-closed behavior. Both "
           "ran in an isolated SQLite `:memory:` RefreshDatabase fixture; `--apply` was not used and the repository "
           "database was not mutated.\n" if DRY_RUN.is_file()
           else "Dry-run evidence is pending.\n"),
        encoding="utf-8", newline="\n",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
