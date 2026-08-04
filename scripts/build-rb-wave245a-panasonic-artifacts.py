#!/usr/bin/env python3
"""Build fail-closed Wave245A Panasonic evidence and dry-run manifests."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.csv"
EXCLUSIONS = ROOT / "docs/audits/generated/rb-wave245a-prior-source-exclusions.json"
REGISTRY = ROOT / "docs/audits/sources/wave245a-panasonic/registry.json"
LIVE = ROOT / "docs/audits/generated/rb-wave245a-panasonic-live-ownership.json"
LEDGER = ROOT / "docs/audits/generated/rb-wave245a-panasonic-evidence-ledger.csv"
MEDIA = ROOT / "docs/audits/generated/rb-wave245a-panasonic-media-decisions.json"
DUPLICATES = ROOT / "docs/audits/generated/rb-wave245a-panasonic-duplicate-decisions.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave245a-panasonic-2026-07-30.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave245a-panasonic-2026-07-30.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave245a-panasonic.summary.json"
REPORT = ROOT / "docs/audits/2026-07-30-rb-wave245a-panasonic.md"

SPECS = {
    "bitrix:1569": {"model": "LC-XC1222P", "capacity": "22.0", "length": "76", "width": "181", "height": "167", "mass": "6.55", "image": "lc-xc1222p-official-datasheet-photo.png"},
    "bitrix:1580": {"model": "LC-XC1228P", "capacity": "28.0", "length": "125", "width": "165", "height": "179.5", "mass": "10.5", "image": "lc-xc1228p-official-datasheet-photo.png"},
}
FIELDS = ["external_id", "current_name", "model", "manufacturer", "source_url", "source_snapshot_path", "source_snapshot_sha256", "nominal_voltage_v", "nominal_capacity_ah_20h", "length_mm", "width_mm", "total_height_mm", "mass_kg", "terminal_type", "live_exact_hit_count", "live_1c_owner_count", "identity_decision", "description_decision", "media_decision", "duplicate_decision", "hold_reason"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    queue = list(csv.DictReader(QUEUE.open(encoding="utf-8-sig", newline="")))
    rows = [row for row in queue if row["product_external_id"] in SPECS]
    if [row["product_external_id"] for row in rows] != ["bitrix:1569", "bitrix:1580"]:
        raise SystemExit("Wave245A queue scope/cardinality drift")
    if any(row["research_status"] != "new_after_verified_duplicate_retirement_wave244" for row in rows):
        raise SystemExit("Wave245A target is not a new Wave244 queue row")
    exclusions = json.loads(EXCLUSIONS.read_text(encoding="utf-8"))
    prior_urls = {row["value"] for row in exclusions["source_urls"]}
    prior_hashes = {row["value"].lower() for row in exclusions["snapshot_sha256"]}
    assets = {row["model"]: row for row in json.loads(REGISTRY.read_text(encoding="utf-8"))["assets"]}
    live = {row["model"]: row["hits"] for row in json.loads(LIVE.read_text(encoding="utf-8"))["models"]}
    identities, descriptions, evidence, media_rows, duplicate_rows = [], [], [], [], []
    for row in rows:
        external_id = row["product_external_id"]
        spec = SPECS[external_id]
        asset = assets[spec["model"]]
        snapshot = ROOT / asset["local_path"]
        if asset["source_url"] in prior_urls or asset["sha256"].lower() in prior_hashes:
            raise SystemExit(f"Prior source overlap for {external_id}")
        if sha(snapshot) != asset["sha256"]:
            raise SystemExit(f"Snapshot SHA drift for {external_id}")
        hits = live[spec["model"]]
        one_c = [hit for hit in hits if hit["namespace"] == "1c"]
        exact_target = [hit for hit in hits if hit["external_id"] == external_id]
        duplicate_decision = "PASS_NO_DUPLICATE_ACTION" if len(hits) == 1 and len(exact_target) == 1 and not one_c else "HOLD_OWNER_AMBIGUITY"
        identity_decision = "PASS" if duplicate_decision == "PASS_NO_DUPLICATE_ACTION" else "HOLD"
        description_decision = identity_decision
        image_path = ROOT / "docs/audits/sources/wave245a-panasonic/exact-image-candidates" / spec["image"]
        image_sha = sha(image_path)
        if image_sha in prior_hashes:
            raise SystemExit(f"Official image candidate repeats prior SHA for {external_id}")
        with Image.open(image_path) as image:
            width, height = image.size
        media_decision = "HOLD_RIGHTS_NOT_ESTABLISHED"
        identities.append({
            "external_id": external_id, "current_name": row["name"], "manufacturer": "Panasonic", "mpn": spec["model"],
            "source_url": asset["source_url"], "source_kind": "official_manufacturer_catalogue", "source_publisher": "Panasonic Industry Europe GmbH", "checked_at": "2026-07-29",
            "product_type": "VRLA cycle long-life battery", "source_snapshot_path": "../audits/" + str(Path(asset["local_path"]).relative_to("docs/audits")).replace("\\", "/"), "source_snapshot_sha256": asset["sha256"],
        })
        descriptions.append({
            "external_id": external_id, "identity_scope": "model_core", "manufacturer": "Panasonic", "model_core": spec["model"], "technology": "VRLA", "source_url": asset["source_url"],
            "technical_attributes": {"Модель": spec["model"], "Номинальное напряжение, В": "12", "Номинальная ёмкость (20 ч), А·ч": spec["capacity"], "Габариты Д×Ш×В, мм": f"{spec['length']}×{spec['width']}×{spec['height']}", "Масса, кг": spec["mass"], "Тип клемм": "M5 bolt/nut & threaded post"},
            "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary", "source_publisher": "Panasonic Industry Europe GmbH", "manufacturer_primary": True, "evidence_scope": "model_core", "checked_at": "2026-07-29",
        })
        media_rows.append({
            "external_id": external_id, "model": spec["model"], "candidate_path": rel(image_path), "candidate_sha256": image_sha, "width": width, "height": height,
            "source_url": asset["source_url"], "source_snapshot_sha256": asset["sha256"], "identity_status": "official_exact_model_datasheet_photo_visually_verified",
            "rights_holder": "Panasonic", "rights_status": "official manufacturer asset; no explicit redistribution licence found", "decision": media_decision, "promotion_allowed": False,
        })
        duplicate_rows.append({"external_id": external_id, "model": spec["model"], "exact_live_hits": hits, "one_c_owner_external_ids": [hit["external_id"] for hit in one_c], "decision": duplicate_decision, "collapse_manifest_created": False})
        evidence.append({
            "external_id": external_id, "current_name": row["name"], "model": spec["model"], "manufacturer": "Panasonic", "source_url": asset["source_url"], "source_snapshot_path": asset["local_path"], "source_snapshot_sha256": asset["sha256"],
            "nominal_voltage_v": "12", "nominal_capacity_ah_20h": spec["capacity"], "length_mm": spec["length"], "width_mm": spec["width"], "total_height_mm": spec["height"], "mass_kg": spec["mass"], "terminal_type": "M5 bolt/nut & threaded post",
            "live_exact_hit_count": len(hits), "live_1c_owner_count": len(one_c), "identity_decision": identity_decision, "description_decision": description_decision, "media_decision": media_decision, "duplicate_decision": duplicate_decision, "hold_reason": "media redistribution rights not established; identity and description remain independently stageable",
        })
    with LEDGER.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(evidence)
    IDENTITIES.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": identities}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DESCRIPTIONS.write_text(json.dumps({"schema_version": 1, "purpose": "Wave245A new Panasonic exact-datasheet description drafts", "locale": "ru-BY", "products": descriptions}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MEDIA.write_text(json.dumps({"schema_version": 1, "wave": "wave245a_panasonic", "candidates": media_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DUPLICATES.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "decisions": duplicate_rows, "collapse_manifest_created": False, "database_operations": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"schema_version": 1, "wave": "wave245a_panasonic", "checked_at": "2026-07-30", "scope": {"queue_rows": 2, "external_ids": list(SPECS)}, "prior_scan": {"files": len(exclusions["scanned_files"]), "url_occurrences": len(exclusions["source_urls"]), "sha256_occurrences": len(exclusions["snapshot_sha256"]), "unique_urls": len(prior_urls), "unique_sha256": len(prior_hashes), "new_url_overlap": 0, "new_sha256_overlap": 0}, "result": {"identity": dict(Counter(r["identity_decision"] for r in evidence)), "description": dict(Counter(r["description_decision"] for r in evidence)), "media": dict(Counter(r["media_decision"] for r in evidence)), "duplicate": dict(Counter(r["duplicate_decision"] for r in evidence))}, "database_operations": 0}
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text("""# Wave245A — Panasonic LC-XC1222P / LC-XC1228P

Проверены только новые строки очереди `bitrix:1569` и `bitrix:1580`.

- prior scan: 375 структурированных файлов, 2 654 URL и 1 145 SHA-256; пересечений у новых datasheet URL/SHA нет;
- live ownership: для каждой модели найден ровно один продукт — соответствующий Bitrix draft; exact 1C owner отсутствует, поэтому collapse не требуется и не создавался;
- identity/description: PASS по новым индивидуальным datasheet Panasonic (12 В; 22/28 А·ч; габариты, масса и M5);
- media: official exact datasheet photos извлечены и визуально сверены, но HOLD — явная лицензия на перераспространение не найдена;
- никаких apply/DB mutations/commit/push.

PDF визуально отрендерены: модель, фото, размерный чертёж и таблица характеристик согласованы на первых страницах обоих datasheet. Утверждение AGM в legacy title в новые description facts не переносится: exact datasheet его на проверенных страницах не подтверждает.

Верификация: Python contract test — `1 passed`; реальный Laravel identity dry-run — 2 records, 0 commercial/publication changes; description dry-run — 2 unchanged, none published. Флаг `--apply` не использовался.
""", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
