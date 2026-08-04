import csv,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('wave225d',ROOT/'scripts/build-rb-wave225d-ocr-input.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def test_wave225d_accepts_only_single_existing_hash_matched_asset_and_holds_failures():
 with (ROOT/'docs/audits/generated/rb-wave225a-preview-image-review-queue.csv').open(encoding='utf-8-sig',newline='') as h:
  valid=next(x for x in csv.DictReader(h) if x['partition']=='displayable_preview_requires_human_review')
 assets=ROOT/'.tmp/wave225-assets'; accepted,held=mod.validate_row(valid,assets)
 assert accepted is not None and held is None and Path(accepted['image_path']).is_file()
 missing={**valid,'media_ids':'definitely-missing','storage_paths':'legacy/missing.png'};accepted,held=mod.validate_row(missing,assets)
 assert accepted is None and held['hold_reason']=='local_asset_missing'
 ambiguous={**valid,'media_ids':valid['media_ids']+';other'};accepted,held=mod.validate_row(ambiguous,assets)
 assert accepted is None and held['hold_reason']=='multiple_or_delimited_media_metadata'
def test_wave225d_real_output_never_contains_ocr_verdict_or_auto_pass():
 s=json.loads((ROOT/'docs/audits/generated/rb-wave225-ocr-input.summary.json').read_text(encoding='utf-8'))
 with (ROOT/'docs/audits/generated/rb-wave225-ocr-input.csv').open(encoding='utf-8-sig',newline='') as h:fields=next(csv.reader(h))
 assert fields==mod.OCR_FIELDS and s['policy']['ocr_verdicts_created']==0 and s['policy']['auto_pass'] is False
