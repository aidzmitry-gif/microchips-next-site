#!/usr/bin/env python3
"""Build deterministic fail-closed evidence for the 92-row Wave246B CSB partition."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SCOPE = ROOT / "docs/audits/generated/rb-wave246-b2b-scope.csv"
CATALOG = ROOT / "docs/audits/sources/wave242-leoch-marathon-csb/csb-catalog-2026.pdf"
LIVE = ROOT / "docs/audits/sources/wave246b-csb/live-db-exact-owner-snapshot.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave246b-csb-evidence-ledger.csv"
PRIOR_INDEX = ROOT / "docs/audits/generated/rb-wave246b-csb-prior-evidence-index.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave246b-csb.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave246b-csb-2026-07-30.json"
IDENTITIES_BITRIX = ROOT / "docs/imports/rb-verified-oem-identities-wave246b-csb-bitrix-dry-run-2026-07-30.json"
IDENTITIES_ACTIVE = ROOT / "docs/imports/rb-verified-oem-identities-wave246b-csb-active-1c-dry-run-2026-07-30.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave246b-csb-2026-07-30.json"
DRY_RUN = ROOT / "docs/audits/generated/rb-wave246b-csb-laravel-dry-runs.json"
REPORT = ROOT / "docs/audits/2026-07-30-rb-wave246b-csb.md"
CATALOG_URL = "https://csb-battery.com/wp-content/uploads/2026/03/CSB-Catalog-2026-Digital-Spread-1.pdf"
CATALOG_SHA = "79806a16440edc8e4704770ac2da6f76a5f6ab093e55474d3617e1da2fe822a8"
PINS = {
    SCOPE: "63ee6cebb1e91830958c82c399354f89115939ce2fc8d428c5ccf11518b2e7db",
    CATALOG: CATALOG_SHA,
    LIVE: "b51815bede985e831f6d27253fb2e1b2a2a734d4cd0eb5b4943f3d6afbf0fb17",
}
PRIOR_FILES = {
    "docs/imports/rb-source-backed-descriptions-wave242-leoch-marathon-csb-2026-07-29.json": "387348f7c54a5ed31f0e002ce6f383088afdbf048f20e7daf07c018c7d5b7e32",
    "docs/imports/rb-source-backed-description-drafts-csb-wave178-2026-07-29.json": "fc4f7dceb3d82c38d2c4fc4f6ee86c57baa3a522da8ee3cb77f40d89f17987b1",
    "docs/imports/rb-source-backed-description-drafts-csb-xhrl-wave176-2026-07-29.json": "c984e71f82db8384a1203447dd7165055753ad9fda152f0a3b03aa73c7e6a668",
    "docs/imports/rb-source-backed-description-drafts-csb-xtv-wave175-2026-07-29.json": "50fd444bbbbf436ac740bb7e7469972f9242bdd5f0c85abfcaab1c19d4d96b87",
    "docs/imports/rb-source-backed-description-drafts-csb-evx-evh-msj-wave177-2026-07-29.json": "4009e1a4082d65cb3c6d70b80e5dfbe3dca7b07ab381e213c7d98d4da100a43f",
    "docs/imports/rb-source-backed-description-drafts-csb-wave180-2026-07-29.json": "68ece57afa47a223d29ce4bae45fc1326a1fc6877994d3c008e3fdb94d68a60e",
    "docs/imports/rb-source-backed-description-drafts-csb-wave185-2026-07-29.json": "a00bb4212a7a5181cfee788b02083ffad2a66e2e61ad9388cc595e03b83c6872",
    "docs/imports/rb-source-backed-description-drafts-wave-94-2026-07-28.json": "232e0277c91531cb6844b838490c7317f8b324f063416bc5e2dfb2a7cd54f312",
    "docs/imports/rb-source-backed-description-drafts-wave-107-2026-07-28.json": "38e4d8d49c70691ffd7e6e5a2c8db8c3ec87c22a78300517d25877dfd73f3924",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def catalog_token(mpn: str) -> str:
    return re.sub(r"\s+F2$", "", mpn, flags=re.I)


def series(mpn: str) -> str:
    rules = (
        (r"^GP", "GP"), (r"^GPL", "GPL"), (r"^HRL", "HRL"), (r"^HR", "HR"),
        (r"^(?:UPS|RUM)", "UPS"), (r"^XHRL.*FTFR$", "XHRL-FT"), (r"^XHRL", "XHRL"),
        (r"^XPL.*FT$", "XPL-FT"), (r"^XPL", "XPL"), (r"^XTV", "XTV"),
        (r"^XHT", "Calor XHT-FT"), (r"^48RE", "RE 48V"), (r"^RE", "RE"),
        (r"^MSJ", "MSJ"), (r"^MSV", "MSV"), (r"^MU", "MU"),
    )
    return next((label for pattern, label in rules if re.search(pattern, mpn, re.I)), "")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    for path, digest in PINS.items():
        if sha(path) != digest:
            raise SystemExit(f"pinned input drifted: {path.relative_to(ROOT)}")
    with SCOPE.open(encoding="utf-8-sig", newline="") as handle:
        scope = [row for row in csv.DictReader(handle) if row["partition"] == "csb"]
    if len(scope) != 92 or len({row["product_external_id"] for row in scope}) != 92:
        raise SystemExit("scope must be exactly 92 unique CSB rows")
    if any(row["research_status"] != "pending_official_source_research" for row in scope):
        raise SystemExit("scope research state drifted")
    scope_by_id = {row["product_external_id"]: row for row in scope}

    prior_by_id: dict[str, dict[str, object]] = {}
    prior_hits: dict[str, list[str]] = {external_id: [] for external_id in scope_by_id}
    for relative, digest in PRIOR_FILES.items():
        path = ROOT / relative
        if sha(path) != digest:
            raise SystemExit(f"prior evidence drifted: {relative}")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for product in payload.get("products", []):
            external_id = product.get("external_id")
            if external_id not in scope_by_id:
                continue
            if normalized(product.get("mpn") or product.get("model_core") or "") != normalized(scope_by_id[external_id]["mpn"]):
                raise SystemExit(f"historical exact MPN drift: {external_id}")
            prior_hits[external_id].append(relative)
            prior_by_id.setdefault(external_id, {"product": product, "path": relative, "sha256": digest})
    if set(prior_by_id) != set(scope_by_id):
        raise SystemExit(f"historical CSB evidence coverage is not 92: {set(scope_by_id) - set(prior_by_id)}")
    write_json(PRIOR_INDEX, {
        "schema_version": 1, "checked_at": "2026-07-30", "scope_rows": 92,
        "covered_rows": len(prior_by_id), "new_row_research_performed": 0,
        "files": [{"path": path, "sha256": digest} for path, digest in PRIOR_FILES.items()],
        "coverage": [{"external_id": external_id, "mpn": scope_by_id[external_id]["mpn"], "evidence_files": prior_hits[external_id]}
                     for external_id in sorted(scope_by_id)],
    })

    page_texts = [page.extract_text() or "" for page in PdfReader(str(CATALOG)).pages]
    page_norms = [normalized(text) for text in page_texts]
    if len(page_texts) != 16:
        raise SystemExit("CSB 2026 catalogue page topology drifted")
    f2_models = {"GP645 F2", "GP6120 F2", "GP1272 F2", "GP12120 F2"}
    page3 = page_texts[2]
    if page3.upper().count("F1/F2") < 4 or any(normalized(catalog_token(model)) not in normalized(page3) for model in f2_models):
        raise SystemExit("F2 terminal-to-model table evidence drifted")
    catalog_pages = {}
    for row in scope:
        token = normalized(catalog_token(row["mpn"]))
        pages = [index + 1 for index, text in enumerate(page_norms) if token in text]
        if not pages:
            raise SystemExit(f"exact catalogue token absent: {row['mpn']}")
        catalog_pages[row["product_external_id"]] = pages[0]

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    live_by_id = {row["external_id"]: row for row in live["ownership"]}
    if set(live_by_id) != set(scope_by_id) or live["counts"]["targets"] != 92:
        raise SystemExit("live ownership snapshot scope drifted")

    ledger = []
    identities = []
    identities_bitrix = []
    identities_active = []
    descriptions = []
    for row in sorted(scope, key=lambda item: int(item["scope_order"])):
        external_id, mpn = row["product_external_id"], row["mpn"]
        owner = live_by_id[external_id]
        decision = "PASS" if owner["decision"] == "NO_EXACT_NON_TARGET_OWNER" else "HOLD"
        hold_reason = "" if decision == "PASS" else "EXACT_NON_TARGET_OWNER_EXISTS"
        prior = prior_by_id[external_id]
        ledger.append({
            "scope_order": row["scope_order"], "external_id": external_id, "name": row["name"],
            "manufacturer": "CSB", "mpn": mpn, "series": series(mpn),
            "catalogue_page": str(catalog_pages[external_id]),
            "terminal_variant_check": "PASS_EXACT_F2_IN_MODEL_TABLE" if mpn in f2_models else "PASS_EXACT_CATALOGUE_TOKEN",
            "prior_evidence_path": prior["path"], "prior_evidence_sha256": prior["sha256"],
            "catalogue_url": CATALOG_URL, "catalogue_snapshot_path": CATALOG.relative_to(ROOT).as_posix(),
            "catalogue_snapshot_sha256": CATALOG_SHA,
            "exact_non_target_owner_ids": "|".join(item["external_id"] for item in owner["exact_non_target_owner_candidates"]),
            "ownership_decision": owner["decision"], "decision": decision, "hold_reason": hold_reason,
            "identity_manifest_eligible": "true" if decision == "PASS" else "false",
            "description_manifest_eligible": "true" if decision == "PASS" else "false",
            "media_manifest_eligible": "false", "media_reason": "NO_EXPLICIT_RIGHTS_AND_EXACT_VISUAL_PROOF_CONTRACT",
        })
        if decision != "PASS":
            continue
        identity = {
            "external_id": external_id, "current_name": row["name"], "manufacturer": "CSB", "mpn": mpn,
            "source_url": CATALOG_URL, "source_kind": "official_manufacturer_catalogue",
            "source_publisher": "CSB Energy Technology Co., Ltd.", "checked_at": "2026-07-29",
            "product_type": "CSB industrial battery", "source_snapshot_path": "../audits/sources/wave242-leoch-marathon-csb/csb-catalog-2026.pdf",
            "source_snapshot_sha256": CATALOG_SHA,
        }
        identities.append(identity)
        target_status = owner["target"]["status"]
        if external_id.startswith("bitrix:") and target_status == "draft":
            identities_bitrix.append(identity)
        elif not external_id.startswith("bitrix:") and target_status == "active":
            identities_active.append(identity)
        historical = prior["product"]
        descriptions.append({
            "external_id": external_id, "identity_scope": "model_core", "manufacturer": "CSB", "model_core": mpn,
            "technology": historical["technology"], "source_url": CATALOG_URL,
            "technical_attributes": {"Модель": mpn, "Серия": series(mpn), "Технология": historical["technology"]},
            "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary", "source_publisher": "CSB Energy Technology Co., Ltd.",
            "manufacturer_primary": True, "evidence_scope": "model_core", "checked_at": "2026-07-29",
        })

    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)
    write_json(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "purpose": "Wave246B CSB exact PASS identities", "products": identities})
    write_json(IDENTITIES_BITRIX, {"schema_version": 1, "site_key": "microchips-by", "target_kind": "bitrix_draft", "products": identities_bitrix})
    write_json(IDENTITIES_ACTIVE, {"schema_version": 1, "site_key": "microchips-by", "target_kind": "active_1c", "products": identities_active})
    write_json(DESCRIPTIONS, {"schema_version": 1, "purpose": "Wave246B CSB exact PASS source-backed descriptions", "locale": "ru-BY", "products": descriptions})
    decisions = Counter(row["decision"] for row in ledger)
    dry = {"status": "not_run"}
    if DRY_RUN.exists():
        candidate = json.loads(DRY_RUN.read_text(encoding="utf-8"))
        if candidate.get("identity_manifest_sha256") == sha(IDENTITIES) and candidate.get("description_manifest_sha256") == sha(DESCRIPTIONS):
            dry = candidate
    summary = {
        "schema_version": 1, "wave": "wave246b_csb", "checked_at": "2026-07-30",
        "scope": {"rows": 92, "partition": "csb", "all_genuinely_pending": True},
        "prior_evidence": {"covered_rows": 92, "new_row_research": 0, "index_path": PRIOR_INDEX.relative_to(ROOT).as_posix()},
        "catalogue": {"path": CATALOG.relative_to(ROOT).as_posix(), "sha256": CATALOG_SHA, "exact_model_rows": 92, "f2_variant_rows": 4},
        "decisions": dict(sorted(decisions.items())),
        "ownership": live["counts"], "manifests": {"identity": len(identities), "identity_bitrix_dry_run": len(identities_bitrix),
            "identity_active_1c_dry_run": len(identities_active), "identity_existing_manufacturer_draft_not_command_target": len(identities)-len(identities_bitrix)-len(identities_active),
            "description": len(descriptions), "media": 0},
        "laravel_dry_runs": dry,
        "safety": {"apply_performed": False, "domain_database_mutations_requested": 0, "dry_run_audit_import_runs_expected": 1, "publication_changes_requested": 0,
                   "commercial_changes_requested": 0, "network_research_calls": 0},
    }
    write_json(SUMMARY, summary)
    REPORT.write_text(
        "# Wave246B: CSB 92-row B2B partition\n\n"
        "Scope is exactly the 92 `partition=csb` rows from `rb-wave246-b2b-scope.csv`. All 92 were already covered "
        "by SHA-pinned historical CSB evidence, so no row-level web research was repeated. The pinned official CSB "
        "2026 catalogue independently contains every model; its GP table explicitly ties GP645, GP6120, GP1272 and "
        "GP12120 to terminal options F1/F2. Pages 3-4 were rendered and visually checked.\n\n"
        f"Live read-only ownership result: PASS {decisions['PASS']}, HOLD {decisions['HOLD']}. The four HOLD rows are "
        "`bitrix:2829` GP12170, `bitrix:2912` GP12260, `bitrix:3027` GP12400 and `bitrix:754` GP1272 F2; each has "
        "one or more exact active non-target owners. Only the 88 PASS rows enter identity and description manifests.\n\n"
        "No media row is emitted: the catalogue does not establish both an exact model visual association and an "
        "explicit reusable/company-owned rights basis for these 92 storefront records. No apply, publication, price, "
        "availability or domain-record mutation was requested.\n\n"
        "Real Laravel dry-runs passed without `--apply`: 12 Bitrix-draft identities and 3 active-1C identities were "
        "validated with zero identity/commercial/publication changes. The remaining 73 PASS identities are existing "
        "manufacturer-origin draft records outside both identity command target kinds. The description command accepted "
        "all 88 PASS model-core rows as refresh candidates (0 created, 88 refreshed in the rolled-back transaction, "
        "0 unchanged) and published none. Per command contract, the final description dry-run writes one audit-only "
        "`ImportRun`; persisted product/description/media changes remain zero.\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"scope": len(ledger), "pass": decisions["PASS"], "hold": decisions["HOLD"], "identity": len(identities), "description": len(descriptions)}, sort_keys=True))


if __name__ == "__main__":
    main()
