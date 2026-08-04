import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "merge-rb-wave230-description-manifests.py"
SPEC = importlib.util.spec_from_file_location("wave230_merge", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def payload(rows):
    return {"locale": "ru-BY", "products": rows}


def row(external_id):
    return {"external_id": external_id, "identity_scope": "model_core"}


def test_merges_exact_frozen_denominator():
    products = MODULE.merge_payloads(
        [("a", payload([row("bitrix:1")])), ("b", payload([row("bitrix:2")]))],
        {"bitrix:1", "bitrix:2"},
    )
    assert [item["external_id"] for item in products] == ["bitrix:1", "bitrix:2"]


def test_rejects_missing_or_out_of_scope_product():
    for rows in ([row("bitrix:1")], [row("bitrix:1"), row("bitrix:3")]):
        try:
            MODULE.merge_payloads([("a", payload(rows))], {"bitrix:1", "bitrix:2"})
        except ValueError:
            pass
        else:
            raise AssertionError("scope drift must be rejected")


def test_accepts_explicit_hold_for_frozen_product():
    products = MODULE.merge_payloads(
        [("a", payload([row("bitrix:1")]))],
        {"bitrix:1", "bitrix:2"},
        {"bitrix:2"},
    )
    assert len(products) == 1
