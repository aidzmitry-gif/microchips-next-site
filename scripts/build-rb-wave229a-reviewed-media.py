import csv,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'docs/audits/generated';I=R/'docs/imports';IDX=R/'.tmp/wave229-hold-001/index.json';OCR=D/'wave227-ocr-batches/wave227-ocr-input-001.csv';CAND=D/'rb-wave227-legacy-preview-candidates.csv';L=D/'rb-wave229a-reviewed-media.csv';M=I/'rb-reviewed-legacy-preview-media-wave229a-2026-07-29.json';S=D/'rb-wave229a-reviewed-media.summary.json'
PASS={'bitrix:10747','bitrix:1164','bitrix:1397','bitrix:1403','bitrix:1413','bitrix:1414','bitrix:1415','bitrix:1416','bitrix:1420','bitrix:1433','bitrix:1434','bitrix:1438','bitrix:1472','bitrix:1491','bitrix:1492','bitrix:1495','bitrix:1514','bitrix:1518','bitrix:1527','bitrix:1536','bitrix:1544','bitrix:1545','bitrix:1547','bitrix:1549','bitrix:1558','bitrix:1559','bitrix:1562','bitrix:1575','bitrix:1582','bitrix:1592','bitrix:1606','bitrix:1612','bitrix:1616','bitrix:1625','bitrix:1631','bitrix:1640','bitrix:1717','bitrix:1723','bitrix:1737','bitrix:1789','bitrix:1791','bitrix:20122','bitrix:20124','bitrix:20125','bitrix:20126','bitrix:20133','bitrix:20134','bitrix:20136'}
def main():
 idx=json.loads(IDX.read_text(encoding='utf-8'));o={x['external_id']:x for x in csv.DictReader(OCR.open(encoding='utf-8-sig',newline=''))};c={x['external_id']:x for x in csv.DictReader(CAND.open(encoding='utf-8-sig',newline=''))};rows=[x for sh in idx['sheets'] for x in sh['rows']]
 if len(rows)!=68 or set(x['external_id'] for x in rows)-set(o):raise SystemExit('scope drift')
 out=[];images=[]
 for x in rows:
  q=o[x['external_id']];e=c[x['external_id']];v='PASS' if x['external_id'] in PASS else 'HOLD';reason='exact_expected_mpn_visibly_legible_on_product_or_label' if v=='PASS' else 'exact_expected_mpn_not_visibly_legible'
  if str(e['media_id'])!=str(x['media_id']) or e['content_sha256']!=q['hash']:raise SystemExit('candidate evidence drift')
  out.append({'external_id':x['external_id'],'media_id':x['media_id'],'expected_mpn':x['expected_exact'],'image_path':x['image_path'],'hash':q['hash'],'verdict':v,'reason':reason})
  if v=='PASS':images.append({'external_id':x['external_id'],'media_id':int(x['media_id']),'content_sha256':q['hash'],'storage_path':e['storage_path'],'rights_basis':e['rights_basis'],'identity_scope':'exact','mpn':x['expected_exact'],'identity_evidence_level':'visible_exact_mpn','visual_verification_note':reason,'reviewed_at':'2026-07-29'})
 with L.open('w',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 M.write_text(json.dumps({'schema_version':1,'locale':'ru-BY','purpose':'Wave229-A manually reviewed company-owned legacy media; PASS requires visibly legible exact MPN.','images':images},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 s={'rows':68,'pass':len(images),'hold':68-len(images),'visible_mismatches':0,'database_apply':False};S.write_text(json.dumps(s,indent=2)+'\n');print(s)
if __name__=='__main__':main()
