from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "build-rb-wave250-release-gate-queue.py"


def module():
    spec = importlib.util.spec_from_file_location("wave250", SCRIPT)
    loaded = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(loaded)
    return loaded


def row(index: int, category: str = "seo:batteries-industrial") -> dict[str, object]:
    return {
        "product_id": index, "external_id": f"bitrix:{10000 + index}", "name": f"Industrial battery {index}",
        "manufacturer": "Maker", "mpn": f"MPN-{index}", "manufacturer_normalized": "maker",
        "mpn_normalized": f"mpn{index}", "product_status": "active", "short_description": "D" * 220,
        "site_product_id": index, "is_published": True, "price": None, "availability": "on_request",
        "category_external_id": category, "category_name": "Industrial batteries", "verified_media_count": 1,
        "matching_applied_description_count": 1, "description_source_urls": json.dumps([f"https://maker.example/{index}"]),
        "description_source_kind": "official_manufacturer_product_page", "description_source_tier": "manufacturer_primary",
        "description_identity_scope": "exact", "description_source_checked_at": "2026-07-29",
        "product_url_count": 1, "product_path": f"/catalog/industrial/{index}", "product_url_locale": "ru-BY",
        "url_is_indexable": False, "seo_record_count": 1, "seo_canonical_path": f"/catalog/industrial/{index}",
        "seo_is_indexable": False, "seo_title": f"Battery {index}", "seo_description": f"Description {index}",
        "canonical_redirect_source_count": 0, "current_price_evidence_count": 0,
        "fresh_matching_price_evidence_count": 0, "open_duplicate_conflict_count": 0,
        "unresolved_identity_candidate_count": 0, "identity_pair_catalogue_count": 1,
    }


def snapshot(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "site_key": "microchips-by", "currency": "BYN", "locale": "ru-BY", "rows": rows,
        "meta": {"site_domain": "microchips-by.test", "root_url_count": 1, "root_indexable_url_count": 0, "duplicate_site_url_paths": 0},
    }


def test_accumulates_all_blocker_lanes_and_selects_exactly_300() -> None:
    wave = module()
    rows = [row(index) for index in range(1, 306)]
    for item in rows:
        item["verified_media_count"] = 0
    multi = rows[0]
    multi.update({
        "manufacturer": "", "manufacturer_normalized": "", "mpn": "", "mpn_normalized": "",
        "product_status": "draft", "short_description": "short", "matching_applied_description_count": 0,
        "product_url_count": 0, "product_path": "", "seo_record_count": 0, "availability": "in_stock",
        "price": "100.00", "current_price_evidence_count": 0, "fresh_matching_price_evidence_count": 0,
    })
    selected, summary = wave.build(snapshot(rows), {})
    assert len(selected) == 300
    assert len({item["product_external_id"] for item in selected}) == 300
    assert all(int(item["blocker_count"]) > 0 for item in selected)
    # The high-blocker row sorts after the 304 one-blocker cards and is not used
    # to pad the fixed queue.
    assert multi["external_id"] not in {item["product_external_id"] for item in selected}
    assert all(item["all_blockers"] == "EXACT_VERIFIED_MEDIA_MISSING" for item in selected)
    assert summary["global_release_blockers"] == ["SITE_DOMAIN_NOT_PRODUCTION", "ROOT_URL_NOT_SINGLE_AND_INDEXABLE"]
    assert summary["quality"]["database_mutations"] == 0


