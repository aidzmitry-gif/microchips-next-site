#!/usr/bin/env python3
"""Build Wave241 descriptions from already pinned manufacturer-primary sources."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave240.csv"
MANIFEST = ROOT / "docs/imports/rb-source-backed-descriptions-wave241-2026-07-29.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave241-source-backed-descriptions-ledger.csv"
SUMMARY = ROOT / "docs/audits/generated/rb-wave241-source-backed-descriptions.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave241-source-backed-descriptions.md"

CHECKED_AT = "2026-07-29"
QUEUE_SHA256 = "ab23b26e4f5b7f4561ca69fefaa22615ed19bc8c17a234e923b16b56c5980f4c"

IDENTITY_REGISTRIES = {
    "rb-verified-oem-identities-wave206-panasonic-ventura-mnb-2026-07-29.json":
        "73bfc5abd4649ec4b2c5982ee78b2508f3ce1e0fc9d8ca2cf7af7d9421dd6d0a",
    "rb-verified-oem-identities-wave209a-2026-07-29.json":
        "ae1cced58e0b29937e0cbb0ee64e77447c7100d9051c26b61cc645c789070467",
    "rb-verified-oem-identities-wave209c-stationary-2026-07-29.json":
        "0034afde9010c292f9c5175916ea6849014c774560eb40d755f7a1ab14c65415",
    "rb-verified-oem-identities-wave211c-stationary-2026-07-29.json":
        "b442052924f95e3782640680e51d2311b7789f43c14d2dc471e4e3aa85cca95e",
}

PRIOR_DESCRIPTION_MANIFESTS = {
    "rb-source-backed-description-evidence-wave228a-2026-07-29.json": "8c98e26a4b2a611aaa266b185e5d40b55de18c21e7675719cfb9b5052f7e74c6",
    "rb-source-backed-description-stageable-wave228c-2026-07-29.json": "36602c6ee2bf273aefc5edc5d8848e779fcf82a7a2aeb0884ca952dfa9f48945",
    "rb-source-backed-description-stage-manifest-wave228a-2026-07-29.json": "b6c23c518fbe8318e2e958236be85c628f081c877845e5db404c64f4c4761e55",
    "rb-source-backed-description-stage-manifest-wave228b-2026-07-29.json": "9a63f259bf7bf162e6d3872efdad1a31f4317b7c2792b44e7098540e45220cdb",
    "rb-source-backed-description-stage-manifest-wave230-2026-07-29.json": "d47c5dddb82d0c479e526f550ad0816bd094cf4f5cb63070bda75038d9e5cbbb",
    "rb-source-backed-description-stage-manifest-wave230a-2026-07-29.json": "3d49e4f427250e5e7d76eca9741d93d95d2f8f35d49156a3190f51d68bde3f3e",
    "rb-source-backed-description-stage-manifest-wave230b-2026-07-29.json": "686db4619aa01c5bd756e8f193e67f743abddd474c8b8276b7a207bb9ca942ad",
    "rb-source-backed-description-stage-manifest-wave230c-2026-07-29.json": "17e488a8465be81f0397cc3fbfc12f3863ef3779ab2ff6b0b2cde24a35ea8a1c",
    "rb-source-backed-description-stage-manifest-wave231c-2026-07-29.json": "6be11e030a314ebe862125763ec1e9fcf86eb29cc183d86895db08368e264a5f",
    "rb-source-backed-descriptions-wave232g-2026-07-29.json": "14fa3f5616b7e050373875fea68969151cc98773b143ad86b4eec7986aa5cb5b",
    "rb-source-backed-descriptions-wave233e-delta-2026-07-29.json": "4a94ba4b8b680af364374c051a88a25be14cf619b5cfdb77e1150a187ed59756",
    "rb-source-backed-descriptions-wave234d-general-security-2026-07-29.json": "5a53081e3c89023a0f4c2722deabf96c497fb02e92a4c371591191e1e248b508",
    "rb-source-backed-descriptions-wave236-verified-media-2026-07-29.json": "ebc0c4f51ba1a80591e47a8a06940839a9d1470064aaf713de60e1d989219b05",
    "rb-source-backed-descriptions-wave239-fiamm-2026-07-29.json": "8fcfeacfe40e85976d5f4367beb3444fb32f494ab4c87332ba5e8527d914a830",
}

LEDGER_FIELDS = (
    "external_id", "manufacturer", "mpn", "identity_registry", "identity_registry_sha256",
    "source_url", "source_kind", "source_publisher", "source_snapshot_path",
    "source_snapshot_sha256", "source_exact_model_present", "technology", "source_technology_present",
    "prior_description_manifest_hits",
    "decision", "hold_reason",
)

APC_TECHNOLOGY = {
    "RBC17": "lead-acid",
    "RBC14": "lead-acid",
    "RBC9": "lead-acid",
    "RBC40": "lead-acid",
    "RBC24": "lead-acid",
}


def verified_technology(manufacturer: str, mpn: str) -> str:
    """Return only a technology established by the pinned primary source/series."""
    if manufacturer == "Panasonic":
        return "VRLA AGM"
    if manufacturer == "MNB":
        if mpn.startswith("MNG "):
            return "VRLA GEL"
        if mpn.startswith(("MM ", "MR ")):
            return "VRLA AGM"
    if manufacturer == "Ventura" and mpn.startswith(("GP ", "GPL ", "HRL ")):
        return "VRLA AGM"
    if manufacturer == "Sonnenschein":
        return "GEL"
    if manufacturer == "APC" and mpn in APC_TECHNOLOGY:
        return APC_TECHNOLOGY[mpn]
    if manufacturer == "EnerSys":
        return "AGM"
    raise SystemExit(f"Wave241 has no pinned technology rule for {manufacturer} {mpn}")


def technology_markers(technology: str) -> tuple[str, ...]:
    if technology == "VRLA lead-acid":
        return ("VRLA", "LEADACID")
    if technology == "lead-acid":
        return ("LEADACID",)
    if "GEL" in technology:
        return ("GEL",)
    if "AGM" in technology:
        return ("AGM",)
    raise SystemExit(f"Wave241 has no source marker rule for technology {technology}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def compact(value: str) -> str:
    return re.sub(r"[^0-9A-ZА-Я]", "", value.upper())


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def source_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    if path.suffix.lower() in {".html", ".htm"}:
        return BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser").get_text(" ", strip=True)
    return path.read_text(encoding="utf-8", errors="replace")


def resolve_snapshot(registry_path: Path, relative: str) -> Path:
    path = (registry_path.parent / relative).resolve()
    require(path.is_relative_to(ROOT), f"source snapshot escapes repository: {relative}")
    require(path.is_file(), f"source snapshot missing: {path.relative_to(ROOT)}")
    return path


def build() -> dict[str, object]:
    require(sha256(QUEUE) == QUEUE_SHA256, "Wave240 queue pin drift")
    scope_rows = [
        row for row in read_csv(QUEUE)
        if row["has_applied_description"] == "false" and row["manufacturer"].strip() and row["mpn"].strip()
    ]
    require(len(scope_rows) == 44, f"Wave241 scope drift: {len(scope_rows)}")
    scope = {row["product_external_id"]: row for row in scope_rows}
    require(len(scope) == 44, "Wave241 scope contains duplicate external IDs")

    prior_ids: set[str] = set()
    prior_rows = 0
    prior_pins: dict[str, str] = {}
    for name, expected in PRIOR_DESCRIPTION_MANIFESTS.items():
        path = ROOT / "docs/imports" / name
        require(sha256(path) == expected, f"prior description manifest pin drift: {name}")
        products = json.loads(path.read_text(encoding="utf-8"))["products"]
        prior_rows += len(products)
        prior_ids.update(str(row["external_id"]) for row in products)
        prior_pins[path.relative_to(ROOT).as_posix()] = expected
    require(not (set(scope) & prior_ids), "Wave241 target already exists in a Wave228-239 description manifest")

    identities: dict[str, tuple[dict[str, object], Path, str]] = {}
    identity_pins: dict[str, str] = {}
    for name, expected in IDENTITY_REGISTRIES.items():
        path = ROOT / "docs/imports" / name
        require(sha256(path) == expected, f"identity registry pin drift: {name}")
        identity_pins[path.relative_to(ROOT).as_posix()] = expected
        for row in json.loads(path.read_text(encoding="utf-8"))["products"]:
            external_id = str(row.get("external_id", ""))
            if external_id not in scope:
                continue
            require(external_id not in identities, f"duplicate identity registry coverage: {external_id}")
            identities[external_id] = (row, path, expected)
    require(set(identities) == set(scope), f"identity registry coverage drift: {sorted(set(scope) ^ set(identities))}")

    text_cache: dict[Path, str] = {}
    products: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for external_id in sorted(scope):
        queue_row = scope[external_id]
        identity, registry_path, registry_sha = identities[external_id]
        require(identity["manufacturer"] == queue_row["manufacturer"], f"manufacturer drift: {external_id}")
        require(identity["mpn"] == queue_row["mpn"], f"MPN drift: {external_id}")
        require(identity["source_kind"] in {"official_manufacturer_catalogue", "official_manufacturer_product_page"},
                f"non-primary source kind: {external_id}")
        snapshot = resolve_snapshot(registry_path, str(identity["source_snapshot_path"]))
        require(sha256(snapshot) == identity["source_snapshot_sha256"], f"source snapshot pin drift: {external_id}")
        if snapshot not in text_cache:
            text_cache[snapshot] = compact(source_text(snapshot))
        exact_present = compact(str(identity["mpn"])) in text_cache[snapshot]
        technology = verified_technology(str(identity["manufacturer"]), str(identity["mpn"]))
        technology_present = all(marker in text_cache[snapshot] for marker in technology_markers(technology))
        decision = "PASS" if exact_present and technology_present else "HOLD"
        hold_reason = ""
        if not exact_present:
            hold_reason = "exact_mpn_absent_from_pinned_manufacturer_primary_snapshot"
        elif not technology_present:
            hold_reason = "technology_absent_from_pinned_manufacturer_primary_snapshot"
        ledger.append({
            "external_id": external_id,
            "manufacturer": str(identity["manufacturer"]),
            "mpn": str(identity["mpn"]),
            "identity_registry": registry_path.relative_to(ROOT).as_posix(),
            "identity_registry_sha256": registry_sha,
            "source_url": str(identity["source_url"]),
            "source_kind": str(identity["source_kind"]),
            "source_publisher": str(identity["source_publisher"]),
            "source_snapshot_path": snapshot.relative_to(ROOT).as_posix(),
            "source_snapshot_sha256": str(identity["source_snapshot_sha256"]),
            "source_exact_model_present": str(exact_present).lower(),
            "technology": technology,
            "source_technology_present": str(technology_present).lower(),
            "prior_description_manifest_hits": "0",
            "decision": decision,
            "hold_reason": hold_reason,
        })
        if decision != "PASS":
            continue
        products.append({
            "external_id": external_id,
            "identity_scope": "model_core",
            "manufacturer": str(identity["manufacturer"]),
            "model_core": str(identity["mpn"]),
            "technology": technology,
            "source_url": str(identity["source_url"]),
            "technical_attributes": {
                "Модель": str(identity["mpn"]),
                "Тип изделия": str(identity["product_type"]),
                "Технология": technology,
            },
            "source_kind": str(identity["source_kind"]),
            "source_tier": "manufacturer_primary",
            "source_publisher": str(identity["source_publisher"]),
            "manufacturer_primary": True,
            "evidence_scope": "model_core",
            "checked_at": CHECKED_AT,
        })

    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)
    manifest = {
        "schema_version": 1,
        "purpose": "Wave241 no-repeat source-backed descriptions from existing SHA-pinned manufacturer-primary snapshots only.",
        "locale": "ru-BY",
        "products": products,
    }
    write_json(MANIFEST, manifest)
    pass_count = sum(row["decision"] == "PASS" for row in ledger)
    hold_count = len(ledger) - pass_count
    summary = {
        "schema_version": 1,
        "wave": "wave241_source_backed_descriptions",
        "checked_at": CHECKED_AT,
        "coverage": {"scope": 44, "pass": pass_count, "hold": hold_count},
        "queue": {"path": QUEUE.relative_to(ROOT).as_posix(), "sha256": QUEUE_SHA256},
        "identity_registries": identity_pins,
        "no_repeat_audit": {
            "prior_description_manifest_count": len(PRIOR_DESCRIPTION_MANIFESTS),
            "prior_description_product_rows": prior_rows,
            "scope_overlap": 0,
            "pins": prior_pins,
        },
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(products)},
        "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha256(LEDGER), "rows": len(ledger)},
        "safety": {"network_calls": 0, "database_operations": 0, "apply_performed": False,
                   "commercial_changes": 0, "publication_changes": 0, "media_changes": 0},
    }
    write_json(SUMMARY, summary)
    REPORT.write_text(
        "# Wave241: no-repeat source-backed descriptions\n\n"
        f"Wave241 processed all 44 Wave240 rows with a missing applied description and non-empty manufacturer/MPN. "
        f"Result: **PASS {pass_count}, HOLD {hold_count}**.\n\n"
        "## No-repeat audit\n\n"
        f"Four existing manufacturer identity registries cover 44/44 targets without overlap. Fourteen Wave228-239 "
        f"description evidence/stage manifests contain {prior_rows} product rows and have zero overlap with this scope. "
        "Earlier description packages selected other cohorts, commonly verified-media gaps; Wave241 does not repeat those rows.\n\n"
        "## Evidence boundary\n\n"
        "Every PASS row revalidates the identity-registry SHA, the local manufacturer PDF/HTML SHA, exact normalized MPN "
        "presence, and a technology marker from the same pinned source. The manifest carries only the existing model, "
        "product-type and technology facts. Price, stock, warranty, publication, "
        "URL and media claims are excluded. HOLD rows remain outside the manifest. No database apply or network request occurred.\n",
        encoding="utf-8",
        newline="\n",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
