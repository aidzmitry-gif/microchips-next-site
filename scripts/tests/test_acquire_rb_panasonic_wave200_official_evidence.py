import hashlib, importlib.util, shutil, uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("acq",ROOT/"scripts"/"acquire-rb-panasonic-wave200-official-evidence.py"); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def temp():
    root=ROOT/"docs"/"audits"/"generated"/f"test-panasonic-wave200-acq-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    return root

def candidate(path):
    path.write_text("product_external_id,model_token,pack_variant_key\nbitrix:1,CR2032,Panasonic CR2032 1BP\n",encoding="utf-8-sig")

def test_accepts_exact_saved_panasonic_evidence():
    root=temp()
    try:
        c=root/"c.csv"; candidate(c); snap=root/"source.pdf"; snap.write_bytes(b"pdf")
        e=root/"e.csv"; e.write_text("product_external_id,model_token,pack_variant_key,source_url,source_kind,snapshot_path,snapshot_sha256\nbitrix:1,CR2032,Panasonic CR2032 1BP,https://industrial.panasonic.com/x.pdf,exact_datasheet,"+str(snap)+","+hashlib.sha256(b"pdf").hexdigest()+"\n",encoding="utf-8-sig")
        assert m.build(c,e,root)["accepted_exact_first_party_records"]==1
    finally:
        shutil.rmtree(root)

def test_rejects_cross_pack_evidence():
    root=temp()
    try:
        c=root/"c.csv"; candidate(c); snap=root/"source.pdf"; snap.write_bytes(b"pdf")
        e=root/"e.csv"; e.write_text("product_external_id,model_token,pack_variant_key,source_url,source_kind,snapshot_path,snapshot_sha256\nbitrix:1,CR2032,Panasonic CR2032 2BP,https://industrial.panasonic.com/x.pdf,exact_datasheet,"+str(snap)+","+hashlib.sha256(b"pdf").hexdigest()+"\n",encoding="utf-8-sig")
        try: m.build(c,e,root)
        except ValueError as x: assert "cross-variant" in str(x)
        else: assert False
    finally:
        shutil.rmtree(root)