def test_excludes_processed_indexable_ready_and_electronic_components() -> None:
    wave = module()
    rows = [row(index) for index in range(1, 305)]
    for item in rows:
        item["verified_media_count"] = 0
    processed_id = str(rows[0]["external_id"])
    rows[1]["url_is_indexable"] = True
    rows[2]["seo_is_indexable"] = True
    rows[3]["verified_media_count"] = 1  # strict ready
    selected, summary = wave.build(snapshot(rows), {processed_id: [{"reason": "prior", "path": "x", "sha256": "a"}]})
    selected_ids = {item["product_external_id"] for item in selected}
    assert processed_id not in selected_ids
    assert str(rows[1]["external_id"]) not in selected_ids
    assert str(rows[2]["external_id"]) not in selected_ids
    assert str(rows[3]["external_id"]) not in selected_ids
    assert summary["no_repeat"]["selected_overlap_prior_processed"] == 0
    assert summary["excluded"] == {"already_indexable": 2, "prior_processed_no_repeat": 1, "strict_ready_no_remediation_needed": 1}

    electronic = row(999, "seo:electronic-components")
    try:
        wave.primary_rows([electronic])
    except wave.QueueError:
        pass
    else:
        raise AssertionError("electronic-components must never enter B2B scope")


def test_sort_is_blocker_count_then_commercial_priority() -> None:
    wave = module()
    rows = [row(index, "seo:power-supplies") for index in range(1, 301)]
    for item in rows:
        item["verified_media_count"] = 0
    priority = row(400, "seo:ups-systems")
    priority["verified_media_count"] = 0
    rows.append(priority)
    two_blockers = row(401, "seo:ups-systems")
    two_blockers["verified_media_count"] = 0
    two_blockers["short_description"] = "short"
    rows.append(two_blockers)
    selected, _ = wave.build(snapshot(rows), {})
    assert selected[0]["product_external_id"] == priority["external_id"]
    assert two_blockers["external_id"] not in {item["product_external_id"] for item in selected}
    assert [int(item["blocker_count"]) for item in selected] == sorted(int(item["blocker_count"]) for item in selected)


def test_all_strict_blockers_are_preserved_and_outputs_have_hashes() -> None:
    wave = module()
    rows = [row(index) for index in range(1, 301)]
    for item in rows:
        item.update({
            "verified_media_count": 0, "short_description": "short", "matching_applied_description_count": 0,
            "product_url_locale": "ru-RU", "seo_title": "", "seo_description": "", "availability": "in_stock",
            "price": "200.00", "current_price_evidence_count": 2, "fresh_matching_price_evidence_count": 0,
        })
    selected, summary = wave.build(snapshot(rows), {})
    first = selected[0]
    assert first["description_blockers"] == "DESCRIPTION_TOO_SHORT|DESCRIPTION_APPLIED_MATCH_MISSING"
    assert first["media_blockers"] == "EXACT_VERIFIED_MEDIA_MISSING"
    assert "URL_LOCALE_INVALID" in first["url_seo_blockers"]
    assert first["price_blockers"] == "VISIBLE_PRICE_CURRENT_EVIDENCE_COUNT_INVALID|VISIBLE_PRICE_FRESH_MATCH_MISSING"
    assert int(first["blocker_count"]) == len(first["all_blockers"].split("|"))

    output_dir = SCRIPT.parents[1] / "docs" / "audits" / "generated" / "wave250-test-output"
    wave.write_outputs(selected, summary, {}, [{"path": "fixture", "sha256": "abc"}], output_dir)
    output_json = json.loads((output_dir / wave.OUTPUT_JSON.name).read_text(encoding="utf-8"))
    assert output_json["outputs"]["csv"]["sha256"] == wave.sha256(output_dir / wave.OUTPUT_CSV.name)
    assert output_json["outputs"]["processed_no_repeat_ledger"]["sha256"] == wave.sha256(output_dir / wave.OUTPUT_LEDGER.name)
    assert output_json["payload_sha256"]
    with (output_dir / wave.OUTPUT_CSV.name).open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 300
    with (output_dir / wave.OUTPUT_LEDGER.name).open(encoding="utf-8-sig", newline="") as stream:
        ledger = list(csv.DictReader(stream))
    assert len(ledger) == 300
    assert len({item["product_external_id"] for item in ledger}) == 300
    assert {item["ledger_state"] for item in ledger} == {"selected_wave250_queue"}
