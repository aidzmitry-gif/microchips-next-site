from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "build-one-c-seo-category-assignment.py"
SPEC = importlib.util.spec_from_file_location("one_c_classifier", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PowerTaxonomyRulesTest(unittest.TestCase):
    def assert_category(self, name: str, expected: str | None) -> None:
        self.assertEqual(expected, MODULE.category(name, "")[0])

    def test_separates_ups_devices_from_ups_batteries(self) -> None:
        self.assert_category("Источник бесперебойного питания Eaton 9E1000i", "seo:ups-systems")
        self.assert_category("ИБП Hiden Control HS20-3024P", "seo:ups-systems")
        self.assert_category("Аккумуляторная батарея для ИБП 12 В 9 Ач", "seo:batteries-ups")
        self.assert_category("Батарейный модуль UPS SRT192BP2", "seo:batteries-ups")

    def test_separates_power_supplies_converters_and_false_positive_nouns(self) -> None:
        self.assert_category("Блок питания IRM-30-24", "seo:power-supplies")
        self.assert_category("Преобразователь напряжения DC/DC 24/12 В", "seo:power-converters")
        self.assert_category("Инвертор 24 В 1000 Вт", "seo:power-converters")
        self.assert_category("Преобразователь частоты Schneider ATV320", "seo:electrical-protection-control")
        self.assert_category("Преобразователь ржавчины Elcon P", "seo:assembly-materials")

    def test_charger_wins_over_generic_mains_adapter_and_ambiguous_item_waits(self) -> None:
        self.assert_category("Сетевое З/У Robiton", "seo:chargers")
        self.assert_category("Эл. питания литиевый OMRON CJ1W-BAT01 3V", "seo:primary-cells")
        self.assert_category("Источник питания M4T28-BR12SH1", None)


if __name__ == "__main__":
    unittest.main()
