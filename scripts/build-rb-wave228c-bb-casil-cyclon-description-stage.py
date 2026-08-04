#!/usr/bin/env python3
"""Build strict official-source description refresh evidence for Wave228-C."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "docs/audits/generated/rb-full-content-readiness-wave227-after.csv"
BB_EVIDENCE = ROOT / "docs/audits/generated/rb-wave206-fiamm-bb-csb-evidence.csv"
CASIL_INDEX = ROOT / "docs/audits/sources/wave208s-stationary/snapshot-index.json"
ENERSYS_EVIDENCE = ROOT / "docs/audits/generated/rb-wave209a-official-evidence.csv"
ENERSYS_SOURCES = ROOT / "docs/audits/generated/rb-wave209a-official-source-registry.json"
MANIFEST = ROOT / "docs/imports/rb-source-backed-description-stageable-wave228c-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave228c-bb-casil-cyclon-description-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave228c-bb-casil-cyclon-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave228c-bb-casil-cyclon-description-stage.md"

PINS = {
    READINESS: "57fcb5e7f2f8b159001a707547025ddc8fd93e1e9576bfd67fc074eefed4dd6e",
    BB_EVIDENCE: "76821308633585012ffe6d08570d285728e3567f0ded16f168a2be021d5b52ff",
    CASIL_INDEX: "3b35a013fba75235ce7d06ff975275872be991771a29ecf2f44a7c5ca7595a48",
    ENERSYS_EVIDENCE: "5d093d66deddc3ad25858e918ccf1fa72a9087f78db42785632e8af5ffe62aa9",
    ENERSYS_SOURCES: "bc34c9169aa88bec5771ef02722e01cd666b50e778bbe75fae2646b6ca380149",
}

# The only Wave227 image-verified, no-description rows in this manufacturer slice.
TARGETS = (
    ("bitrix:1593", "B.B. Battery", "BPS40-12", "B.B. Battery BPS40-12", "bb"),
    ("bitrix:1519", "B.B. Battery", "HR15-12", "B.B. Battery HR15-12", "bb"),
    ("bitrix:1565", "B.B. Battery", "HR22-12", "B.B. Battery HR22-12", "bb"),
    ("bitrix:1587", "B.B. Battery", "HR4-12", "B.B. Battery HR4-12", "bb"),
    ("bitrix:1576", "Casil", "CA12260", "Casil CA12260", "casil"),
    ("bitrix:1473", "Casil", "CA6120", "Casil CA6120", "casil"),
    ("bitrix:1410", "Casil", "CA613", "Casil CA613", "casil"),
    ("bitrix:1555", "Casil", "CA628", "Casil CA628", "casil"),
    ("bitrix:1583", "Casil", "CA633", "Casil CA633", "casil"),
    ("bitrix:24554", "EnerSys", "0810-0075", "EnerSys Cyclon 0810-0075", "enersys"),
    ("bitrix:24531", "EnerSys", "0810-0103", "EnerSys Cyclon 0810-0103", "enersys"),
)
TECHNOLOGY = {
    "bb": "свинцово-кислотная аккумуляторная батарея",
    "casil": "свинцово-кислотная аккумуляторная батарея",
    "enersys": "AGM",
}
TECHNOLOGY_TOKEN = {
    "bb": "Lead Acid",
    "casil": "Lead Acid Battery",
    "enersys": "AGM",
}
LEDGER_FIELDS = (
    "external_id", "manufacturer", "model_core", "partition", "source_url", "source_kind",
    "source_publisher", "snapshot_path", "snapshot_sha256", "required_exact_tokens", "technology",
    "description_scope", "hold_reason", "stageable",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def exact_token_present(path: Path, token: str) -> bool:
    if path.suffix.casefold() == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return token.casefold() in text.casefold()


def name_contains_model_core(name: str, model_core: str) -> bool:
    expected = re.sub(r"[^A-Z0-9]", "", model_core.upper())
    tokens = re.findall(r"[A-Z0-9]+", name.upper())
    for start in range(len(tokens)):
        candidate = ""
        for token in tokens[start:]:
            candidate += token
            if candidate == expected:
                return True
            if len(candidate) >= len(expected):
                break
    return False


def source_record(target: tuple[str, str, str, str, str], bb: dict[str, dict[str, str]], casil: dict[str, dict], enersys: dict[str, dict[str, str]], enersys_sources: dict[str, dict]) -> dict[str, str]:
    external_id, manufacturer, mpn, display_name, family = target
    if family == "bb":
        row = bb.get(external_id)
        require(row is not None and row["partition"] == "exact" and row["safe_to_apply"] == "true", f"B.B. evidence missing: {external_id}")
        require(row["replacement_manufacturer"] == manufacturer and row["replacement_mpn"] == mpn, f"B.B. identity drift: {external_id}")
        path = ROOT / row["snapshot_path"]
        return {"url": row["source_url"], "kind": "official_manufacturer_catalogue", "publisher": manufacturer, "path": path.as_posix(), "sha": row["snapshot_sha256"], "model_token": row["required_tokens"]}
    if family == "casil":
        row = casil.get(external_id)
        require(row is not None and row["manufacturer"] == manufacturer and row["model"] == mpn, f"Casil evidence missing: {external_id}")
        path = ROOT / row["snapshot_path"]
        return {"url": row["source_url"], "kind": row["source_kind"], "publisher": row["publisher"], "path": path.as_posix(), "sha": row["snapshot_sha256"], "model_token": mpn}
    row = enersys.get(external_id)
    require(row is not None and row["partition"] == "exact_safe" and row["model_token"] == mpn, f"EnerSys evidence missing: {external_id}")
    source = enersys_sources.get("enersys-cyclon-selection-guide.pdf")
    require(source is not None and source["source_url"] == row["source_url"] and source["sha256"] == row["source_snapshot_sha256"], f"EnerSys source registry drift: {external_id}")
    path = ROOT / "docs/audits/sources/wave209a/enersys-cyclon-selection-guide.pdf"
    return {"url": row["source_url"], "kind": "official_manufacturer_catalogue", "publisher": "EnerSys", "path": path.as_posix(), "sha": row["source_snapshot_sha256"], "model_token": mpn}


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(sha256(path) == expected, f"review evidence drift: {path.relative_to(ROOT)}")
    require(len(TARGETS) == len(set(TARGETS)) == 11, "frozen Wave228-C target drift")

    readiness = {row["product_external_id"]: row for row in read_csv(READINESS)}
    image_without_description = [row for row in readiness.values() if row["has_verified_published_image"] == "true" and row["has_applied_description"] == "false"]
    require(len(image_without_description) == 52, "Wave227 image-verified/no-description denominator drift")
    target_ids = {row[0] for row in TARGETS}
    require(set(target_ids) <= {row["product_external_id"] for row in image_without_description}, "Wave228-C target is outside Wave227 image-verified/no-description scope")
    require(Counter(readiness[row[0]]["manufacturer"] for row in TARGETS) == {"B.B. Battery": 4, "Casil": 5, "EnerSys": 2}, "Wave228-C manufacturer scope drift")
    for external_id, manufacturer, mpn, _, _ in TARGETS:
        row = readiness[external_id]
        require(row["manufacturer"] == manufacturer and row["mpn"] == mpn, f"Wave227 identity drift: {external_id}")
        require(name_contains_model_core(row["name"], mpn), f"Wave227 name lacks model-core boundaries: {external_id}")

    bb = {row["product_external_id"]: row for row in read_csv(BB_EVIDENCE)}
    casil_index = json.loads(CASIL_INDEX.read_text(encoding="utf-8"))
    casil = {row["external_id"]: row for row in casil_index["sources"]}
    enersys = {row["product_external_id"]: row for row in read_csv(ENERSYS_EVIDENCE)}
    enersys_sources = {row["filename"]: row for row in json.loads(ENERSYS_SOURCES.read_text(encoding="utf-8"))}

    manifest_rows: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for target in TARGETS:
        external_id, manufacturer, mpn, _display_name, family = target
        source = source_record(target, bb, casil, enersys, enersys_sources)
        snapshot = Path(source["path"])
        require(snapshot.is_file() and sha256(snapshot) == source["sha"], f"snapshot hash drift: {external_id}")
        require(source["url"].startswith("https://"), f"non-HTTPS official source: {external_id}")
        require(exact_token_present(snapshot, source["model_token"]), f"exact MPN missing from snapshot: {external_id}")
        require(exact_token_present(snapshot, TECHNOLOGY_TOKEN[family]), f"conservative technology token missing from snapshot: {external_id}")
        technology = TECHNOLOGY[family]
        manifest_rows.append({
            "external_id": external_id,
            "identity_scope": "model_core",
            "manufacturer": manufacturer,
            "model_core": mpn,
            "technology": technology,
            "source_url": source["url"],
            "technical_attributes": {"Технология": technology},
            "source_kind": source["kind"],
            "source_tier": "manufacturer_primary",
            "source_publisher": source["publisher"],
            "manufacturer_primary": True,
            "evidence_scope": "model_core",
            "checked_at": "2026-07-29",
        })
        ledger.append({
            "external_id": external_id,
            "manufacturer": manufacturer,
            "model_core": mpn,
            "partition": "exact_official_source_model_core_stageable",
            "source_url": source["url"],
            "source_kind": source["kind"],
            "source_publisher": source["publisher"],
            "snapshot_path": str(snapshot.relative_to(ROOT)).replace("\\", "/"),
            "snapshot_sha256": source["sha"],
            "required_exact_tokens": f"{source['model_token']}|{TECHNOLOGY_TOKEN[family]}",
            "technology": technology,
            "description_scope": "bounded_model_core_and_technology_only",
            "hold_reason": "",
            "stageable": "true",
        })

    require(len(manifest_rows) == 11 == len({row["external_id"] for row in manifest_rows}), "Wave228-C manifest cardinality drift")
    require(len({row["model_core"].casefold() for row in manifest_rows}) == 11, "Wave228-C model-core uniqueness drift")
    MANIFEST.write_text(json.dumps({
        "schema_version": 1,
        "purpose": "Wave228-C strict official-source model-core description refresh candidates only; use with --refresh-existing --refresh-applied after review.",
        "locale": "ru-BY",
        "products": manifest_rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(ledger)
    summary = {
        "schema_version": 1,
        "wave": "wave228c_bb_casil_cyclon_description_stage",
        "target_rows": len(TARGETS),
        "wave227_image_verified_no_description_denominator": len(image_without_description),
        "manufacturer_counts": dict(Counter(row["manufacturer"] for row in manifest_rows)),
        "inputs": {str(path.relative_to(ROOT)).replace("\\", "/"): digest for path, digest in PINS.items()},
        "stage_command": "content:stage-source-backed-description-drafts microchips-by docs/imports/rb-source-backed-description-stageable-wave228c-2026-07-29.json --refresh-existing --refresh-applied",
        "manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": sha256(MANIFEST),
        "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"),
        "ledger_sha256": sha256(LEDGER),
        "database_apply": False,
        "publication_changes": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave228-C: strict B.B. Battery, Casil and EnerSys Cyclon description refresh\n\n"
        "The Wave227 readiness snapshot contains 52 image-verified products without an applied description. "
        "This frozen slice contains exactly 11: four B.B. Battery, five Casil and two EnerSys Cyclon products.\n\n"
        "- Every candidate has an exact source MPN token, HTTPS first-party URL, SHA-256-pinned local snapshot and a conservative technology-only attribute.\n"
        "- B.B. Battery uses existing manufacturer series snapshots; Casil uses existing exact manufacturer product-page snapshots; EnerSys Cyclon uses the existing official selection-guide snapshot.\n"
        "- The stage manifest deliberately omits snapshot fields because the Laravel source-evidence contract rejects them; the companion ledger retains each path and hash.\n"
        "- The DB catalogue names retain technical suffixes after the exact model token, so the Laravel exact-MPN end-of-name rule rejects them. The stage contract therefore uses bounded manufacturer-primary `model_core` evidence, not an exact MPN or display-name claim. All 11 currently have `legacy_preview_applied` drafts. This is a strict source upgrade candidate for `--refresh-existing --refresh-applied`; this builder did not run that command, apply a database change, publish content, or alter commercial/media data.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
