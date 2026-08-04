from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "build-rb-manufacturer-series-expansion.py"
SPEC = importlib.util.spec_from_file_location("manufacturer_series_expansion", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_slugify_preserves_plus_as_an_identity_bearing_token() -> None:
    assert MODULE.slugify("EnerSys-12HX650F-FR+") == "enersys-12hx650f-fr-plus"
    assert MODULE.slugify("EnerSys-12HX650F-FR") == "enersys-12hx650f-fr"


def test_build_merges_exact_model_facts_over_series_facts() -> None:
    source = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "locale": "ru-BY",
        "category_external_id": "seo:batteries-industrial",
        "category_slug": "catalog/industrial-batteries/batteries-industrial",
        "series": [
            {
                "manufacturer": "EnerSys",
                "series": "PowerSafe GFM",
                "models": ["6GFM200"],
                "source_url": "https://example.test/official.pdf",
                "technology": "VRLA AGM",
                "facts": {"Технология": "VRLA AGM", "Напряжение": "серия 6–12 В"},
                "model_facts": {
                    "6GFM200": {"Напряжение": "12 В", "Ёмкость": "200 А·ч"}
                },
                "name_template": "Аккумулятор {manufacturer} {model}",
            }
        ],
    }

    candidates, descriptions, _ = MODULE.build(source)

    expected = {"Технология": "VRLA AGM", "Напряжение": "12 В", "Ёмкость": "200 А·ч"}
    assert candidates["products"][0]["technical_attributes"] == expected
    assert descriptions["products"][0]["technical_attributes"] == expected


def test_build_keeps_exact_mpn_when_human_model_label_is_used() -> None:
    source = {
        "schema_version": 1,
        "site_key": "microchips-by",
        "locale": "ru-BY",
        "category_external_id": "seo:batteries-industrial",
        "category_slug": "catalog/industrial-batteries/batteries-industrial",
        "series": [
            {
                "manufacturer": "Exide",
                "series": "Classic OPzS Solar",
                "models": ["NVSL020190WC0FB"],
                "model_labels": {"NVSL020190WC0FB": "OPzS Solar 190"},
                "source_url": "https://example.test/official.pdf",
                "technology": "flooded lead-acid OPzS",
                "facts": {"Technology": "OPzS"},
                "name_template": "Industrial battery {manufacturer} {label} (MPN {model})",
            }
        ],
    }

    candidates, descriptions, previews = MODULE.build(source)

    candidate = candidates["products"][0]
    assert candidate["mpn"] == "NVSL020190WC0FB"
    assert candidate["name"] == "Industrial battery Exide OPzS Solar 190 (MPN NVSL020190WC0FB)"
    assert candidate["slug"] == "exide-nvsl020190wc0fb"
    assert descriptions["products"][0]["mpn"] == "NVSL020190WC0FB"
    assert previews["products"][0]["product_slug"] == "exide-nvsl020190wc0fb"
