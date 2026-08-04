#!/usr/bin/env python3
"""Split unclassified 1C rows into clear out-of-scope and research queues.

Only explicit office/food/household/service signals are marked out_of_scope.
Everything else stays in a research queue; this is not a classifier that
pretends uncertain technical rows are irrelevant.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def compiled(pattern: str) -> re.Pattern[str]:
    """Decode only unicode escapes while preserving regex operators.

    Current 1C vocabulary keeps Cyrillic as ``\\uXXXX`` in raw strings to
    survive Windows source encodings.  ``re`` otherwise treats these tokens
    literally, which would silently miss eligible out-of-scope rows.
    """
    return re.compile(
        _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), pattern),
        re.IGNORECASE,
    )


SCOPE_RULES = {
    "food": r"чай|кофе|печень|конфет|\bконф[\"']?|шоколад|вафл|карамел|батончик|сахар|зефир|молок|сушк|продукт|лакомств|крупа|вода питьев|сгущ|кондитер|маф",
    "office": r"бумага|папка|регистратор|маркер|ручка|канц|скоросшивател|конверт|закладк|клей[- ]каранд|линейк|блок бумаги|скотч|ножниц|карандаш|ластик|блокнот|\bфайл\b|календар|штамп|печать |краска штемп|антистеплер|зажим.*бумаг|скобы|этикетк|наклейк",
    "household": r"салфетк|стакан|тарелк|вилк|ложек|пакет(ы|ов)? |губк|средств.*мыть|средств.*стек|мусор|полотенц|массаж|мячик|стол |полка |мебел|кухонн|диспенсер|стул |тумба|шкаф|корзин.*бумаг|контейнер",
    "service_or_finance": r"доставк|комисси.*банк|\bбанк\b|товарн.*накладн|книга замечан|бсо|услуг|топливо|\bаи-?95\b|\bдт-",
    "automotive": r"\bvag\b|тормозн|масло мотор|антифриз|фильтр (маслян|салон|воздушн)|прокладк.*коллект|патрубок.*радиатор|свеча накал|пыльник|шрус|рулев|гидравлическ.*насос|глушител",
}

# The first pass intentionally stayed narrow. This second explicit vocabulary
# covers further clearly non-Microchips merchandise found in the live
# no-category sample. Unicode escapes keep PowerShell 5.1 source encoding from
# changing the meaning of Cyrillic patterns.
SCOPE_RULES.update({
    "office_extended": (
        r"\u0441\u043a\u0440\u0435\u043f\u043a|\u0442\u0440\u0435\u0443\u0433\u043e\u043b\u044c\u043d\u0438\u043a|"
        r"\u043b\u0435\u043d\u0442\u0430\s+\u043a\u043b\u0435\u0439\u043a|\u0441\u0442\u0435\u043f\u043b\u0435\u0440|"
        r"\u0442\u0435\u0442\u0440\u0430\u0434|\u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d\u0438\u043a|"
        r"\u0442\u043e\u0447\u0438\u043b\u043a|\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u043e\u0440|"
        r"\u043a\u0430\u043b\u044c\u043a\u0443\u043b\u044f\u0442\u043e\u0440|\u0434\u044b\u0440\u043e\u043a\u043e\u043b|"
        r"\u043b\u043e\u0442\u043e\u043a\s+\u0433\u043e\u0440\u0438\u0437|\u043f\u043e\u0434\u0441\u0442\u0430\u0432\u043a\u0430-\u043e\u0440\u0433\u0430\u043d\u0430\u0439\u0437\u0435\u0440|"
        r"\u0440\u0435\u0437\u0438\u043d\u043a\u0438\s*\u0434[\\/]\s*\u0431\u0430\u043d\u043a\u043d\u043e\u0442|"
        r"\u043a\u043d\u043e\u043f\u043a\u0438\s+\u0441\u0438\u043b\u043e\u0432\u044b\u0435|"
        r"\u043b\u0435\u0437\u0432\u0438\u044f\s+\u0434[\\/]\s*\u043d\u043e\u0436\u0435\u0439|"
        r"\u043a\u043b\u0435\u0439[-\u043a\u0430\u0440\u0430\u043d\u0434\u0430\u0448\u0441\u0435\u043a\u0443\u043d\u0434\u043d\u043e\u0439 ]"
    ),
    "household_extended": (
        r"\u043a\u043e\u0441\u0442\u044e\u043c\s+\u043c\u0443\u0436\u0441\u043a|\u043b\u043e\u0436\u043a\u0430\s+\u043e\u0434\u043d\u043e\u0440\u0430\u0437|"
        r"\u0432\u0438\u043b\u043a\u0438?\s+\u043e\u0434\u043d\u043e\u0440\u0430\u0437|\u0448\u0432\u0430\u0431\u0440|"
        r"\u0442\u0440\u044f\u043f\u043a\u0430\s+\u0434[\\/]\s*\u043f\u043e\u043b\u0430|\u0449\u0435\u0442\u043a\u0430-\u0441\u043c\u0435\u0442\u043a\u0430|"
        r"\u043a\u043e\u0432\u0440\u0438\u043a\s+\u0432\u043b\u0430\u0433\u043e\u0432\u043f\u0438\u0442|"
        r"\u0441\u0440\u0435\u0434\u0441\u0442\u0432\u043e\s+\u0434\u0435\u0437\u0438\u043d\u0444\u0438\u0446|"
        r"\u043f\u043b\u0435\u043d\u043a\u0430-\u0441\u0442\u0440\u0435\u0439\u0447|\u0434\u043e\u0441\u043a\u0430\s+\u0434[\\/]\s*\u043b\u0435\u043f\u043a\u0438"
    ),
})

# Exact abbreviations and commercial spellings observed in the 1C export.
# These are intentionally narrow: an item is excluded only when its own name
# names office, household, apparel/leisure or automotive merchandise.
SCOPE_RULES.update({
    "office_observed_export": (
        r"\u0441\u043a\u043e\u0440\u043e\u0448\u0438\u0432\u0430\u0442\u0435\u043b|"
        r"\u0441\u0442\u0435\u0440\u0436\u0435\u043d\u044c\s*\.?(?:\s|$)|"
        r"\u043d\u0430\u0431\u043e\u0440\s+\u043d\u0430\u0441\u0442\u043e\u043b|"
        r"\u043a\u043e\u0440\u0440\.?\s*\u0436\u0438\u0434\u043a|"
        r"\u043d\u0438\u0442\u044c\s*\u0434[\/\.]\s*\u0441\u0448\u0438\u0432\u043a"
    ),
    "household_observed_export": (
        r"\u0432\u0438\u043b\u043e\u043a\s+\u043e\u0434\u043d\u043e\u0440\u0430\u0437|"
        r"\u043e\u0434\u043d\u043e\u0440\u0430\u0437\.?(?:\s|$)|"
        r"\u043c\u044f\u0447\s*\d+\s*cm"
    ),
    "consumer_it_observed_export": (
        r"\u043c\u044b\u0448\u044c\s+(?:logitech|optical)|"
        r"\u043a-\u0442\s+logitech|\u0438\u0433\u0440\u043e\u0432\u044b\u0435\s+\u0430\u043a\u0441\u0435\u0441\u0441\u0443\u0430\u0440"
    ),
    "automotive_observed_export": (
        r"\u043f\u043e\u0434\u0443\u0448\u043a\u0430\s+\u0434\u0432\u0438\u0433\u0430\u0442\u0435\u043b\u044f|"
        r"\u043f\u043e\u0434\u0448\u0438\u043f\u043d\u0438\u043a\s+\u0441\u0442\u0443\u043f\u0438\u0447\u043d|"
        r"\u0449\u0435\u0442\u043a\u0438\s+\u043f\u043b\u043e\u0441\u043a|"
        r"\u043b\u0430\u043c\u043f\u0430\s*\(?w\d+w"
    ),
})

# Use Unicode escapes for the current source export.  Older source patterns
# above retain compatibility with historical mojibake CSV snapshots; these
# rules make the triage deterministic for the UTF-8 1C file now in use.
SCOPE_RULES.update({
    "food_utf8": (
        r"\u0447\u0430\u0439|\u043a\u043e\u0444\u0435|\u043f\u0435\u0447\u0435\u043d\u044c|\u043a\u043e\u043d\u0444\u0435\u0442|"
        r"\u0448\u043e\u043a\u043e\u043b\u0430\u0434|\u0432\u0430\u0444\u043b|\u043a\u0430\u0440\u0430\u043c\u0435\u043b|"
        r"\u0431\u0430\u0442\u043e\u043d\u0447\u0438\u043a|\u0437\u0435\u0444\u0438\u0440|\u043c\u043e\u043b\u043e\u043a\u043e|"
        r"\u043a\u0440\u0443\u043f\u0430|\u0441\u0430\u0445\u0430\u0440|\u043b\u0430\u043a\u043e\u043c\u0441\u0442\u0432"
    ),
    "office_utf8": (
        r"\u0431\u0443\u043c\u0430\u0433\u0430|\u043f\u0430\u043f\u043a\u0430|\u0440\u0443\u0447\u043a\u0430|\u043a\u0430\u043d\u0446|"
        r"\u0441\u0442\u0435\u043f\u043b\u0435\u0440|\u0442\u0435\u0442\u0440\u0430\u0434|\u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d\u0438\u043a|"
        r"\u043c\u0430\u0440\u043a\u0435\u0440|\u043a\u0430\u043b\u044c\u043a\u0443\u043b\u044f\u0442\u043e\u0440|"
        r"\u0441\u043a\u0440\u0435\u043f\u043a|\u043b\u0430\u0441\u0442\u0438\u043a|\u0431\u043b\u043e\u043a\u043d\u043e\u0442|"
        r"\u043b\u0430\u0441\u0442\u0438\u043a|\u0434\u044b\u0440\u043e\u043a\u043e\u043b"
    ),
    "construction_utf8": (
        r"\u0433\u0438\u043f\u0441\u043e\u043a\u0430\u0440\u0442\u043e\u043d|\u043f\u0440\u043e\u0444\u0438\u043b\u044c\s+(?:knauf|\u0443\u0441|\u0441\u0442\u043e\u0435\u0447)|"
        r"\u0430\u043d\u043a\u0435\u0440[- ]?\u0431\u043e\u043b\u0442|\u0441\u0430\u043c\u043e\u0440\u0435\u0437|"
        r"\u043c\u0438\u043d\u0432\u0430\u0442|\u043f\u043b\u0435\u043d\u043a\u0430\s+pvc|pvc\s+\u043f\u043b\u0435\u043d\u043a|"
        r"\u0431\u0430\u043b\u043a\u0430\s+\u0441\u0435\u043f\u0442|\u0440\u0430\u043c\u0430\s+\u0441\u0435\u0442\u043e"
    ),
    "automotive_utf8": (
        r"\u0442\u043e\u0440\u043c\u043e\u0437\u043d|\u0430\u043d\u0442\u0438\u0444\u0440\u0438\u0437|\u0441\u0432\u0435\u0447\u0430\s+\u043d\u0430\u043a\u0430\u043b|"
        r"\u0444\u0438\u043b\u044c\u0442\u0440\s+(?:\u043c\u0430\u0441\u043b\u044f\u043d|\u0441\u0430\u043b\u043e\u043d|\u0432\u043e\u0437\u0434\u0443\u0448\u043d)|"
        r"\u043c\u0430\u0441\u043b\u043e\s+\u043c\u043e\u0442\u043e\u0440|\u0441\u0442\u0435\u043a\u043b\u043e\u043e\u0447\u0438\u0441\u0442\u0438\u0442\u0435\u043b"
    ),
})

SCOPE_RULES.update({
    "office_extended_2": (
        r"\u0441\u043a\u043e\u0440\u043e\u0441\u0448\u0438\u0432\u0430\u0442\u0435\u043b|\u0441\u0442\u0435\u0440\u0436\u0435\u043d\u044c\s+\u0448\u0430\u0440|"
        r"\u043a\u043e\u0440\u0440\.?(?:\u0435\u043a\u0442|\s*\u0440\u043e\u043b\u043b)|\u043d\u0430\u0431\u043e\u0440\s+\u043d\u0430\u0441\u0442\u043e\u043b|"
        r"\u043a\u0430\u043b\u044c\u043a-?\u0440|\u0438\u0433\u043b\u0430\s+\u0434[\\/]\s*\u0441\u0448\u0438\u0432\u0430\u043d\u0438\u044f\s+\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442|"
        r"\u0440\u0435\u0433\u0438\u0441\u0442[а-я]*\s*\d+\u043c\u043c|\u0436\u0443\u0440\u043d\u0430\u043b\s+\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446|"
        r"\u043d\u0430\u0431\u043e\u0440\s+\u0440\u0443\u0447\u0435\u043a|\u043e\u0441\u043d\u0430\u0441\u0442\u043a\u0430\s+\u0434\u043b\u044f\s+\u043a\u0440\u0443\u0433\u043b\u043e\u0439\s+\u043f\u0435\u0447\u0430\u0442|"
        r"\u044f\u0440\u043b\u044b\u043a\u043e\u0434\u0435\u0440\u0436\u0430\u0442\u0435\u043b|\u043d\u0438\u0442\u044c\s+\u0434[\\/]\s*\u0441\u0448\u0438\u0432\u043a\u0438\s+\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442|"
        r"\u043d\u0430\u0431\u043e\u0440\s+\u043b\u043e\u0442\u043a\u043e\u0432\s+\u0433\u043e\u0440\u0438\u0437"
    ),
    "apparel_and_leisure": (
        r"\u043f\u0435\u0440\u0447\u0430\u0442\u043a\u0438?\s+\u0442\u0440\u0438\u043a\u043e\u0442|\u0436\u0438\u043b\u0435\u0442\s+\u0441\u043f\u0435\u0446|"
        r"\u0441\u0430\u043d\u0434\u0430\u043b\u0438|\u0443\u043a\u0440\u0430\u0448\u0435\u043d\u0438\u0435\s+\u0435\u043b\u043e\u0447\u043d|"
        r"\u0431\u0430\u043b\u0430\u043d\u0441\s+\u0431\u043e\u043b\u043b|\u043c\u043e\u043d\u0438\u0442\u043e\u0440\s+(?:lg|samsung|aoc)"
    ),
    "automotive_extended": (
        r"\u0440\u0435\u043c\u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\s+(?:\u0442\u0443\u0440\u0431\u043e\u043a\u043e\u043c\u043f\u0440\u0435\u0441\u0441\u043e\u0440|\u0441\u0443\u043f\u043f\u043e\u0440\u0442)|"
        r"\u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\s+\u043a\u043e\u043b\u043e\u0434\u043e\u043a|\u043e\u043f\u043e\u0440\u0430\s+(?:\u0448\u0430\u0440\u043e\u0432\u0430\u044f|\u0434\u0432\u0438\u0433\u0430\u0442\u0435\u043b\u044f)|"
        r"\u043f\u043e\u0434\u0448\u0438\u043f\u043d\u0438\u043a\s+(?:\u0432\u044b\u0436\u0438\u043c\u043d\u043e\u0439|\u0441\u0442\u0443\u043f\u0438\u0447\u043d\u044b\u0439)|"
        r"\u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\s+\u043d\u0430\u043f\u0440\u0430\u0432\u043b\u044f\u044e\u0449\u0435\u0439\s+\u0433\u0438\u043b\u044c\u0437\u044b|"
        r"\u043b\u0430\u043a\s+\u0431\u0435\u0441\u0446\u0432\u0435\u0442\u043d\u044b\u0439\s+\d+\u043c\u043b|\u0449\u0435\u0442\u043a\u0438\s+\u0441\u0442\u0435\u043a\u043b\u043e\u043e\u0447\u0438\u0441\u0442\u0438\u0442\u0435\u043b\u044f"
    ),
})

# Current 1C data is UTF-8.  These patterns are intentionally product-specific
# so that a technical word occurring in a legitimate component does not remove
# it from the catalogue.  For example, only "шуруп по ..." is construction;
# a generic fastener remains for later technical classification.
SCOPE_RULES.update({
    "office_utf8_current": r"\u0442\u0440\u0443\u0434\u043e\u0432\u0430\u044f\s+\u043a\u043d\u0438\u0436\u043a\u0430|\u0442\u0440\u0443\u0434\u043e\u0432\u044b\u0435\s+\u043a\u043d\u0438\u0436\u043a\u0438",
    "furniture_utf8_current": r"\u0434\u0438\u0432\u0430\u043d(?:-|\s)\u043a\u0440\u043e\u0432\u0430\u0442\u044c|\u043c\u0435\u0431\u0435\u043b\u044c",
    "construction_utf8_current": r"\u0448\u0443\u0440\u0443\u043f\s+\u043f\u043e|\u0434\u044e\u0431\u0435\u043b\u044c(?:-|\s)\u0433\u0432\u043e\u0437\u0434\u044c|\u0433\u0438\u043f\u0441\u043e\u043a\u0430\u0440\u0442\u043e\u043d|\u043c\u0438\u043d\u0432\u0430\u0442",
    "food_utf8_current": r"\u0436\u0435\u0432\.?\u043c\u0430\u0440\u043c\u0435\u043b\u0430\u0434|\u043a\u0440\u0443\u0430\u0441\u0441\u0430\u043d|\u043d\u0430\u043f\u0438\u0442\u043e\u043a",
    "leisure_utf8_current": r"\u043c\u044f\u0447\s+\u0434\u043b\u044f\s+\u0439\u043e\u0433\u0438|\bjoga\s+ball\b|\u0435\u043b\u043a\u0430\s+\u0438\u0441\u043a\u0443\u0441",
    "apparel_ppe_utf8_current": r"\u043f\u0435\u0440\u0447\u0430\u0442\u043a\u0438|\u0445\u0430\u043b\u0430\u0442\s+\u043c\u0435\u0434",
    "automotive_utf8_current": r"\u043e\u0447\u0438\u0441\u0442\u0438\u0442\u0435\u043b\u044c\s+\u0442\u043e\u0440\u043c\u043e\u0437\u043e\u0432|\u0441\u0442\u0443\u043f\u0438\u0447\u043d\u043e\u0433\u043e\s+\u043f\u043e\u0434\u0448\u0438\u043f\u043d\u0438\u043a\u0430",
    "service_utf8_current": r"\u043e\u0431\u0435\u0441\u043f\u0435\u0447\u0435\u043d\u0438\u0435\s+\u043f\u043e\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f\s+\u0431\u044e\u0434\u0436\u0435\u0442\u0430|\u0437\u0430\u043c\u0435\u043d\u0430\s+\u043f\u043e\u0434\u0448\u0438\u043f\u043d\u0438\u043a\u043e\u0432|\u0440\u0435\u043c\u043e\u043d\u0442\s+\u0430\u043a\u0431|\u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0430\s+\u0430\u043a\u0431",
    "automotive_battery_utf8_current": r"\b6\u0441\u0442\b|skat[- ]?t[ -]?auto|\u0442\u0435\u0441\u0442\u0435\u0440\s+\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u044f\s+\u0435\u043c\u043a\u043e\u0441\u0442\u0438\s+\u0430\u043a\u0431",
})


# Explicitly named procurement, promotional and packaging goods seen in the
# current 1C delta.  These terms do not describe a battery, power, lighting or
# electronic-component buyer intent, so keeping them as product pages would
# create thin and irrelevant SEO inventory. Technical packaging that is part
# of a named electronic product is not matched by these phrases.
SCOPE_RULES.update({
    "non_catalogue_procurement_utf8_current": (
        r"\u043a\u0440\u0435\u043a\u0435\u0440|\u0447\u0438\u043f\u0441\u044b?|\u043a\u0430\u043a\u0430\u043e(?:[- ]?\u043d\u0430\u043f\u0438\u0442)?|\u0446\u0438\u043a\u043e\u0440\u0438\u0439|\u043f\u0430\u0441\u0442\u0438\u043b\u0430|"
        r"\u043c\u0438\u0448\u0443\u0440\u0430|\u0431\u0443\u0441\u044b\s+\u0434\u043b\u044f\s+\u0435\u043b\u043a\u0438|\u0448\u0430\u0440\u044b?\s+\u043d\u043e\u0432\u043e\u0433\u043e\u0434|\u0443\u043a\u0440\u0430\u0448\u0435\u043d\u0438\u0435\s+\u0435\u043b|"
        r"\u043b\u0430\u043d\u044a\u044f\u0440\u0434|\u0434\u0438\u0437\u0430\u0439\u043d[- ]\u043c\u0430\u043a\u0435\u0442|\u0441\u0442\u0438\u043a\u0435\u0440\s+\d|\u0442\u0430\u0431\u043b\u0438\u0447\u043a\u0430\s+\u043f\u0432\u0445|"
        r"\u043b\u043e\u0436\u043a\u0438?\s+\u0441\u0442\u043e\u043b\u043e\u0432|\u043a\u0440\u0443\u0436\u043a\u0430\s+\u0441\s+\u043d\u0430\u043d\u0435\u0441\u0435\u043d|\u0432\u0435\u0448\u0430\u043b\u043a\u0430|\u0441\u0430\u043b\u0430\u0442\u043d\u0438\u043a|\u043c\u043e\u043b\u043e\u0442\u0438\u043b\u043a\u0430\s+\u0434\u043b\u044f\s+\u043f\u0435\u0440\u0446\u0430|"
        r"\u0433\u043e\u0444\u0440\u043e\u044f\u0449\u0438\u043a|\u0441\u0442\u0440\u0435\u0442\u0447[- ]\u043f\u043b\u0435\u043d\u043a|\u0432\u043e\u0437\u0434\u0443\u0448\u043d\u043e(?:-\u043f\u0443\u0437\u044b\u0440\u044c\u043a\u043e\u0432\u0430\u044f)\s+\u043f\u043b\u0435\u043d\u043a|"
        r"\u043a\u043e\u0440\u043e\u0431\u043a\u0430\s+\d{2,}.*(?:\u043a\u0430\u0440\u0442\u043e\u043d|\u0433\u043e\u0444\u0440)|\u043f\u043b\u0435\u043d\u043a\u0430\s+pvc|pvc\s+\u0442\u0435\u0440\u043c\u043e\u043f\u043b\u0435\u043d\u043a|"
        r"\u0430\u0432\u0442\u043e\u043c\u043e\u0431\u0438\u043b\u044c|\u043c\u043e\u0442\u043e\u0440\u043d\u043e\u0435\s+\u043c\u0430\u0441\u043b\u043e|\u043e\u043f\u043e\u0440\u0430\s+\u0430\u0432\u0442\u043e\u043c\u043e\u0431\u0438\u043b|\u0430\u043f\u0442\u0435\u0447\u043a\u0430\s+\u043f\u0435\u0440\u0432\u043e\u0439\s+\u043f\u043e\u043c\u043e\u0449\u0438|\u043c\u0430\u044f\u043a\s+\u0438\u043c\u043f\u0443\u043b\u044c\u0441\u043d\u044b\u0439"
    )
})

# A final, deliberately literal pass over the present 1C residue.  Abbreviated
# names from the accounting export are matched here rather than by broad nouns:
# this keeps real technical goods for classification while removing obvious
# seasonal, office, service and generic-accounting rows from the SEO inventory.
SCOPE_RULES.update({
    "seasonal_and_promotional_observed": (
        r"\u0433\u0438\u0440\u043b\u044f\u043d\u0434\u0430\s+\u043d\u043e\u0432\u043e\u0433\u043e\u0434|"
        r"\u0435\u043b\u043e\u0447\u043d\u043e\u0435\s+\u0443\u043a\u0440\u0430\u0448|"
        r"\u0443\u043a\u0440\u0430\u0448\.?\u043d\u043e\u0432|\u043d\u0430\u0431\u043e\u0440\s+\u0448\u0430\u0440|"
        r"\u0434\u043e\u0436\u0434\u0438\u043a\s+\"?\u043d\u043e\u0432\u043e\u0433\u043e\u0434|"
        r"\u0432\u0435\u0440\u0445\.?\s*\u043d\u0430\s+\u0435\u043b\u043a\u0443|\u043c\u0438\u0448\u0443\u0440\u0430"
    ),
    "household_observed_batch": (
        r"\u043a\u043e\u0432\u0440\u0438\u043a\s+\u0433\u0440\u044f\u0437\u0435\u0437\u0430\u0449\u0438\u0442|"
        r"\u0445\u043e\u0437\u044f\u0439\u0441\u0442\u0432\u0435\u043d\u043d\u043e\u0435\s+\u043c\u044b\u043b\u043e|"
        r"\u0431\u0443\u0442\u044b\u043b\u044c\s+\u043f\u043a\s+18[,\.]9"
    ),
    "generic_accounting_rows": (
        r"^\u043f\u0440\u043e\u043c\u0442\u043e\u0432\u0430\u0440\u044b$|^\u0442\u043e\u0432\u0430\u0440\u044b$|^\d{5,8}$"
    ),
    "service_and_document_observed": (
        r"\u0440\u0435\u043c\u043e\u043d\u0442\s+\u0438\s+\u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0430|"
        r"\u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u0435\s+\u0440\u0430\u0431\u043e\u0442|"
        r"\u0441\u0435\u0440\u0432\u0438\u0441\u043d\u0430\u044f\s+\u043a\u043d\u0438\u0436\u043a\u0430|"
        r"\u0441\u0435\u0440\u0442\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f|"
        r"\u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0439\s+\u0434\u0435\u043a\u043b\u0430\u0440\u0430\u0446"
    ),
})

# Accounting titles regularly abbreviate a product name and occasionally lose
# a repeated letter.  These are still unambiguous exclusions: the patterns
# require a consumer-gaming phrase or a named passenger-car model, rather than
# a generic word that could describe industrial equipment.
SCOPE_RULES.update({
    "consumer_gaming_accessory_current": r"\u0438\u0433\u0440\u043e\u0432\u044b\u0435\s+\u0430\u043a\u0441\u0435+\u0441\u0443\u0430\u0440",
    "automotive_model_or_brake_current": (
        r"\b(?:nissan|qashqai|x[- ]?trail|mazda\s+cx[- ]?5)\b|"
        r"\u0434\u0438\u0441\u043a\.?\u0442\u043e\u0440\u043c|"
        r"\u0440/\u043a\s+\u043d\u0430\u043f\u0440\u0430\u0432\u043b\.\s*\u0441\u0443\u043f\."
    ),
})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-of-scope", type=Path, required=True)
    parser.add_argument("--research", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.input.open(encoding="utf-8-sig", newline="")))
    out, research = [], []
    counts: Counter[str] = Counter()
    for row_number, row in enumerate(rows, start=2):
        external_id = (row.get("product_external_id") or row.get("external_id") or "").strip()
        name = (row.get("name") or "").strip()
        if not external_id or not name:
            continue
        normalized = {
            "row_number": row.get("row_number") or str(row_number),
            "product_external_id": external_id,
            "name": name,
            "rule": row.get("rule") or "",
        }
        text = name.casefold()
        matched = next((name for name, pattern in SCOPE_RULES.items() if compiled(pattern).search(text)), None)
        if matched:
            out.append({**normalized, "scope_reason": matched})
            counts[matched] += 1
        else:
            research.append({**normalized, "scope_reason": "requires_technical_or_catalogue_research"})

    args.out_of_scope.parent.mkdir(parents=True, exist_ok=True)
    fields = ["row_number", "product_external_id", "name", "rule", "scope_reason"]
    for path, data in [(args.out_of_scope, out), (args.research, research)]:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
    summary = {
        "unclassified_input": len(rows),
        "clear_out_of_scope": len(out),
        "requires_research": len(research),
        "out_of_scope_by_reason": dict(sorted(counts.items())),
        "invariant": "Only explicit non-catalogue wording is out_of_scope; all other rows remain for technical research.",
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
