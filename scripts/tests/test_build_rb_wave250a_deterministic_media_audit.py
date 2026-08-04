from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-rb-wave250a-deterministic-media-audit.py"
SPEC = importlib.util.spec_from_file_location("wave250a", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def target() -> dict[str, object]:
    return {
        "external_id": "bitrix:1", "product_id": 1, "site_product_id": 2,
        "name": "Battery Exact-12", "manufacturer": "Vendor", "mpn": "Exact-12",
        "category_external_id": "seo:batteries-ups", "product_path": "/catalog/exact-12",
    }


def media() -> dict[str, object]:
    return {
        "external_id": "bitrix:1", "media_id": 10, "storage_path": "products/exact-12.jpg",
        "content_sha256": "a" * 64, "actual_sha256": "a" * 64, "local_exists": True,
        "source_kind": "manufacturer_primary",
        "source_page_url": "https://manufacturer.example/products/exact-12",
        "source_asset_url": "https://manufacturer.example/assets/exact-12.jpg",
        "rights_basis": "Licensed manufacturer asset with reuse permission.",
        "verification_status": "needs_review", "hash_distinct_product_count": 1,
        "verified_same_identity_hash_count": 0,
    }


def test_machine_proven_exact_official_local_asset_is_candidate() -> None:
    row = MODULE.classify_media(target(), media(), set(), set(), set())
    assert row["decision"] == "DETERMINISTIC_PROMOTION_CANDIDATE"
    assert row["identity_evidence"] == "exact_mpn_in_official_source_url"
    assert row["rights_evidence"] == "reusable"


def test_prior_ledger_excludes_entire_product_before_other_gates() -> None:
    row = MODULE.classify_media(target(), media(), {"bitrix:1"}, set(), set())
    assert row["decision"] == "HOLD"
    assert row["blocker"] == "prior_product_ledger"


def test_unique_company_owned_legacy_attachment_still_needs_exact_identity() -> None:
    candidate = media()
    candidate.update({
        "source_kind": "legacy_exact_preview",
        "source_page_url": "https://microchips.by/catalog/1/",
        "source_asset_url": "",
        "rights_basis": "Company-owned Microchips legacy Bitrix upload backup.",
    })
    row = MODULE.classify_media(target(), candidate, set(), set(), set())
    assert row["decision"] == "HOLD"
    assert row["blocker"] == "exact_identity_not_machine_proven_without_visual_guess"


def test_shared_hash_and_missing_rights_fail_closed() -> None:
    shared = media()
    shared["hash_distinct_product_count"] = 2
    assert MODULE.classify_media(target(), shared, set(), set(), set())["blocker"] == "content_hash_shared_across_distinct_products"
    no_rights = media()
    no_rights["rights_basis"] = "Official manufacturer asset; no explicit redistribution licence found."
    assert MODULE.classify_media(target(), no_rights, set(), set(), set())["blocker"] == "reusable_rights_not_proven"


def test_verified_same_identity_hash_can_prove_identity_but_not_override_no_repeat() -> None:
    candidate = media()
    candidate.update({
        "source_kind": "legacy_exact_preview", "source_page_url": "https://microchips.by/1/",
        "verified_same_identity_hash_count": 1, "hash_distinct_product_count": 2,
    })
    passed = MODULE.classify_media(target(), candidate, set(), set(), set())
    assert passed["decision"] == "DETERMINISTIC_PROMOTION_CANDIDATE"
    held = MODULE.classify_media(target(), candidate, set(), set(), {"a" * 64})
    assert held["blocker"] == "prior_content_hash"
