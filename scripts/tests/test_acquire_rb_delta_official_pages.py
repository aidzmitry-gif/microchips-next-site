from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "acquire-rb-delta-official-pages.py"
SPEC = importlib.util.spec_from_file_location("delta_acquire", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_model_key_preserves_decimal_identity_but_ignores_spacing() -> None:
    assert MODULE.model_key("HR 12-4.5") != MODULE.model_key("HR 12-45")
    assert MODULE.model_key("FTS 12-100X") == MODULE.model_key("FTS 12-100 X")


def test_page_model_requires_one_unique_h1_and_removes_brand() -> None:
    raw = b"<html><h1>DELTA DTM 1217</h1><h1>DELTA DTM 1217</h1></html>"
    assert MODULE.page_model(raw) == "DTM 1217"
