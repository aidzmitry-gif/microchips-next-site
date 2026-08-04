#!/usr/bin/env python3
"""Build fail-closed identity, description, media, and duplicate artifacts for Wave245C."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "docs/audits/generated/rb-enrichment-queue-wave244.csv"
LIVE = ROOT / "docs/audits/generated/rb-wave245c-panasonic-live-safety.json"
REGISTRY = ROOT / "docs/audits/sources/wave245c-panasonic/source-registry.json"
PRIOR_INDEX = ROOT / "docs/audits/sources/wave206-panasonic-ventura-mnb/snapshot-index.json"
PRIOR_211C = ROOT / "docs/audits/generated/rb-wave211c-stationary-evidence.csv"
PRIOR_209C = ROOT / "docs/audits/generated/rb-wave209c-stationary-evidence.csv"

LEDGER = ROOT / "docs/audits/generated/rb-wave245c-panasonic-evidence-ledger.csv"
DUPLICATES = ROOT / "docs/audits/generated/rb-wave245c-panasonic-duplicate-review.json"
MEDIA = ROOT / "docs/audits/generated/rb-wave245c-panasonic-media-review.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave245c-panasonic.summary.json"
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave245c-panasonic-2026-07-30.json"
DESCRIPTIONS = ROOT / "docs/imports/rb-source-backed-descriptions-wave245c-panasonic-2026-07-30.json"

PINS = {
    QUEUE: "eb2549163840fce48d5f08e5f08129b268ddf11a220f84de8e0635a7c93eb0ab",
    LIVE: "09b7e6da18482adebf84ce618dbee6b4380fea22a86f9468879b4d7aec7024d8",
    REGISTRY: "b8ed05e17863124d8b15634509d603a2994cf225cffab36f82f92bc278219813",
    PRIOR_INDEX: "705579d386df38e100fc430a52c1f834aece98742444e1ea4786205eff00828f",
    PRIOR_211C: "eb7c4e86ae614db2f0dfc5368baf08c0199e168ca9b68f7551d5beddc7335714",
    PRIOR_209C: "5ec2b64ddc1f03c503dddc97e1544710d3cd17e29af7f41223aa4850f805c384",
}
TARGETS = {
    "bitrix:3232": {"model": "UP-VW0645P1", "voltage": "6 В", "capacity": "7,8 А·ч", "rated_power": "135 Вт", "dimensions": "34 × 151 × 100 мм", "mass": "1,30 кг"},
    "bitrix:1598": {"model": "UP-VW1220P1", "voltage": "12 В", "capacity": "4,0 А·ч", "rated_power": "120 Вт", "dimensions": "38,5 × 140 × 100 мм", "mass": "1,30 кг"},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def model_in_name(name: str, model: str) -> bool:
    return re.search(rf"(?<![A-Z0-9]){re.escape(model)}(?![A-Z0-9])", name, re.I) is not None


def main() -> None:
    for path, digest in PINS.items():
        if sha(path) != digest:
            raise SystemExit(f"pinned input drift: {path}")

    with QUEUE.open(encoding="utf-8-sig", newline="") as handle:
        queue = {row["product_external_id"]: row for row in csv.DictReader(handle) if row["product_external_id"] in TARGETS}
    if set(queue) != set(TARGETS) or any(row["has_applied_description"] != "false" or row["identity_fields_present"] != "0" for row in queue.values()):
        raise SystemExit("Wave245C queue scope/state drift")

    live_data = json.loads(LIVE.read_text(encoding="utf-8"))
    live = {row["external_id"]: row for row in live_data["rows"]}
    if live_data["site"] != "microchips-by" or not set(TARGETS).issubset(live):
        raise SystemExit("Wave245C live target drift")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    sources = {row["model"]: row for row in registry["sources"]}
    if set(sources) != {facts["model"] for facts in TARGETS.values()}:
        raise SystemExit("Wave245C source scope drift")

    current_urls = {row["final_url"] for row in sources.values()} | {registry["rights_source"]["final_url"]}
    current_shas = {row["snapshot_sha256"] for row in sources.values()}
    for path in (ROOT / "docs/audits/sources").rglob("*.pdf"):
        if "wave245c-panasonic" not in path.as_posix() and sha(path) in current_shas:
            raise SystemExit(f"prior source SHA repeated: {path}")
    for base in (ROOT / "docs/audits", ROOT / "docs/imports"):
        for path in base.rglob("*"):
            # Wave245B's exclusion inventory was generated concurrently after
            # this Wave245C source directory already existed, so treating that
            # circular inventory as a prior source would be a false positive.
            if path.name == "rb-wave245b-prior-source-exclusions.json":
                continue
            if not path.is_file() or "wave245c" in path.as_posix().lower() or path.suffix.lower() not in {".json", ".csv", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(url in text for url in current_urls):
                raise SystemExit(f"prior source URL repeated: {path}")

    rights = registry["rights_source"]
    rights_path = ROOT / rights["snapshot_path"]
    if sha(rights_path) != rights["snapshot_sha256"]:
        raise SystemExit("rights snapshot SHA drift")
    rights_text = rights_path.read_text(encoding="utf-8", errors="ignore").lower()
    for phrase in ("protected by copyright", "prior written permission", "personal non commercial"):
        if phrase not in rights_text:
            raise SystemExit(f"rights source missing fail-closed phrase: {phrase}")

    extracted: dict[str, str] = {}
    for model, source in sources.items():
        pdf = ROOT / source["snapshot_path"]
        image = ROOT / source["image_candidate_path"]
        if sha(pdf) != source["snapshot_sha256"] or sha(image) != source["image_candidate_sha256"]:
            raise SystemExit(f"source/image SHA drift: {model}")
        text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
        extracted[model] = text
        if not model_in_name(text, model) or "INDIVIDUAL DATA SHEETS" not in text or "Faston 250" not in text:
            raise SystemExit(f"exact primary assertions missing: {model}")
        with Image.open(image) as candidate:
            if candidate.size != (source["image_candidate_width"], source["image_candidate_height"]) or candidate.width < 200 or candidate.height < 170:
                raise SystemExit(f"official image shape drift: {model}")

    required_numeric = {
        "UP-VW0645P1": ["Nominal voltage (V)", "6", "20 hours rate (Ah)", "7.8", "135", "1.30"],
        "UP-VW1220P1": ["Nominal voltage (V)", "12", "20 hours rate (Ah)", "4.0", "120", "1.30"],
    }
    for model, tokens in required_numeric.items():
        if any(token not in extracted[model] for token in tokens):
            raise SystemExit(f"exact technical facts missing: {model}")

    identities, descriptions, ledger_rows, duplicate_rows, media_rows = [], [], [], [], []
    for external_id, facts in TARGETS.items():
        model = facts["model"]
        target = live[external_id]
        exact_1c = [row for row in live.values() if row["external_id"] not in TARGETS and model_in_name(row["name"], model)]
        if external_id == "bitrix:3232" and exact_1c:
            raise SystemExit("UP-VW0645P1 unexpectedly gained a live 1C exact duplicate")
        if external_id == "bitrix:1598" and {row["external_id"] for row in exact_1c} != {"КА-00003724", "КА-00005218"}:
            raise SystemExit("UP-VW1220P1 live 1C ambiguity drift")
        duplicate_decision = "PASS_NO_EXACT_1C_DUPLICATE" if not exact_1c else "HOLD_AMBIGUOUS_TWO_1C_EXACT_NAME_CANDIDATES"
        identity_decision = "PASS" if not exact_1c else "HOLD"
        source = sources[model]
        duplicate_rows.append({
            "bitrix_external_id": external_id, "model": model, "decision": duplicate_decision,
            "live_1c_candidates": [{"external_id": row["external_id"], "name": row["name"], "published": row["site_product"]["published"] if row["site_product"] else None} for row in exact_1c],
            "collapse_manifest_emitted": False,
        })
        ledger_rows.append({
            "external_id": external_id, "model": model, "identity_decision": identity_decision,
            "duplicate_decision": duplicate_decision, "source_url": source["final_url"],
            "source_snapshot_sha256": source["snapshot_sha256"], "exact_image_sha256": source["image_candidate_sha256"],
            "media_decision": "HOLD_RIGHTS_PERMISSION_REQUIRED", "safe_to_stage_identity_description": "true" if identity_decision == "PASS" else "false",
        })
        media_rows.append({
            "external_id": external_id, "model": model, "source_url": source["final_url"],
            "image_candidate_path": source["image_candidate_path"], "image_candidate_sha256": source["image_candidate_sha256"],
            "dimensions": [source["image_candidate_width"], source["image_candidate_height"]],
            "visual_review": {"method": "manual_view_image_original", "result": "PASS_EXACT_MODEL_LABEL_AND_BATTERY_FORM", "reviewed_at": "2026-07-30"},
            "rights_source_url": rights["final_url"], "rights_snapshot_path": rights["snapshot_path"], "rights_snapshot_sha256": rights["snapshot_sha256"],
            "rights_status": "HOLD_PRIOR_WRITTEN_PERMISSION_REQUIRED", "safe_to_import": False,
        })
        if identity_decision != "PASS":
            continue
        identities.append({
            "external_id": external_id, "current_name": queue[external_id]["name"], "manufacturer": "Panasonic", "mpn": model,
            "source_url": source["final_url"], "source_kind": "official_manufacturer_catalogue",
            "source_publisher": "Panasonic Industry Europe GmbH", "checked_at": "2026-07-29", "product_type": "stationary VRLA AGM battery",
            "source_snapshot_path": "../audits/" + source["snapshot_path"].split("docs/audits/", 1)[1], "source_snapshot_sha256": source["snapshot_sha256"],
        })
        descriptions.append({
            "external_id": external_id, "identity_scope": "exact", "manufacturer": "Panasonic", "mpn": model,
            "display_name": f"Аккумулятор Panasonic {model}", "technology": "VRLA AGM",
            "source_url": source["final_url"], "source_kind": "official_manufacturer_catalogue", "source_tier": "manufacturer_primary",
            "source_publisher": "Panasonic Industry Europe GmbH", "manufacturer_primary": True, "evidence_scope": "exact_model", "checked_at": "2026-07-29",
            "technical_attributes": {"Серия": "UP-VW", "Номинальное напряжение": facts["voltage"], "Номинальная ёмкость (20 ч)": facts["capacity"], "Номинальная мощность (10 мин)": facts["rated_power"], "Габариты": facts["dimensions"], "Масса": facts["mass"], "Выводы": "Faston 250"},
        })

    if [row["external_id"] for row in identities] != ["bitrix:3232"] or len(media_rows) != 2:
        raise SystemExit("Wave245C fail-closed output partition drift")
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ledger_rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(ledger_rows)
    write_json(IDENTITIES, {"schema_version": 1, "site_key": "microchips-by", "target_kind": "bitrix_draft", "purpose": "Wave245C exact Panasonic identities after live duplicate gate", "products": identities})
    write_json(DESCRIPTIONS, {"schema_version": 1, "purpose": "Wave245C exact Panasonic manufacturer-primary descriptions", "locale": "ru-BY", "products": descriptions})
    write_json(DUPLICATES, {"schema_version": 1, "site_key": "microchips-by", "pairs": duplicate_rows, "database_apply": False})
    write_json(MEDIA, {"schema_version": 1, "site_key": "microchips-by", "candidates": media_rows, "verified_media_import_manifest_emitted": False})
    write_json(SUMMARY, {
        "schema_version": 1, "wave": "wave245c_panasonic", "checked_at": "2026-07-30", "scope": list(TARGETS),
        "identity_description_pass": ["bitrix:3232"], "identity_description_hold": ["bitrix:1598"],
        "media_exact_visual_pass_rights_hold": 2, "duplicate_collapse_ready": 0,
        "new_source_urls": sorted(current_urls), "new_source_sha256": sorted(current_shas), "prior_url_collisions": 0, "prior_sha_collisions": 0,
        "outputs": {"identity": {"path": IDENTITIES.relative_to(ROOT).as_posix(), "sha256": sha(IDENTITIES)}, "description": {"path": DESCRIPTIONS.relative_to(ROOT).as_posix(), "sha256": sha(DESCRIPTIONS)}, "duplicates": {"path": DUPLICATES.relative_to(ROOT).as_posix(), "sha256": sha(DUPLICATES)}, "media": {"path": MEDIA.relative_to(ROOT).as_posix(), "sha256": sha(MEDIA)}, "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "sha256": sha(LEDGER)}},
        "policy": {"fail_closed": True, "database_apply": False, "media_import": False, "commit": False, "push": False},
    })
    print(json.dumps({"scope": 2, "identity_description_pass": 1, "duplicate_hold": 1, "media_rights_hold": 2}))


if __name__ == "__main__":
    main()
