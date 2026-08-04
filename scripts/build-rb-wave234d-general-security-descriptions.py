#!/usr/bin/env python3
"""Build source-backed General Security descriptions from the pinned official catalogue."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
IDENTITIES = ROOT / "docs/imports/rb-verified-oem-identities-wave234c-general-security-2026-07-29.json"
SNAPSHOT = ROOT / "docs/audits/sources/wave234c/general-security-product.html"
OUTPUT = ROOT / "docs/imports/rb-source-backed-descriptions-wave234d-general-security-2026-07-29.json"
SUMMARY = ROOT / "docs/audits/generated/rb-wave234d-general-security-descriptions.summary.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_model(value: str) -> str:
    return re.sub(r"[\s-]+", "", value.upper())


def clean(value: str) -> str:
    return " ".join(value.replace("а/ч", "А·ч").split())


def title_ends_with_exact_mpn(name: str, mpn: str) -> bool:
    without_summary = re.sub(r"\s*\([^)]*(?:AGM|GEL|LiFePO4)[^)]*\)\s*$", "", name, flags=re.I)
    name_tokens = re.findall(r"[^\W_]+", without_summary.lower(), flags=re.UNICODE)
    mpn_tokens = re.findall(r"[^\W_]+", mpn.lower(), flags=re.UNICODE)
    return bool(mpn_tokens) and name_tokens[-len(mpn_tokens):] == mpn_tokens


def main() -> None:
    identities = json.loads(IDENTITIES.read_text(encoding="utf-8"))["products"]
    if len(identities) != 29:
        raise SystemExit(f"General Security identity manifest drift: rows={len(identities)}")
    soup = BeautifulSoup(SNAPSHOT.read_text(encoding="utf-8"), "html.parser")
    cards = {}
    for article in soup.select("article.node-product"):
        heading = article.select_one("h2")
        if not heading:
            continue
        values = {}
        for block in article.select(".card_min_block"):
            parts = [clean(node.get_text(" ", strip=True)) for node in block.find_all("div", recursive=False)]
            if len(parts) == 2:
                values[parts[0]] = parts[1]
        cards[compact_model(heading.get_text(" ", strip=True))] = values
    if len(cards) < 80:
        raise SystemExit(f"Official General Security card parse drift: cards={len(cards)}")

    products = []
    excluded_nonterminal_mpn = []
    for identity in identities:
        if not title_ends_with_exact_mpn(identity["current_name"], identity["mpn"]):
            excluded_nonterminal_mpn.append(identity["external_id"])
            continue
        attrs = cards.get(compact_model(identity["mpn"]))
        if not attrs or not all(key in attrs for key in ("Напряжение", "Ёмкость", "Размеры", "Вес")):
            raise SystemExit(f"Exact official card missing fields for {identity['external_id']} {identity['mpn']}")
        products.append({
            "external_id": identity["external_id"], "identity_scope": "exact",
            "manufacturer": "General Security", "mpn": identity["mpn"],
            "display_name": identity["current_name"],
            "technology": "AGM, клапанно-регулируемая свинцово-кислотная батарея (VRLA)",
            "source_url": identity["source_url"], "source_kind": "official_manufacturer_catalogue",
            "source_tier": "manufacturer_primary", "source_publisher": "General Security",
            "manufacturer_primary": True, "evidence_scope": "exact_model", "checked_at": "2026-07-29",
            "technical_attributes": {
                "Номинальное напряжение": attrs["Напряжение"],
                "Номинальная ёмкость": attrs["Ёмкость"],
                "Габариты": attrs["Размеры"],
                "Масса": attrs["Вес"],
                "Технология": "AGM, клапанно-регулируемая свинцово-кислотная батарея (VRLA)",
            },
        })
    manifest = {
        "schema_version": 1,
        "purpose": "Exact General Security technical descriptions from a pinned official catalogue; no price, stock, warranty, publication, URL or media-rights claim.",
        "locale": "ru-BY", "products": products,
    }
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema_version": 1, "batch": "wave234d_general_security_descriptions", "checked_at": "2026-07-29",
        "identity_manifest": {"path": IDENTITIES.relative_to(ROOT).as_posix(), "sha256": sha256(IDENTITIES), "rows": len(identities)},
        "source": {"path": SNAPSHOT.relative_to(ROOT).as_posix(), "sha256": sha256(SNAPSHOT), "parsed_cards": len(cards)},
        "excluded_nonterminal_mpn_external_ids": excluded_nonterminal_mpn,
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(products)},
        "policy": {"manufacturer_primary_only": True, "database_mutations": 0, "commercial_mutations": 0,
                   "media_rights_claims": 0, "publication_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(products), "source_cards": len(cards)}))


if __name__ == "__main__":
    main()
