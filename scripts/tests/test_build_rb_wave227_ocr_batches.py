from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/build-rb-wave227-ocr-batches.py"
WORK = ROOT / ".tmp" / "pytest-wave227-ocr-batches"


def module():
    spec = importlib.util.spec_from_file_location("wave227", SCRIPT)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(mod):
    root = WORK / "assets"
    export = WORK / "export.csv"
    rows = []
    for index in range(102):
        exact = index % 2 == 0
        relative = f"legacy-staging/rb/{index}.png"
        storage = root / relative
        storage.parent.mkdir(parents=True, exist_ok=True)
        storage.write_bytes(f"wave227-local-asset-{index}".encode())
        rows.append({"external_id": f"bitrix:{1000 + index}", "media_id": str(5000 + index), "storage_path": relative, "content_sha256": sha256(storage), "rights_basis": "Company-owned legacy preview", "identity_scope": "exact" if exact else "model_core", "mpn": f"CR{index:04d}" if exact else "", "model_core": "" if exact else f"BR{index:04d}", "manufacturer": "" if exact else "Panasonic"})
    with export.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(mod.EXPORT_FIELDS), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
    return export, root, rows


def test_wave227_generalized_export_has_exact_and_model_core_100_plus_2_chunks() -> None:
    mod = module(); export, assets, rows = fixture(mod); out = WORK / "chunks"
    result = mod.build(export, (), assets, out, 100)
    assert result["selected_rows"] == 102
    assert [batch["rows"] for batch in result["batches"]] == [100, 2]
    selected = []
    for batch in result["batches"]:
        with (ROOT / batch["input"]).open(encoding="utf-8-sig", newline="") as handle:
            selected.extend(csv.DictReader(handle))
    assert len(selected) == 102 and all(bool(row["expected_mpn"]) != bool(row["expected_model_core"]) for row in selected)
    assert result["policy"] == {"ocr_executed": False, "database_apply": False, "media_promotion": False, "auto_pass": False, "publication_changes": 0}
    assert (out / "wave227-ocr-input-001.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_wave227_reviewed_media_is_excluded_by_defense_in_depth() -> None:
    mod = module(); export, assets, rows = fixture(mod); reviewed = WORK / "reviewed.json"
    reviewed.write_text(json.dumps({"images": [{"external_id": rows[0]["external_id"], "media_id": int(rows[0]["media_id"]), "content_sha256": rows[0]["content_sha256"]}]}), encoding="utf-8")
    result = mod.build(export, (reviewed,), assets, WORK / "excluded", 100)
    assert result["selected_rows"] == 101
    assert result["ledger"]["counts"] == {"excluded": 1, "selected": 101}


def test_wave227_holds_every_current_batch_shared_hash_even_for_same_expected_mpn() -> None:
    mod = module(); export, assets, rows = fixture(mod)
    duplicate = [rows[0].copy(), rows[1].copy()]
    duplicate[1]["external_id"] = "bitrix:9999"
    duplicate[1]["media_id"] = "9999"
    duplicate[1]["identity_scope"] = "exact"
    duplicate[1]["mpn"] = duplicate[0]["mpn"]
    duplicate[1]["model_core"] = ""
    duplicate[1]["content_sha256"] = duplicate[0]["content_sha256"]
    duplicate[1]["storage_path"] = duplicate[0]["storage_path"]
    with export.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(mod.EXPORT_FIELDS), lineterminator="\n")
        writer.writeheader(); writer.writerows(duplicate)
    result = mod.build(export, (), assets, WORK / "shared-hash", 100)
    assert result["selected_rows"] == 0 and result["shared_asset_hash_holds"] == 2
    ledger = list(csv.DictReader((WORK / "shared-hash/wave227-ocr-batch-ledger.csv").open(encoding="utf-8-sig", newline="")))
    assert len(ledger) == 2 and {row["reason"] for row in ledger} == {"shared_asset_hash_across_products"}
