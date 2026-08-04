import importlib.util
import shutil
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("wave200",ROOT/"scripts"/"build-rb-panasonic-wave200-preparation.py"); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def temp():
    root=ROOT/"docs"/"audits"/"generated"/f"test-panasonic-wave200-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root

def test_build_preserves_pack_variant_and_is_fail_closed():
    root=temp()
    try:
        source=root/"facet.csv"
        source.write_text("bitrix_id,name\n1,Батарейка Panasonic CR2032 1BP\n2,Батарейка Panasonic BR2032/F2N\n",encoding="utf-8-sig")
        result=m.build(source,root,2)
        assert result["candidate_records"]==2
        rows=(root/"rb-panasonic-wave200-candidates.csv").read_text(encoding="utf-8-sig")
        assert "CR2032 1BP" in rows and "false" in rows
    finally:
        shutil.rmtree(root)

def test_build_rejects_unexpected_count():
    root=temp()
    try:
        source=root/"facet.csv"; source.write_text("bitrix_id,name\n1,Panasonic CR2032\n",encoding="utf-8-sig")
        try: m.build(source,root,2)
        except ValueError as e: assert "expected 2" in str(e)
        else: assert False
    finally:
        shutil.rmtree(root)
