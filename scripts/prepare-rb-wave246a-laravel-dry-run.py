#!/usr/bin/env python3
"""Prepare temporary, no-repeat validation subsets for Wave246A Laravel dry-runs."""
import csv, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/".tmp/wave246a-laravel"
scope=[r for r in csv.DictReader((ROOT/"docs/audits/generated/rb-wave246-b2b-scope.csv").open(encoding="utf-8-sig")) if r["partition"]=="enersys"]
ids={r["product_external_id"] for r in scope}; bitrix={x for x in ids if x.startswith("bitrix:")}
def read(path): return json.loads((ROOT/path).read_text(encoding="utf-8-sig"))
identity=read("docs/imports/rb-verified-oem-identities-wave209a-2026-07-29.json")
identity["products"]=[r for r in identity["products"] if r["external_id"] in bitrix]
desc=[]
for path in ["docs/imports/rb-source-backed-descriptions-wave241-2026-07-29.json","docs/imports/rb-source-backed-description-drafts-enersys-wave179-2026-07-29.json","docs/imports/rb-source-backed-description-drafts-enersys-wave183-2026-07-29.json","docs/imports/rb-source-backed-description-drafts-enersys-rh-wave193-2026-07-29.json"]:
 desc.extend(r for r in read(path)["products"] if r["external_id"] in ids)
if len(identity["products"])!=15 or len(desc)!=92 or len({r["external_id"] for r in desc})!=92: raise SystemExit("temporary Laravel subset cardinality drift")
preview=[]
for path in ["docs/imports/rb-source-verified-preview-enersys-wave179-2026-07-29.json","docs/imports/rb-source-verified-preview-enersys-wave183-2026-07-29.json","docs/imports/rb-source-verified-preview-enersys-rh-wave193-2026-07-29.json"]:
 preview.extend(r for r in read(path)["products"] if r["external_id"] in ids)
if len(preview)!=77 or len({r["external_id"] for r in preview})!=77: raise SystemExit("temporary preview subset cardinality drift")
OUT.mkdir(parents=True,exist_ok=True)
(OUT/"identity-15.json").write_text(json.dumps(identity,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"descriptions-92.json").write_text(json.dumps({"schema_version":1,"locale":"ru-BY","products":desc},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
(OUT/"preview-77.json").write_text(json.dumps({"locale":"ru-BY","products":preview},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"identity_rows":15,"description_rows":92,"preview_rows":77,"persistent_import_manifests_created":0}))
