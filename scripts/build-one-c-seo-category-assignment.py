#!/usr/bin/env python3
"""Produce conservative 1C -> target SEO category assignments.

Only high-signal name/path rules are applied.  An unknown row is reported,
never forced into a misleading category merely to make a dashboard reach 100%.
The output is accepted by catalog:assign-site-product-categories.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


_UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")


def has(text: str, *patterns: str) -> bool:
    """Match a rule while supporting the deliberate ``\\uXXXX`` vocabulary.

    The current source keeps its newer Cyrillic patterns as ASCII unicode
    escapes so the script itself stays portable between Windows code pages.
    Raw regex strings do not decode those escapes automatically, so decode
    only the unicode tokens (not other regex escapes such as ``\\b``) before
    matching.
    """
    return any(
        re.search(
            _UNICODE_ESCAPE.sub(lambda match: chr(int(match.group(1), 16)), pattern),
            text,
            re.IGNORECASE,
        )
        for pattern in patterns
    )


def category(name: str, path: str) -> tuple[str | None, str]:
    text = norm(f"{name} {path}")
    # High-confidence power taxonomy. Keep these rules before the historical
    # broad battery/application rules: a UPS device and a battery intended for
    # a UPS are different buyer tasks and must never share one SEO leaf.
    if has(text, r"\bcj1w-bat01\b"):
        return "seo:primary-cells", "plc_backup_primary_battery_model"
    if has(text, r"\bm4t28-br12sh1\b"):
        return None, "power_item_type_requires_review"
    battery_guard = has(
        text,
        r"\u0430\u043a\u043a\u0443\u043c\u0443\u043b\u044f\u0442\u043e\u0440",
        r"\u0430\u043a\u043a\u0443\u043c\u0443\u043b\u044f\u0442\u043e\u0440\u043d\u0430\u044f\s+\u0431\u0430\u0442\u0430\u0440\u0435\u044f",
        r"\u0431\u0430\u0442\u0430\u0440\u0435\u0439\u043d\w*\s+(?:\u0431\u043b\u043e\u043a|\u043c\u043e\u0434\u0443\u043b)",
    )
    explicit_ups = has(
        text,
        r"^(?:\u0438\u0431\u043f\b|\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\s+\u0431\u0435\u0441\u043f\u0435\u0440\u0435\u0431\u043e\u0439\u043d\u043e\u0433\u043e\s+\u043f\u0438\u0442\u0430\u043d\u0438\u044f\b)",
    )
    if explicit_ups and not battery_guard:
        return "seo:ups-systems", "explicit_ups_device"
    if has(text, r"\u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c\s+\u0440\u0436\u0430\u0432\u0447\u0438\u043d\u044b"):
        return "seo:assembly-materials", "rust_treatment_material"
    if has(text, r"\u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c\s+\u0447\u0430\u0441\u0442\u043e\u0442\u044b"):
        return "seo:electrical-protection-control", "frequency_drive"
    if has(text, r"\u0437\u0430\u0440\u044f\u0434\u043d\u043e\u0435\s+\u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e", r"\u0441\u0435\u0442\u0435\u0432\u043e\u0435\s+\u0437/?\u0443"):
        return "seo:chargers", "explicit_charger"
    if has(text, r"\u0431\u043b\u043e\u043a\s+\u043f\u0438\u0442\u0430\u043d\u0438\u044f", r"\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\s+\u043f\u0438\u0442\u0430\u043d\u0438\u044f", r"\u0441\u0435\u0442\u0435\u0432\u043e\u0439\s+\u0430\u0434\u0430\u043f\u0442\u0435\u0440", r"\u0430\u0434\u0430\u043f\u0442\u0435\u0440\s+\u043f\u0438\u0442\u0430\u043d\u0438\u044f", r"\bpower supply\b"):
        return "seo:power-supplies", "explicit_power_supply"
    if has(text, r"\b(?:ac[- ]?dc|dc[- ]?dc)\b", r"\u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c\s+\u043d\u0430\u043f\u0440\u044f\u0436\u0435\u043d\u0438\u044f", r"\u0438\u043d\u0432\u0435\u0440\u0442\u043e\u0440\b"):
        return "seo:power-converters", "explicit_power_converter"
    if battery_guard and has(text, r"\u0431\u0435\u0441\u043f\u0435\u0440\u0435\u0431\u043e\u0439\u043d", r"\b\u0438\u0431\u043f\b", r"\bups\b"):
        return "seo:batteries-ups", "ups_battery_or_module"
    # Device/application leaves must win over generic battery terms.
    if has(text, r"бесперебойн", r"\bибп\b", r"\bups\b"):
        return "seo:batteries-ups", "ups"
    if has(text, r"тягов", r"погрузчик", r"электрокар"):
        return "seo:batteries-traction", "traction"
    if has(text, r"ноутбук", r"\blaptop\b", r"thinkpad", r"macbook"):
        return "seo:replacement-laptops", "laptop"
    if has(text, r"iphone", r"смартфон", r"телефон", r"samsung", r"xiaomi", r"huawei", r"nokia", r"sony ericsson"):
        return "seo:replacement-mobile", "mobile_device"
    if has(text, r"canon", r"nikon", r"фотоаппарат", r"видеокамер", r"\bcamera\b"):
        return "seo:replacement-photo", "photo_device"
    if has(text, r"шуруповерт", r"электроинструмент", r"makita", r"bosch", r"dewalt", r"metabo"):
        return "seo:replacement-tools", "power_tool"
    if has(text, r"медиц", r"дефибрил", r"инфуз", r"монитор пациент"):
        return "seo:replacement-medical", "medical"
    if has(text, r"электросамокат", r"электровелосипед", r"гироскутер", r"электротранспорт"):
        return "seo:replacement-transport", "electric_transport"
    if has(text, r"зарядн", r"\bcharger\b"):
        return "seo:chargers", "charger"
    # Electrical distribution products have a distinct buyer task and must
    # not be folded into the postponed electronic-components assortment.
    # These phrases name the item class directly, so they remain safe for a
    # 1C-only draft catalog even when a model title is otherwise terse.
    if has(text, r"\u0430\u0432\u0442\.?\s*\u0432\u044b\u043a\u043b", r"\u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\w*\s+\u0432\u044b\u043a\u043b\u044e\u0447"):
        return "seo:electrical-protection-control", "circuit_breaker"
    if has(text, r"\bdin[- ]?\u0440\u0435\u0439\u043a", r"\u0433\u0438\u043b\u044c\u0437\u0430\s+\u0441\u043e\u0435\u0434\u0438\u043d\u0438\u0442\u0435\u043b\u044c\u043d"):
        return "seo:electrical-installation", "electrical_installation"
    if has(text, r"\u0432\u044b\u0432\u043e\u0434\u044b\s+\u043f\u043e\u043b\u044e\u0441\u043d\u044b\u0435"):
        return "seo:batteries-accessories", "battery_terminal"
    if has(text, r"блок питания", r"источник питания", r"\bpower supply\b", r"инвертор"):
        return "seo:power-systems", "power_system"
    if has(text, r"фонар"):
        return "seo:flashlights", "flashlight"
    if has(text, r"микросхем", r"диод", r"транзист", r"резистор", r"конденсатор", r"варистор", r"стабилитрон", r"тиристор", r"оптопар", r"\bigbt\b", r"разъ[её]м", r"плата защиты", r"контроллер заряда", r"предохранител", r"термореле", r"микропереключател", r"датчик", r"провод", r"кабель", r"клемм", r"наконечник", r"термоусад", r"никелев[аяую]+ лент", r"светодиод", r"\bled\b", r"корпус.*элемент", r"ионистор"):
        return "seo:electronic-components", "electronic_component"
    if has(text,
           r"стеллаж", r"складск", r"тележк",
           r"стойка\s+сам\b", r"\bсам\s+стойка"):
        return "seo:warehouse-equipment", "warehouse"
    if has(text, r"opzs", r"opzv", r"промышленн"):
        return "seo:batteries-industrial", "industrial_battery"
    if has(text, r"батарейк", r"элемент питания", r"литиевый элемент", r"\bls\s*\d", r"\bcr\d", r"\blr\d", r"\b6lr\d", r"\br\d{1,2}\b"):
        return "seo:primary-cells", "primary_cell"
    if has(text, r"аккумулятор", r"\b18650\b", r"\b14500\b", r"\b26650\b", r"ni-?mh", r"ni-?cd", r"lifepo", r"li-?ion", r"литий[- ]ион"):
        return "seo:rechargeable-cells", "rechargeable_cell"
    # Explicit technical nouns and brands whose product class is not
    # ambiguous.  They are intentionally narrow: generic brand names (for
    # example Panasonic) still require a product-class signal above.
    if has(text,
           r"\u043e\u043f\u0442\u0440\u043e\u043d", r"\u0432\u0435\u043d\u0442\u0438\u043b\u044f\u0442\u043e\u0440",
           r"\u0440\u0430\u0434\u0438\u043e\u043c\u043e\u0434\u0443\u043b\u044c", r"\u0441\u0435\u043d\u0441\u043e\u0440\u043d\u0430\u044f\s+\u043f\u0430\u043d\u0435\u043b\u044c",
           r"\u0436\u043a\u0438[- ]?\u0434\u0438\u0441\u043f\u043b\u0435\u0439", r"\u0441\u0432\u0435\u0442\u043e\u0434\u0438\u043e\u0434\u043d\u0430\u044f\s+\u043b\u0435\u043d\u0442\u0430",
           r"\beth(?:ernet)?\b"):
        return "seo:electronic-components", "explicit_electronic_component"
    if has(text, r"\b(?:renata|fanso|tekcell|tadiran|saft|zenipower)\b", r"\b3r12\b", r"\b[cс]r\d"):
        return "seo:primary-cells", "explicit_primary_cell"
    if has(text, r"\u0430\u043a\u043a?\u043c\u0443\u043b\u044f\u0442\u043e\u0440"):
        return "seo:rechargeable-cells", "explicit_rechargeable_cell"

    # Conservative second-pass rules for model formats that carry an
    # unambiguous technical meaning even when an import title omits the
    # Russian generic word. Keep these below more specific device rules.
    if has(text, r"\b(?:a23|23a|er\d{4,}|cr\d{2,}|br\d{2,}|ls\s*\d{4,}|lr\d{2,})\b"):
        return "seo:primary-cells", "primary_cell_model"
    if has(text, r"\b(?:\d+\s*pzs|golf\s+cart)\b"):
        return "seo:batteries-traction", "traction_battery_model"
    if has(text, r"\u043a\u043e\u0440\u043f\u0443\u0441\s+(?:abc|\u0430\u0432\u0441|es|\u0430\u043a\u0431)|\u043a\u0440\u044b\u0448\u043a\u0430\s+\u043a\s+\u0430\u043a\u0431"):
        return "seo:battery-enclosures", "battery_enclosure"
    if has(text, r"\b(?:\u043a\u043e\u043d\u0442\u0430\u043a\u0442|\u0448\u0442\u0435\u043a\u0435\u0440|\u0440\u0430\u0437\u044a[\u0435\u0451]\u043c|\u043a\u043b\u0435\u043c\u043c\u0430)\b"):
        return "seo:electronic-components", "utf8_connector_or_contact"
    if has(text,
           r"\u0441\u0435\u0442\u0435\u0432\u043e\u0439\s+\u0444\u0438\u043b\u044c\u0442\u0440",
           r"\u0443\u0434\u043b\u0438\u043d\u0438\u0442\u0435\u043b\u044c\s+(?!1/4)",
           r"\u0440\u043e\u0437\u0435\u0442\u043a\u0430.*(?:\u043d\u0430\u0440\u0443\u0436|\u043e\u0442\u043a\u0440\u044b\u0442|\u0437\u0430\u0437\u0435\u043c|\u0443\u0441\u0442\u0430\u043d|\d{2}\s*a|\d\s*p\+e)"):
        return "seo:power-accessories", "mains_accessory"
    if has(text, r"\b(?:np\s*[- ]?\d+(?:[- ]?\d+(?:[.,]\d+)?)?\s*(?:ah|\u0430\u0447|v|\u0432)|gb\s*\d+[- ]\d+|fiamm\s+12fgh)\b"):
        return "seo:batteries-ups", "stationary_battery_model_utf8"
    if has(text, r"\b(?:a98l|17(?:47|56)-ba|mr-bat|2cr5|4lr44|4r25|6f22|6lf22|cr[- ]?2032|cr[- ]?123)\b"):
        return "seo:primary-cells", "primary_or_plc_battery_model"
    if has(text, r"\b(?:lp\d{5,}|lr?\d{2,}.*mah)\b", r"\u0430\u043a\u043a\u0443\u043c\u043c?\u0443\u043b\u044f\u0442\u043e\u0440\w*\s+\u0431\u0430\u0442\u0430\u0440\u0435\u044f.*\d+(?:[.,]\d+)?\s*(?:mah|\u043c\u0430\u0447)"):
        return "seo:rechargeable-cells", "rechargeable_pack_model"
    if has(text, r"\u043b\u0438\u0442\u0438\u0439[- ]\u043f\u043e\u043b\u0438\u043c\u0435\u0440", r"\bli[- ]?po\b"):
        return "seo:rechargeable-cells", "lipo_cell"
    if has(text, r"\blir\d"):
        return "seo:rechargeable-cells", "rechargeable_lir_model"
    if has(text, r"\u044d\u043b\.?\s*\u043f\u0438\u0442\u0430\u043d\u0438\u044f", r"\u044d\u043b\u0435\u043c\u0435\u043d\u0442\s+\u043f\u0438\u0442\u0430\u043d\u0438\u044f"):
        return "seo:primary-cells", "utf8_primary_cell_wording"
    # These two groups have their own buyer intent and comparison attributes.
    # Do not flatten them into generic electronic components: meters need
    # ranges/accuracy, while UAV parts need model and voltage compatibility.
    if has(text,
           r"\u043c\u0443\u043b\u044c\u0442\u0438\u043c\u0435\u0442\u0440", r"\u0442\u043e\u043a\u043e\u0432\u044b\u0435\s+\u043a\u043b\u0435\u0449\u0438",
           r"\u0442\u0435\u0441\u0442\u0435\u0440\s+(?:\u043d\u0430\u043f\u0440\u044f\u0436\u0435\u043d\u0438\u044f|usb|\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u044f\s+\u0435\u043c\u043a\u043e\u0441\u0442\u0438)",
           r"\u0449\u0443\u043f\u044b?\s+\u0434\u043b\u044f\s+\u043c\u0443\u043b\u044c\u0442\u0438\u043c\u0435\u0442\u0440", r"\u0449\u0443\u043f\u044b?\s+\u043a\u0432\u0442"):
        return "seo:measurement-equipment", "measurement_equipment"
    if has(text,
           r"\u0431\u043f\u043b\u0430", r"\u043a\u0432\u0430\u0434\u0440\u043e\u043a\u043e\u043f\u0442\u0435\u0440", r"\b(?:dji|betafpv|iflight|hqprop)\b",
           r"\u043f\u0440\u043e\u043f\u0435\u043b\u043b\u0435\u0440", r"\u0431\u0435\u0441\u043a\u043e\u043b\u043b\u0435\u043a\u0442\u043e\u0440\u043d\u044b\u0439\s+\u043c\u043e\u0442\u043e\u0440",
           r"\b(?:fpv|skayzone)\b"):
        return "seo:drone-components", "uav_component"
    if has(text, r"\u0441\u0432\u0435\u0442\u0438\u043b\u044c\u043d\u0438\u043a", r"\u043f\u0430\u043d\u0435\u043b\u044c\s+\u0441\s*\u0434\u0440\u0430\u0439\u0432\u0435\u0440"):
        return "seo:lighting-fixtures", "lighting_fixture"
    if has(text, r"\u043b\u0430\u043c\u043f", r"\becola\b", r"\bcamelion\b", r"\bled(?:bulb|lustre)\b", r"\btl-d\b", r"\bmaster\s+pl\b"):
        return "seo:lighting-lamps", "lighting_lamp"
    if has(text, r"\b(?:6[- ]?g?fm|dtm\d|hrl\s*\d|gpl\s*\d|12fgh\d|csb\s+(?:gpl|hrl)|bb\s+battery)\b"):
        return "seo:batteries-ups", "stationary_battery_model"
    if has(text, r"\b(?:ac[- ]?dc|dc[- ]?dc)\b|\u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c"):
        return "seo:power-systems", "power_converter"
    if has(text, r"\u0434\u0435\u0440\u0436\u0430\u0442\u0435\u043b\u044c\s+\u0431\u0430\u0442\u0430\u0440\u0435\u0438|\u0442\u0435\u0440\u043c\u043e\u043a\u0430\u0440\u0442\u043e\u043d|\u0438\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440\s+\u0443\u0440\u043e\u0432\u043d\u044f\s+\u0437\u0430\u0440\u044f\u0434\u0430|\u0431\u0430\u043b\u0430\u043d\u0441\u0438\u0440"):
        return "seo:electronic-components", "battery_accessory"
    # The original 1C export is UTF-8, while some first-pass rules were
    # preserved from a legacy mojibake snapshot.  Keep this vocabulary narrow:
    # every term below names an electronic component or an assembly material,
    # rather than a general-purpose consumer product.
    if has(text,
           r"\u043c\u043e\u0434\u0443\u043b\u044c", r"\u043f\u043b\u0430\u0442\u0430", r"\u0442\u0440\u0430\u043d\u0441\u0444\u043e\u0440\u043c\u0430\u0442\u043e\u0440",
           r"\u0440\u0435\u0437\u043e\u043d\u0430\u0442\u043e\u0440", r"\u0442\u0435\u0440\u043c\u0438\u0441\u0442\u043e\u0440", r"\u0434\u0440\u043e\u0441\u0441\u0435\u043b\u044c",
           r"\u043f\u0440\u0438\u043f\u043e\u0439", r"\u0444\u043b\u044e\u0441", r"\u0448\u043b\u0435\u0439\u0444",
           r"\u0440\u0430\u0434\u0438\u043e\u043c\u043e\u0434\u0443\u043b\u044c", r"\u0442\u0440\u0430\u043d\u0437\u0438\u0441\u0442\u043e\u0440",
           r"\u043c\u0438\u043a\u0440\u043e\u0441\u0445\u0435\u043c", r"\u043a\u043e\u043d\u0434\u0435\u043d\u0441\u0430\u0442\u043e\u0440"):
        return "seo:electronic-components", "utf8_explicit_electronic_component"
    if has(text, r"\u043b\u0435\u043d\u0442\u0430\s+\u043d\u0438\u043a\u0435\u043b", r"\bccfl\b", r"\bnrf24l01\b"):
        return "seo:electronic-components", "utf8_battery_or_display_component"
    if has(text, r"\bbattery\b|\bli[- ]?(?:ion|pol)\b|\b(?:18650|21700|26700)\b"):
        return "seo:rechargeable-cells", "rechargeable_cell_model"
    # Current 1C titles often contain a readable manufacturer/model but omit
    # the generic Russian product class.  These families are model-specific
    # enough to classify without making an identity or compatibility claim.
    if has(text, r"\bfiamm\s+12fg", r"\bdelta\s+(?:hr|dtm|gel)\b", r"\bventura\s+(?:gpl|gt)\b"):
        return "seo:batteries-ups", "stationary_battery_brand_model"
    if has(text, r"\bpanasonic\b.*(?:eneloop|\d+\s*mah)", r"\bli[- ]?fe\b", r"\blfp\b"):
        return "seo:rechargeable-cells", "rechargeable_brand_or_chemistry"
    if has(text,
           r"\benergizer\b.*(?:\u0431\u0430\u0442\u0430\u0440|alkalin|alkaline|cr|lr|sr)",
           r"\bvarta\s+watch\b", r"\bpanasonic\b.*\b(?:cr|lr|sr)\d"):
        return "seo:primary-cells", "primary_brand_model"
    if has(text,
           r"\b(?:lcd|oled)\b", r"\u0434\u0438\u0441\u043f\u043b\u0435\u0439", r"\u0440\u0435\u043b\u0435\b",
           r"\u043f\u043e\u043b\u0451\u0442\u043d\u044b\u0439\s+\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u043b\u0435\u0440"):
        if has(text, r"\u043f\u043e\u043b\u0451\u0442\u043d\u044b\u0439\s+\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u043b\u0435\u0440"):
            return "seo:drone-components", "uav_flight_controller"
        return "seo:electronic-components", "display_or_relay_component"
    # Computer equipment is kept in a separate tree. It is not merged into
    # electronic components because its users compare different attributes
    # (interfaces, capacity, form factor and system configuration).
    if has(text,
           r"\u0441\u0438\u0441\u0442\u0435\u043c\u043d\u044b\u0439\s+\u0431\u043b\u043e\u043a", r"\u043f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u044b\u0439\s+\u043a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440",
           r"\b(?:thinkcentre|prodesk)\b"):
        return "seo:computer-systems", "computer_system"
    if has(text,
           r"\b(?:hdd|ssd|micro\s*sd|micro-sd)\b", r"\u0436\u0451\u0441\u0442\u043a\u0438\u0439\s+\u0434\u0438\u0441\u043a",
           r"\u0442\u0432\u0435\u0440\u0434\u043e\u0442\u0435\u043b\u044c\u043d\u044b\u0439\s+\u043d\u0430\u043a\u043e\u043f\u0438\u0442\u0435\u043b\u044c",
           r"\u0444\u043b\u0435\u0448[- ]?\u043a\u0430\u0440\u0442\u0430", r"\u043a\u0430\u0440\u0442\u0430\s+\u043f\u0430\u043c\u044f\u0442\u0438"):
        return "seo:data-storage", "computer_storage"
    if has(text,
           r"\u043a\u043e\u043c\u043c\u0443\u0442\u0430\u0442\u043e\u0440", r"\u0440\u043e\u0443\u0442\u0435\u0440", r"\bwi-?fi\b",
           r"\u0442\u0440\u0430\u043d\u0441\u0438\u0432\u0435\u0440"):
        return "seo:network-equipment", "computer_networking"
    if has(text, r"\b\u043c\u0444\u0443\b", r"\u043f\u0440\u0438\u043d\u0442\u0435\u0440"):
        return "seo:printing-equipment", "computer_printing"
    if has(text,
           r"\u0441\u0438\u0441\u0442\u0435\u043c\u043d\u044b\u0439\s+\u0431\u043b\u043e\u043a", r"\u043f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u044b\u0439\s+\u043a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440",
           r"\b(?:thinkcentre|prodesk)\b"):
        return "seo:computer-systems", "computer_system"
    if has(text,
           r"\u043a\u043b\u0430\u0432\u0438\u0430\u0442\u0443\u0440", r"\u043c\u044b\u0448\u044c", r"\u043c\u043e\u043d\u0438\u0442\u043e\u0440",
           r"\u043d\u0430\u0443\u0448\u043d\u0438\u043a", r"\u0433\u0430\u0440\u043d\u0438\u0442\u0443\u0440", r"\u043a\u043e\u043b\u043e\u043d\u043a\u0438?",
           r"\u043a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\s+\u043f\u0435\u0440\u0438\u0444\u0435\u0440\u0438\u0438"):
        return "seo:computer-peripherals", "computer_peripheral"
    if has(text,
           r"\u0440\u043e\u0437\u0435\u0442\u043a\u0430\s+\w+", r"\u0437\u0430\u0436\u0438\u043c\s+\u0432\u0438\u043d\u0442\u043e\u0432\u043e\u0439"):
        return "seo:electronic-components", "electrical_connector"
    if has(text, r"\u043c\u0430\u044f\u043a\s+\u0438\u043c\u043f\u0443\u043b\u044c\u0441\u043d\u044b\u0439", r"\bwr-r-a\b"):
        return None, "automotive_beacon_requires_scope_review"
    if has(text,
           r"\u0431\u043e\u043b\u0442", r"\u0433\u0430\u0439\u043a", r"\u0432\u0438\u043d\u0442", r"\u0448\u0430\u0439\u0431",
           r"\u0437\u0430\u043a\u043b\u0435\u043f\u043a\u0430", r"\u0445\u043e\u043c\u0443\u0442", r"\u043a\u0440\u0435\u043f[\u0435\u0451]\u0436",
           r"\u0448\u043f\u043b\u0438\u043d\u0442", r"\u0448\u043f\u0438\u043b\u044c\u043a\u0430", r"\u0443\u0433\u043e\u043b\u043e\u043a\s+\u0441\u0442\u0430\u043b\u044c\u043d",
           r"\u043f\u0435\u0442\u043b\u044f\s+(?:\u0441\u0442\u0430\u043b\u044c\u043d|\u043d\u0430\u043a\u043b\u0430\u0434\u043d)", r"\u0437\u0430\u0433\u043b\u0443\u0448\u043a\u0430\s+\u043f\u043e\u0434\s+\u043e\u0442\u0432\u0435\u0440\u0441\u0442\u0438\u0435"):
        return "seo:fasteners", "industrial_fastener"
    if has(text,
           r"\u0441\u0432\u0435\u0440\u043b\u043e", r"\u043e\u0442\u0432\u0451\u0440\u0442\u043a", r"\u043a\u043b\u044e\u0447\s+\u0440\u0430\u0437\u0432\u043e\u0434", r"\u043f\u0430\u044f\u043b\u044c\u043d",
           r"\u0431\u043e\u043a\u043e\u0440\u0435\u0437", r"\u0432\u043e\u0440\u043e\u0442\u043e\u043a",
           r"\u0442\u043e\u043d\u043a\u043e\u0433\u0443\u0431\u0446", r"\u0441\u044a[\u0435\u0451]\u043c\u043d\u0438\u043a\s+\u043f\u043e\u0434\u0448\u0438\u043f\u043d\u0438\u043a",
           r"\u043d\u0430\u0431\u043e\u0440\s+\u043a\u043b\u044e\u0447\u0435\u0439", r"\u0442\u0440\u0435\u0449\u043e\u0442\u043a",
           r"\u043f\u043b\u043e\u0441\u043a\u043e\u0433\u0443\u0431", r"\u043f\u0430\u0441\u0441\u0430\u0442\u0438\u0436",
           r"\u043a\u043b\u044e\u0447\s+\u0434[\u0438\u0430]\u043d[\u0430\u0438]\u043c\u043e\u043c\u0435\u0442\u0440\u0438\u0447\u0435\u0441\u043a\w*",
           r"\u043d\u0430\u043f\u0438\u043b\u044c\u043d\u0438\u043a",
           r"\u0433\u0438\u0434\u0440\u0430\u0432\u043b\u0438\u0447\u0435\u0441\u043a\w*\s+(?:\u043f\u0440\u0435\u0441\u0441|\u0446\u0438\u043b\u0438\u043d\u0434\u0440)", r"\u0443\u0434\u043b\u0438\u043d\u0438\u0442\u0435\u043b\u044c\s+1/4",
           r"\u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\s+\u0434\u043b\u044f\s+\u0441\u043d\u044f\u0442\u0438\u044f\s+\u0438\u0437\u043e\u043b\u044f\u0446\u0438\u0438",
           r"\u0437\u0430\u043a\u043b\u0435\u043f\u043e\u0447\u043d\u0438\u043a", r"\u043f\u0438\u0441\u0442\u043e\u043b\u0435\u0442\s+(?:\u0434\u043b\u044f\s+\u0433\u0435\u0440\u043c\u0435\u0442\u0438\u043a\u0430|\u043a\u043b\u0435\u0435\u0432\u043e\u0439)",
           r"\u0441\u0432\u0430\u0440\u043e\u0447\u043d\u044b\u0439\s+\u0430\u043f\u043f\u0430\u0440\u0430\u0442",
           r"\u0448\u043f\u0440\u0438\u0446\s+\u0434\u043b\u044f\s+(?:\u0441\u043c\u0430\u0437\u043a\u0438|\u043c\u0430\u0441\u043b\u0430)", r"\u0449\u0435\u0442\u043a\u0430\s+\u043f\u043e\s+\u043c\u0435\u0442\u0430\u043b\u043b\u0443",
           r"\u043d\u0430\u0431\u043e\u0440\s+(?:\u0433\u043e\u043b\u043e\u0432\u043e\u043a|\u043d\u0430\u0434\u0444\u0438\u043b\u0435\u0439|\u043c\u0435\u0442\u0447\u0438\u043a\u043e\u0432\s+\u0438\s+\u043f\u043b\u0430\u0448\u0435\u043a|\u0430\u0434\u0430\u043f\u0442\u0435\u0440\u043e\u0432|\u0431\u0438\u0442)",
           r"\u043a\u0438\u044f\u043d\u043a\u0430", r"\u043d\u043e\u0436\s+\u043c\u043e\u043d\u0442\u0430\u0436\u043d\u0438\u043a\u0430", r"\u043b\u0435\u0437\u0432\u0438(?:\u0435|\u044f)",
           r"\u043f\u043d\u0435\u0432\u043c\u043e\u043f\u0438\u0441\u0442\u043e\u043b\u0435\u0442\s+\u043f\u0440\u043e\u0434\u0443\u0432\u043e\u0447\u043d\u044b\u0439", r"\u043d\u0430\u0441\u0430\u0434\u043a\u0430\s+\u0434\u043b\u044f\s+\u0433\u0440\u0430\u0432\u0435\u0440\u0430", r"\u043a\u0438\u0441\u0442\u044c\s+\u043f\u043b\u043e\u0441\u043a\u0430\u044f"):
        return "seo:workshop-tools", "workshop_tool"
    if has(text,
           r"\u0441\u0432\u0430\u0440\u043e\u0447\u043d\u0430\u044f\s+\u043b\u0435\u043d\u0442\u0430", r"\u0438\u0437\u043e\u043b\u0435\u043d\u0442", r"\u043a\u043e\u043c\u043f\u0430\u0443\u043d\u0434",
           r"\u0433\u0435\u0440\u043c\u0435\u0442\u0438\u043a", r"\u043a\u043b\u0435\u0439", r"\u043c\u0430\u043b\u044f\u0440\u043d\u0430\u044f\s+\u043b\u0435\u043d\u0442\u0430",
           r"\u0448\u043b\u0438\u0444\u043b\u0438\u0441\u0442", r"\u0441\u043c\u0430\u0437\u043a\u0430",
           # "Клеевые стержни" do not contain the exact noun "клей" but
           # are an unambiguous consumable for assembly.  Keep the two-word
           # phrase narrow so a generic adjective cannot create a category.
           r"\u043a\u043b\u0435\u0435\u0432\w*\s+\u0441\u0442\u0435\u0440\u0436\u043d\w*",
           r"\u043e\u043f\u043b\u0435\u0442\u043a\u0430\s+\u0434\u043b\u044f\s+\u0432\u044b\u043f\u0430\u0439\u043a\u0438", r"\u0442\u0440\u0443\u0431\u043a\u0430\s+\u0442\u0435\u0440\u043c\u043e\u0443\u0441\u0430\u0436\u0438\u0432\u0430\u0435\u043c\u0430\u044f",
           r"\u043b\u0438\u0441\u0442\s+\u0441\u0442\u0435\u043a\u043b\u043e\u0442\u0435\u043a\u0441\u0442\u043e\u043b\u0438\u0442", r"\u0442\u0435\u043a\u0441\u0442\u043e\u043b\u0438\u0442\b", r"\u043a\u0430\u043d\u0438\u0444\u043e\u043b\u044c\b",
           r"\u043b\u0430\u043a\s+\u0430\u043a\u0440\u0438\u043b\u043e\u0432\u044b\u0439\s+\u0438\u0437\u043e\u043b\u044f\u0446\u0438\u043e\u043d\u043d\u044b\u0439\s+\u0434\u043b\u044f\s+\u043f\u0435\u0447\u0430\u0442\u043d\u044b\u0445\s+\u043f\u043b\u0430\u0442",
           r"\u0442\u0435\u0440\u043c\u043e\u0438\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440\u043d\u0430\u044f\s+(?:\u0436\u0438\u0434\u043a\u043e\u0441\u0442\u044c|\u0444\u0440\u0441\s+\u043a\u043e\u043c\u043f\u043e\u0437\u0438\u0446\u0438\u044f)", r"\u0444\u043e\u043b\u044c\u0433\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439\s+\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b"):
        return "seo:assembly-materials", "assembly_material"
    if has(text, r"\bsrt192bp2\b"):
        return "seo:batteries-ups", "ups_external_battery_model"
    if has(text,
           r"\b(?:4pzs\d+|pzs\d+)\b", r"\u0430\u043a\u0431\s+80v"):
        return "seo:batteries-traction", "traction_or_external_battery_model"
    if has(text,
           r"\b(?:3b1065|br603449d|tlh-2450|1756-ba2|mr-bat6v1|2cr17335|cr-2032|en95)\b",
           r"\u043b\u0438\u0442\u0438\u0435\u0432\u0430\u044f\s+\u0431\u0430\u0442\u0430\u0440\u0435\u044f", r"\u044d\u043b\u0435\u043c\u0435\u043d\u0435\u0442\s+\u043f\u0438\u0442\u0430\u043d\u0438\u044f"):
        return "seo:primary-cells", "primary_cell_current_model"
    if has(text,
           r"\b(?:clp-489670|lb-02b)\b", r"\b(?:l\u0440|lp)383454", r"\u0431\u0430\u0442\u0430\u0440\u0435\u044f\s+\u0430\u043a\u043a\u0443\u043c\u043c"):
        return "seo:rechargeable-cells", "rechargeable_pack_current_model"
    if has(text,
           r"\u043a\u043e\u043d\u043d\u0435\u043a\u0442\u043e\u0440", r"\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u043d\u0430\u044f\s+\u0433\u0440\u0443\u043f\u043f\u0430",
           r"\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u043e\u0440", r"\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u043d\u044b\u0435\s+\u044d\u043b\u0435\u043c\u0435\u043d\u0442\u044b"):
        return "seo:electronic-components", "current_connector_or_contactor"
    # Small, high-confidence classes seen in the current 1C residual queue.
    # Each signal describes the product type itself, not an inferred
    # compatibility, so it is safe to use before source enrichment.
    if has(text, r"\u043f\u043e\u043b\u0438\u0438\u043c\u0438\u0434\u043d\u0430\u044f\s+\u043b\u0435\u043d\u0442\u0430"):
        return "seo:assembly-materials", "polyimide_assembly_tape"
    if has(text,
           r"\b(?:micro\s*sd|sdhc|sdxc)\b",
           r"\u043a\u0430\u0440\u0442\u0430\s+(?:\u043f\u0430\u043c\u044f\u0442\u0438|\u0444\u043b\u044d\u0448)"):
        return "seo:data-storage", "memory_card"
    if has(text, r"\u0441\u0435\u0442\u0435\u0432\u043e\u0439\s+\u0444\u0438\u043b\u044c\u0442\u0440", r"\u0444\u0438\u043b\u044c\u0442\u0440\s+\u0441\u0435\u0442\u0435\u0432\u043e\u0439"):
        return "seo:power-accessories", "mains_filter"
    if has(text,
           r"\u0441\u044a\u0451\u043c\u043d\u0438\u043a\s+\u0438\u0437\u043e\u043b\u044f\u0446\u0438\u0438",
           r"\u043a\u043b\u0435\u0449\u0438\s+\u0434\u043b\u044f\s+\u0441\u043d\u044f\u0442\u0438\u044f\s+\u0438\u0437\u043e\u043b\u044f\u0446\u0438\u0438"):
        return "seo:workshop-tools", "wire_stripping_tool"
    if has(text, r"\u0434\u0438\u043e[\u0434\u0442]", r"\b(?:semikron|skm\d|skd\d)"):
        return "seo:electronic-components", "semiconductor_component"
    if has(text, r"\u044d\u043b\u0435\u043c\u0435\u043d\u0442\s+\u043d\u043e\u0440\u043c\u0430\u043b\u044c\u043d"):
        return "seo:measurement-equipment", "reference_measurement_cell"
    if has(text, r"\b(?:fr0?3|fr6)\b"):
        return "seo:primary-cells", "primary_cell_fr_model"
    if has(text,
           r"\u0441\u0435\u0442\u0435\u0432\u043e\u0435\s+(?:\u0430\u0434\u0430\u043f\u0442\u0435\u0440|\u0437/?\u0443)",
           r"\u0430\u0434\u0430\u043f\u0442\u0435\u0440\s+\S+\s+\d+\s*[v\u0432]",
           r"\b(?:ac[- ]?dc|dc[- ]?dc)\b"):
        return "seo:power-systems", "power_adapter_or_converter"
    if has(text, r"\u0441\u0435\u0442\u0435\u0432\u043e\u0435\s+\u0437/?\u0443", r"\u0437\u0430\u0440\u044f\u0434\u043d\u043e\u0435\s+\u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e"):
        return "seo:chargers", "mains_charger"
    if has(text,
           r"\u043c\u0435\u0434\u043d\u044b\u0435\s+\u043f\u043b\u0430\u0441\u0442\u0438\u043d\u044b",
           r"\u0438\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440\s+\u0437\u0430\u0440\u044f\u0434\u0430",
           r"\u0440\u0435\u043e\u0441\u0442\u0430\u0442",
           r"\u043a\u043e\u043d\u0434\u0435\u043d[\u0441\u0441]\u0442\u0430\u0442\u043e\u0440",
           r"\bghr-\d+[a-z-]*\b"):
        return "seo:electronic-components", "explicit_current_component"
    if has(text,
           r"\u0432\u0430\u043a\u0443\u0443\u043c\u043d\u044b\u0439\s+\u043e\u0442\u0441\u043e\u0441",
           r"\u043f\u043b\u0430\u0441\u0442\u0438\u043d\u0430\s+\u043f\u043e\u0434\u043e\u0433\u0440\u0435\u0432\u0430"):
        return "seo:workshop-tools", "soldering_workshop_tool"
    if has(text,
           r"\b(?:radiomaster|betafpv|iflight|dji)\b",
           r"\u043f\u0443\u043b\u044c\u0442\s+\u0443\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u044f.*(?:2\.4\s*ghz|900\s*mhz)"):
        return "seo:drone-components", "uav_radio_component"
    if has(text,
           r"\b(?:jazzway|era)\b.*(?:pled|spl-)",
           r"\u043e\u0444\u0438\u0441\u043d\u044b\u0435\s+\u0441\u0432",
           r"\u0441\u0432\u0435\u0442\u043e\u0434\u0438\u043e\u0434\u043d\u0430\u044f\s+\u043f\u0430\u043d\u0435\u043b\u044c"):
        return "seo:lighting-fixtures", "led_lighting_fixture"
    if has(text, r"\b(?:er\s*2450|er2450)\b", r"\u044d\u043b\u0435\u043c\u0435\u043d\u0442\s+\u043f\u0438\u0442[\u0430\u0438]\u043d"):
        return "seo:primary-cells", "primary_lithium_cell"
    return None, "unclassified"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unclassified", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--exclude", type=Path, action="append", help="CSV with external_id/product_external_id column excluded before staging; repeatable")
    parser.add_argument("--exclude-category", action="append", default=[], help="Category external ID to keep in the review queue; repeatable")
    parser.add_argument("--existing-assignments", type=Path, help="CSV of already-applied product/category pairs; existing category wins")
    args = parser.parse_args()

    assignments: list[dict[str, str]] = []
    unknown: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    seen: set[str] = set()
    excluded: set[str] = set()
    excluded_categories = set(args.exclude_category)
    existing: dict[str, str] = {}
    for exclude_file in args.exclude or []:
        with exclude_file.open(encoding="utf-8-sig", newline="") as handle:
            # Scope and duplicate exclusion manifests use the explicit
            # product_external_id header. Accept the older external_id form
            # too, but never silently treat a non-empty manifest as empty.
            excluded |= {
                (clean.get("product_external_id") or clean.get("external_id") or "").strip()
                for clean in csv.DictReader(handle)
                if (clean.get("product_external_id") or clean.get("external_id") or "").strip()
            }
    if args.existing_assignments:
        with args.existing_assignments.open(encoding="utf-8-sig", newline="") as handle:
            existing = {
                row["product_external_id"].strip(): row["category_external_id"].strip()
                for row in csv.DictReader(handle)
                if row.get("product_external_id", "").strip() and row.get("category_external_id", "").strip()
            }
    preserved_existing = 0
    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle, delimiter=";"), start=2):
            if norm(row.get("ЭтоГруппа", "")) not in {"ложь", "false", "0", "no", "n"}:
                continue
            external_id = row.get("Код", "").strip()
            name = row.get("Наименование", "").strip()
            if not external_id or not name or external_id in seen or external_id in excluded:
                continue
            seen.add(external_id)
            category_id, rule = category(name, row.get("ПолныйПуть", ""))
            base = {"row_number": str(row_number), "product_external_id": external_id, "name": name, "rule": rule}
            if external_id in existing:
                category_id = existing[external_id]
                rule = "preserved_existing_assignment"
                preserved_existing += 1
            if category_id in excluded_categories:
                base["rule"] = f"{rule}_deferred_by_category_policy"
                category_id = None
            if category_id is None:
                unknown.append(base)
                continue
            assignments.append({"product_external_id": external_id, "category_external_id": category_id})
            counts[category_id] += 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "category_external_id"])
        writer.writeheader()
        writer.writerows(assignments)
    with args.unclassified.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["row_number", "product_external_id", "name", "rule"])
        writer.writeheader()
        writer.writerows(unknown)
    summary = {
        "source_product_rows": len(assignments) + len(unknown),
        "excluded_before_classification": len(excluded),
        "preserved_existing_assignments": preserved_existing,
        "assigned_high_signal": len(assignments),
        "unclassified_not_forced": len(unknown),
        "distribution": dict(sorted(counts.items())),
        "invariant": "Every assignment has one target leaf; unclassified rows are intentionally not assigned.",
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
