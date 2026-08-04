import csv
import importlib.util
import json
import shutil
import sys
import uuid
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "classify-rb-current-uncategorized.py"
SPEC = importlib.util.spec_from_file_location("rb_current_uncategorized", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_classifies_only_high_signal_and_defers_electronics():
    work = SCRIPT.parent.parent / "docs" / "audits" / "generated" / f"test-rb-tree-{uuid.uuid4().hex}"
    work.mkdir(parents=True)
    source = work / "source.csv"
    rows = [
        {"product_external_id": "A", "name": "Зарядное устройство Robiton Test100"},
        {"product_external_id": "B", "name": "Резистор 10 кОм"},
        {"product_external_id": "C", "name": "Неизвестное изделие"},
        {"product_external_id": "D", "name": "Адаптер-переходник USB Type-C — RJ45"},
    ]
    try:
        with source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        summary = MODULE.classify(source, work, "result", {"seo:electronic-components"})
        assert summary["source_rows"] == 4
        assert summary["assigned_high_signal"] == 1
        assert summary["deferred_by_market_scope"] == 1
        assert summary["unclassified_hold"] == 2
        payload = json.loads((work / "result-summary.json").read_text(encoding="utf-8"))
        assert payload["automatic_database_mutations"] == 0
        assigned = list(csv.DictReader((work / "result-assignments.csv").open(encoding="utf-8-sig")))
        assert assigned[0]["category_external_id"] == "seo:chargers"
    finally:
        shutil.rmtree(work)
