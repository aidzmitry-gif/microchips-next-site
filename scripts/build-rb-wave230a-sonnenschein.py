import csv,json,hashlib,re,unicodedata
from pathlib import Path
from pypdf import PdfReader
R=Path(__file__).resolve().parents[1];D=R/'docs/audits/generated';I=R/'docs/imports';T=D/'rb-wave230-description-targets.csv';REG=R/'docs/audits/sources/wave211c-stationary/source-registry.json';M=I/'rb-source-backed-description-stage-manifest-wave230a-2026-07-29.json';L=D/'rb-wave230a-sonnenschein-ledger.csv';S=D/'rb-wave230a-sonnenschein.summary.json';REP=R/'docs/audits/2026-07-29-rb-wave230a-sonnenschein.md'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(v):return re.sub(r'[^A-Z0-9]','',unicodedata.normalize('NFKC',v or '').upper())
def k(m):return 'exide-sonnenschein-a400.pdf' if m.startswith('A4') else 'exide-sonnenschein-a500.pdf' if m.startswith('A5') else 'exide-sonnenschein-a700.pdf' if m.startswith('A7') else 'exide-sonnenschein-solar-block.pdf' if m.startswith(('S ','SB ')) else 'exide-sonnenschein-a600.pdf'
IDENTITY_CORRECTION_HOLDS={'bitrix:3117'}
def main():
 with T.open(encoding='utf-8-sig',newline='') as h:t=[x for x in csv.DictReader(h) if x['manufacturer']=='Sonnenschein']
 if len(t)!=35 or len({x['product_external_id'] for x in t})!=35:raise SystemExit('frozen scope drift')
 reg={x['source_id']:x for x in json.loads(REG.read_text(encoding='utf-8-sig'))['sources']};txt={};pins={}
 for q in set(k(x['mpn']) for x in t):
  s=reg[q];p=R/s['snapshot_path'];
  if not p.is_file() or sha(p)!=s['snapshot_sha256'] or 'exidegroup.com' not in s['source_url']:raise SystemExit('pin drift')
  txt[q]=norm('\n'.join(z.extract_text() or '' for z in PdfReader(p).pages));pins[q]=s
 ledger=[];products=[]
 for x in t:
  m=x['mpn'];s=pins[k(m)]; exact=norm(m) in txt[k(m)] and x['product_external_id'] not in IDENTITY_CORRECTION_HOLDS
  part='stageable_model_core' if exact else ('hold_identity_correction_required' if x['product_external_id'] in IDENTITY_CORRECTION_HOLDS else 'hold_exact_model_absent_from_pinned_source')
  ledger.append({'external_id':x['product_external_id'],'mpn':m,'partition':part,'source_url':s['source_url'] if exact else '','snapshot_sha256':s['snapshot_sha256'] if exact else ''})
  if exact:products.append({'external_id':x['product_external_id'],'identity_scope':'model_core','manufacturer':'Sonnenschein','model_core':m,'technology':'GEL','source_url':s['source_url'],'technical_attributes':{'Модель':m},'source_kind':'official_manufacturer_catalogue','source_tier':'manufacturer_primary','source_publisher':s['publisher'],'manufacturer_primary':True,'evidence_scope':'model_core','checked_at':'2026-07-29'})
 with L.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
 M.write_text(json.dumps({'schema_version':1,'locale':'ru-BY','purpose':'Wave230-A frozen Sonnenschein source-backed drafts; bounded model-core only.','products':products},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 s={'target_rows':35,'stageable_model_core':len(products),'exact_scope_rows':0,'holds':35-len(products),'pins':{q:v['snapshot_sha256'] for q,v in pins.items()},'database_apply':False};S.write_text(json.dumps(s,indent=2)+'\n');REP.write_text('# Wave230-A Sonnenschein\n\nAll 35 frozen Sonnenschein rows were checked only against existing SHA-pinned official Exide PDFs. Exact scope is not used because current catalogue names do not end with the MPN after strict technical-summary stripping; source-backed rows use bounded model-core only. No DB apply.\n');print(s)
if __name__=='__main__':main()
