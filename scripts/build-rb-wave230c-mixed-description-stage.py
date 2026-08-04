#!/usr/bin/env python3
"""Build the Wave230-C mixed manufacturer-primary description-stage package.

The package deliberately reuses only previously SHA-pinned evidence.  It also
ties every draft to the Wave229 verified-media manifest through the frozen
Wave230 target register.  No network, database, or importer operation occurs.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
TARGETS = GEN / "rb-wave230-description-targets.csv"
MEDIA = IMPORTS / "rb-reviewed-legacy-preview-media-wave229-2026-07-29.json"
VENTURA_PANASONIC = GEN / "wave206-panasonic-ventura-mnb-evidence.csv"
CASIL_ROBITON = GEN / "rb-wave208s-stationary-evidence.csv"
BB = GEN / "rb-wave209c-stationary-evidence.csv"
DELTA_NEW = GEN / "rb-delta-wave206-official-evidence.csv"
DELTA_OLD = GEN / "wave209b-delta-fiamm-leoch-evidence.csv"
VENTURA_TEXT = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/ventura-catalogue-2023.txt"
MANIFEST = IMPORTS / "rb-source-backed-description-stage-manifest-wave230c-2026-07-29.json"
LEDGER = GEN / "rb-wave230c-mixed-description-ledger.csv"
SUMMARY = GEN / "rb-wave230c-mixed-description.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave230c-mixed-description-stage.md"

PINS = {
    TARGETS: "39bb2ca1d650997d78583ee7daa4589f124b5f3b9e18b0d9bd82e7b4dcab0bd2",
    MEDIA: "99feaa5836d91da2e6c66ce8d808153a799dfe8e2b8cf8208479e8fada2d5ef4",
    VENTURA_PANASONIC: "72c34216da89b856b3e2e82220e674edbe6c0707fe5bc1547499ba3ead22749e",
    CASIL_ROBITON: "d729fe9db4cc48498f395bebadce4c492d493ef2244a9acf332f4e0e90570ca1",
    BB: "5ec2b64ddc1f03c503dddc97e1544710d3cd17e29af7f41223aa4850f805c384",
    DELTA_NEW: "9aef716d13d9dbbaf1a13473641469d61dd130a148b87e89d8c45fc776a0b36c",
    DELTA_OLD: "0f6cf1cb3cd9e07ad205136fdb9b61c5f88ac0fc779a02dea5c6821fde9dc449",
    VENTURA_TEXT: "005fb1d171d5aee334eaffaac058e92aa96898dc543836e0c9e5b0da0709eae7",
}

EXPECTED_COUNTS = {
    "Ventura": 7, "Casil": 5, "ROBITON": 5, "B.B. Battery": 4,
    "Delta": 3, "DELTA": 3, "Panasonic": 1,
}
TECHNOLOGY = {
    "Ventura": ("VRLA AGM", "AGM"),
    "Casil": ("свинцово-кислотная аккумуляторная батарея", "Lead Acid Battery"),
    "ROBITON": ("герметизированная свинцово-кислотная аккумуляторная батарея с клапанным регулированием", "Герметизированная свинцово-кислотная аккумуляторная батарея с клапанным регулированием"),
    "B.B. Battery": ("свинцово-кислотная аккумуляторная батарея", "Lead Acid"),
    "Delta": ("AGM", "AGM"), "DELTA": ("AGM", "AGM"),
    "Panasonic": ("VRLA AGM", "VRLA"),
}
LEDGER_FIELDS = (
    "external_id", "manufacturer", "mpn", "identity_scope", "model_core", "media_id",
    "media_sha256", "source_url", "source_kind", "source_publisher", "snapshot_path",
    "snapshot_sha256", "required_tokens", "technology", "name_ends_with_mpn", "stageable",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def source_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    require(path.is_file(), f"pinned snapshot absent: {value}")
    return path


def text_contains(path: Path, token: str) -> bool:
    return token.casefold() in path.read_text(encoding="utf-8", errors="ignore").casefold()


def normalized_text_contains(path: Path, token: str) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return "".join(char for char in token.casefold() if char.isalnum()) in "".join(char for char in text.casefold() if char.isalnum())


def strict_name_ends_with_mpn(name: str, mpn: str) -> bool:
    """Mirror the exact-only gate: no removal of title/specification suffixes."""
    return name.rstrip().casefold().endswith(mpn.casefold())


def evidence_rows(path: Path) -> dict[str, dict[str, str]]:
    rows = read_csv(path)
    result = {row["product_external_id"]: row for row in rows if row.get("safe_to_apply") == "true"}
    require(len(result) == len({row["product_external_id"] for row in rows if row.get("safe_to_apply") == "true"}), f"duplicate evidence external ID: {path.name}")
    return result


def record_for(target: dict[str, str], sources: dict[str, dict[str, dict[str, str]]]) -> dict[str, str]:
    manufacturer = target["manufacturer"]
    external_id = target["product_external_id"]
    if manufacturer in {"Ventura", "Panasonic"}:
        row = sources["ventura_panasonic"].get(external_id) or sources["stationary"].get(external_id)
        model = (row.get("model", "") or row.get("model_candidate", "")) if row else ""
        kind = "official_manufacturer_catalogue"
    elif manufacturer in {"Casil", "ROBITON"}:
        row = sources["casil_robiton"].get(external_id)
        model = row.get("replacement_mpn", "") if row else ""
        kind = "official_manufacturer_product_page"
    elif manufacturer == "B.B. Battery":
        row = sources["bb"].get(external_id)
        model = row.get("model_candidate", "") if row else ""
        kind = "official_manufacturer_catalogue"
    elif external_id in {"bitrix:1527", "bitrix:1549", "bitrix:1558"}:
        row = sources["delta_new"].get(external_id)
        model = row.get("replacement_mpn", "") if row else ""
        kind = "official_manufacturer_product_page"
    else:
        row = sources["delta_old"].get(external_id)
        model = row.get("model_candidate", "") if row else ""
        kind = "official_manufacturer_product_page"
    require(row is not None and model == target["mpn"], f"missing or mismatched reused evidence: {external_id}")
    return {
        "model": model, "source_url": row["source_url"], "source_publisher": row["source_publisher"],
        "snapshot_path": row["snapshot_path"], "snapshot_sha256": row["snapshot_sha256"],
        "source_assertion": row["source_assertion"], "verified_technology": row.get("verified_technology", ""),
        "source_kind": kind,
    }


def build() -> dict[str, object]:
    for path, expected in PINS.items():
        require(digest(path) == expected, f"pinned input drift: {path.relative_to(ROOT)}")

    targets = read_csv(TARGETS)
    target_ids = {row["product_external_id"] for row in targets}
    selected = [row for row in targets if row["manufacturer"] in EXPECTED_COUNTS]
    require(len(targets) == len(target_ids) == 88, "Wave230 frozen denominator drift")
    require(len(selected) == len({row["product_external_id"] for row in selected}) == 28, "Wave230-C frozen target cardinality drift")
    require(Counter(row["manufacturer"] for row in selected) == EXPECTED_COUNTS, "Wave230-C manufacturer scope drift")

    media = {row["external_id"]: row for row in json.loads(MEDIA.read_text(encoding="utf-8-sig"))["images"]}
    require(len(media) >= 88, "Wave229 verified-media lineage is incomplete")
    for target in selected:
        image = media.get(target["product_external_id"])
        require(image is not None, f"missing verified-media lineage: {target['product_external_id']}")
        require(str(image["media_id"]) == target["media_id"] and image["content_sha256"] == target["media_sha256"], f"verified-media lineage drift: {target['product_external_id']}")
        require(image["mpn"] == target["mpn"] and image["identity_evidence_level"] == "visible_exact_mpn", f"media MPN proof drift: {target['product_external_id']}")

    sources = {
        "ventura_panasonic": evidence_rows(VENTURA_PANASONIC),
        "casil_robiton": evidence_rows(CASIL_ROBITON), "bb": evidence_rows(BB), "stationary": evidence_rows(BB),
        "delta_new": evidence_rows(DELTA_NEW), "delta_old": evidence_rows(DELTA_OLD),
    }
    products: list[dict[str, object]] = []
    ledger: list[dict[str, str]] = []
    for target in sorted(selected, key=lambda row: row["product_external_id"]):
        source = record_for(target, sources)
        snapshot = source_path(source["snapshot_path"])
        technology, technology_token = TECHNOLOGY[target["manufacturer"]]
        require(digest(snapshot) == source["snapshot_sha256"], f"snapshot hash drift: {target['product_external_id']}")
        require(source["source_url"].startswith("https://"), f"non-HTTPS source: {target['product_external_id']}")
        evidence_text = VENTURA_TEXT if snapshot.name == "ventura-catalogue-2023.pdf" else snapshot
        if evidence_text != snapshot:
            require(normalized_text_contains(evidence_text, target["mpn"]) and text_contains(evidence_text, technology_token), f"Ventura catalogue text assertion absent: {target['product_external_id']}")
        elif snapshot.suffix.casefold() == ".pdf":
            # Existing Wave206 catalogue evidence is the pinned extraction of the
            # PDF table; re-extracting that large document here is not evidence.
            require("exact" in source["source_assertion"].casefold(), f"catalogue exact assertion absent: {target['product_external_id']}")
            require("AGM" in source["verified_technology"].upper(), f"catalogue technology assertion absent: {target['product_external_id']}")
        else:
            require(normalized_text_contains(snapshot, target["mpn"]), f"exact MPN absent from pinned source: {target['product_external_id']}")
            require(text_contains(snapshot, technology_token), f"technology token absent from pinned source: {target['product_external_id']}")
        exact = strict_name_ends_with_mpn(target["name"], target["mpn"])
        product: dict[str, object] = {
            "external_id": target["product_external_id"], "identity_scope": "exact" if exact else "model_core",
            "manufacturer": target["manufacturer"], "technology": technology,
            "source_url": source["source_url"], "technical_attributes": {"Технология": technology},
            "source_kind": source["source_kind"], "source_tier": "manufacturer_primary",
            "source_publisher": source["source_publisher"], "manufacturer_primary": True,
            "evidence_scope": "exact_model" if exact else "model_core", "checked_at": "2026-07-29",
        }
        if exact:
            product["mpn"] = target["mpn"]
        else:
            product["model_core"] = target["mpn"]
        products.append(product)
        ledger.append({
            "external_id": target["product_external_id"], "manufacturer": target["manufacturer"], "mpn": target["mpn"],
            "identity_scope": product["identity_scope"], "model_core": "" if exact else target["mpn"],
            "media_id": target["media_id"], "media_sha256": target["media_sha256"], "source_url": source["source_url"],
            "source_kind": source["source_kind"], "source_publisher": source["source_publisher"],
            "snapshot_path": str(snapshot.relative_to(ROOT)).replace("\\", "/"), "snapshot_sha256": source["snapshot_sha256"],
            "required_tokens": f"{target['mpn']}|{technology_token}", "technology": technology,
            "name_ends_with_mpn": str(exact).lower(), "stageable": "true",
        })

    require(len(products) == 28 == len({row["external_id"] for row in products}), "manifest cardinality drift")
    require(all(set(row) >= {"external_id", "identity_scope", "manufacturer", "technology", "source_url", "technical_attributes", "source_kind", "source_tier", "source_publisher", "manufacturer_primary", "evidence_scope", "checked_at"} for row in products), "product contract drift")
    require(all(row["identity_scope"] == "model_core" and row["evidence_scope"] == "model_core" and "model_core" in row and "mpn" not in row for row in products), "strict name-end gate drift")
    manifest = {
        "schema_version": 1,
        "purpose": "Wave230-C frozen verified-media source-backed description drafts; bounded model-core scope when the exact name-end contract does not pass.",
        "locale": "ru-BY",
        "application_contract": {"stage_only": True, "refresh_existing": True, "refresh_applied": True, "database_apply": False},
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger)
    summary = {
        "schema_version": 1, "wave": "wave230c_mixed_primary_description_stage",
        "frozen_denominator": 88, "target_rows": 28, "manufacturer_counts": dict(Counter(row["manufacturer"] for row in products)),
        "identity_scope_counts": dict(Counter(row["identity_scope"] for row in products)),
        "verified_media_lineage": {"manifest": str(MEDIA.relative_to(ROOT)).replace("\\", "/"), "sha256": PINS[MEDIA], "rows": 28, "identity_evidence_level": "visible_exact_mpn"},
        "inputs": {str(path.relative_to(ROOT)).replace("\\", "/"): expected for path, expected in PINS.items()},
        "manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"), "manifest_sha256": digest(MANIFEST),
        "ledger": str(LEDGER.relative_to(ROOT)).replace("\\", "/"), "ledger_sha256": digest(LEDGER),
        "database_apply": False, "publication_changes": 0,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(
        "# Wave230-C: remaining mixed manufacturer-primary descriptions\n\n"
        "This package covers exactly 28 frozen Wave230 verified-media targets: Ventura (7), Casil (5), ROBITON (5), B.B. Battery (4), Delta/DELTA (6) and Panasonic (1). Each row is tied to the Wave229 media ID, SHA-256 and `visible_exact_mpn` proof before staging evidence is evaluated.\n\n"
        "Only existing SHA-pinned manufacturer-primary evidence is reused: Ventura/Panasonic catalogue rows, Casil/ROBITON product pages, B.B. Battery catalogues and Delta product pages. Each snapshot is rehashed and must contain the exact MPN and a conservative technology token.\n\n"
        "The strict raw `nameEndsWith(MPN)` contract fails for all 28 catalogue names because each retains a technical suffix. Therefore every stage row is bounded manufacturer-primary `model_core`, with no exact-only `mpn` or display-name field. The generated manifest is stage-only (`--refresh-existing --refresh-applied` after review); this builder does not execute it or apply database, publication, commercial, media, URL or identity changes.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
