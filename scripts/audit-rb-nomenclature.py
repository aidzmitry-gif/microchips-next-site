# -*- coding: utf-8 -*-
"""Read-only nomenclature audit for the RB focus slice.

Cross-checks what each product NAME states against what its Bitrix PROPERTIES
store, plus structural checks (identity collisions, duplicate names, mixed
script, missing specs). Produces an actionable findings CSV + summary the
owner can use to fix 1C and the legacy site. No source is modified.
"""
import csv
import importlib.util
import json
import os
import re
import sys
from collections import defaultdict, Counter

csv.field_size_limit(10_000_000)

GEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'docs', 'audits', 'generated')
MANIFEST = os.path.join(GEN, 'rb-import-manifest-draft.csv')
PROPVALS = os.path.join(GEN, 'bitrix-b2b-catalog-property-values.csv')

for p in (MANIFEST, PROPVALS):
    if not os.path.exists(p):
        sys.exit(f'Missing required evidence: {p}. Run the manifest generator first.')

# ---- load focus rows -----------------------------------------------------
focus = {r['legacy_element_id']: r for r in csv.DictReader(
    open(MANIFEST, encoding='utf-8-sig'))}
focus_ids = set(focus)

# ---- load spec properties per focus element ------------------------------
SPEC_CODES = {'VOLTAGE', 'AMPERNOST_AH', 'EMKOST_AH', 'EMKOST_MAH',
              'TEHNOLOGY', 'KHIMICHESKIY_SOSTAV', 'FX_FOR_BRAND', 'MOSHCHNOST'}
props = defaultdict(dict)
with open(PROPVALS, encoding='utf-8-sig', newline='') as f:
    for r in csv.DictReader(f):
        eid = r['legacy_element_id']
        if eid in focus_ids and r['property_code'] in SPEC_CODES:
            disp = (r['source_value_display'] or '').strip()
            if disp:
                props[eid][r['property_code']] = disp

# ---- parsers -------------------------------------------------------------
def num(s):
    m = re.search(r'\d+(?:[.,]\d+)?', s or '')
    return float(m.group(0).replace(',', '.')) if m else None

def name_capacity_ah(cap):
    # focus capacity_from_name is like "120Ah", "4.5Ah" (Ah); mAh would end mah
    if not cap:
        return None
    v = num(cap)
    if v is None:
        return None
    if re.search(r'mah|мач', cap, re.I):
        return v / 1000.0
    return v

TECH_FAMILY = {
    'AGM': 'lead', 'GEL': 'lead', 'OPzS': 'lead', 'OPzV': 'lead', 'VRLA': 'lead',
    'свинцово-кислотный': 'lead', 'свинцово-гелевый': 'lead',
    'Sealed Lead Acid': 'lead',
    'LiFePO4': 'li', 'Li-ion': 'li', 'Li-Pol': 'li', 'Li-MnO2': 'li',
    'литий-железо-фосфатный': 'li', 'литий-ионный': 'li',
    'NiMH': 'nimh', 'NiCd': 'nicd',
}
def fam(tech):
    if not tech:
        return None
    return TECH_FAMILY.get(tech, TECH_FAMILY.get(tech.strip(), None))

# Battery packs are cells in series, so any near-integer multiple of a common
# cell voltage is plausible (e.g. 108 В = 9x12, 90 В = 25x3.6).
CELL_VOLTS = [1.2, 2, 2.4, 3.2, 3.6, 3.7, 3.8, 6, 12]
def plausible_voltage(pv):
    for base in CELL_VOLTS:
        k = pv / base
        if abs(k - round(k)) < 0.04 and round(k) >= 1:
            return True
    return False

findings = []
def add(eid, cls, sev, field, nv, pv, note, action):
    r = focus[eid]
    findings.append({
        'legacy_element_id': eid,
        'name': r['name'],
        'legacy_url_candidate': r['legacy_url_candidate'],
        'error_class': cls,
        'severity': sev,
        'field': field,
        'value_in_name': nv,
        'value_in_property': pv,
        'note': note,
        'suggested_action': action,
    })

# ---- A. name vs property spec mismatches ---------------------------------
for eid, r in focus.items():
    p = props.get(eid, {})

    # voltage
    nv = num(r['voltage_from_name'])
    pv = num(p.get('VOLTAGE', ''))
    if nv is not None and pv is not None and abs(nv - pv) > 0.06:
        add(eid, 'E1_voltage_mismatch', 'high', 'напряжение',
            r['voltage_from_name'], p.get('VOLTAGE'),
            f'в названии {nv} В, в свойстве {pv} В',
            'сверить фактическое напряжение; исправить название или свойство в 1С/на сайте')

    # capacity (Ah)
    nc = name_capacity_ah(r['capacity_from_name'])
    pc = num(p.get('AMPERNOST_AH', '')) or num(p.get('EMKOST_AH', ''))
    if nc is not None and pc is not None and pc > 0:
        rel = abs(nc - pc) / max(nc, pc)
        if rel > 0.05:
            # >20% is almost certainly an error; 5-20% may be a C-rate rating
            # difference (lead-acid capacity depends on discharge current).
            big = rel > 0.20
            add(eid, 'E2_capacity_mismatch', 'high' if big else 'medium', 'ёмкость',
                r['capacity_from_name'], f"{p.get('AMPERNOST_AH') or p.get('EMKOST_AH')} А·ч",
                f'в названии {nc} А·ч, в свойстве {pc} А·ч' +
                ('' if big else ' (небольшое расхождение — возможно разный режим разряда C)'),
                'сверить фактическую ёмкость; исправить название или свойство')

    # technology
    nt = r['technology_from_name']
    ptech = p.get('TEHNOLOGY')
    if nt and ptech and nt.upper() != ptech.upper():
        add(eid, 'E4_technology_subtype_mismatch', 'medium', 'технология',
            nt, ptech, f'название: {nt}, свойство TEHNOLOGY: {ptech}',
            'сверить тип; AGM и GEL — разные, исправить расхождение')
    nf = fam(nt)
    kf = fam(p.get('KHIMICHESKIY_SOSTAV'))
    if nf and kf and nf != kf:
        add(eid, 'E3_technology_family_mismatch', 'high', 'химия/технология',
            nt, p.get('KHIMICHESKIY_SOSTAV'),
            f'семейство из названия ({nf}) ≠ хим.состав в базе ({kf})',
            'грубое расхождение химии — проверить, что это тот же товар')

# ---- B. identity collisions (contradictory or duplicate) -----------------
coll_groups = defaultdict(list)
for eid, r in focus.items():
    if r['identity_collision']:
        coll_groups[r['identity_match_key']].append(eid)

def spec_tuple(eid):
    p = props.get(eid, {})
    return (num(p.get('VOLTAGE', '')),
            num(p.get('AMPERNOST_AH', '')) or num(p.get('EMKOST_AH', '')),
            (p.get('TEHNOLOGY') or p.get('KHIMICHESKIY_SOSTAV') or '').upper())

for key, ids in coll_groups.items():
    specs = {eid: spec_tuple(eid) for eid in ids}
    names = {eid: focus[eid]['name'] for eid in ids}
    distinct_specs = set(specs.values())
    brand = focus[ids[0]]['brand_candidate']
    mpn = focus[ids[0]]['mpn_candidate_from_name']
    partners = ' || '.join(f"#{i}:{names[i]}" for i in ids)
    if len(distinct_specs) > 1:
        for eid in ids:
            add(eid, 'E5_identity_collision_contradictory', 'high', 'артикул',
                f'{brand} {mpn}', partners,
                f'одинаковый артикул у товаров с РАЗНЫМИ характеристиками',
                'дать разные артикулы/варианты или исправить характеристики')
    else:
        for eid in ids:
            add(eid, 'E6_identity_collision_duplicate', 'medium', 'артикул',
                f'{brand} {mpn}', partners,
                'одинаковый артикул и одинаковые характеристики',
                'вероятный дубль карточки — объединить или различить вариантом')

# ---- C. exact duplicate names --------------------------------------------
byname = defaultdict(list)
for eid, r in focus.items():
    byname[r['name'].strip().lower()].append(eid)
for nm, ids in byname.items():
    if len(ids) > 1:
        for eid in ids:
            others = ', '.join('#' + i for i in ids if i != eid)
            add(eid, 'E7_duplicate_name', 'medium', 'наименование',
                focus[eid]['name'], f'дубли: {others}',
                f'{len(ids)} карточек с идентичным названием',
                'объединить дубли или уточнить названия')

# ---- D. mixed-script tokens (homoglyphs) ---------------------------------
LAT = re.compile('[A-Za-z]')
CYR = re.compile('[А-Яа-яЁё]')
for eid, r in focus.items():
    for tok in re.split(r'\s+', r['name']):
        core = re.sub(r'[^0-9A-Za-zА-Яа-яЁё]', '', tok)
        if len(core) >= 2 and LAT.search(core) and CYR.search(core):
            add(eid, 'E8_mixed_script_token', 'medium', 'наименование',
                tok, '', f'токен «{tok}» смешивает латиницу и кириллицу',
                'привести к одному алфавиту (частая причина — I/О/С/Р/Н/М/К/В/Т/Х)')
            break

# ---- E. missing all key specs (active focus product) ---------------------
for eid, r in focus.items():
    if r['active'] != 'Y':
        continue
    p = props.get(eid, {})
    has_v = bool(num(p.get('VOLTAGE', '')) or num(r['voltage_from_name']))
    has_c = bool(num(p.get('AMPERNOST_AH', '')) or num(p.get('EMKOST_AH', '')) or
                 name_capacity_ah(r['capacity_from_name']))
    has_t = bool(p.get('TEHNOLOGY') or p.get('KHIMICHESKIY_SOSTAV') or r['technology_from_name'])
    if r['proposed_shared_category'] == 'ibp-ustroystva':
        continue  # UPS devices use power, not battery specs
    if not has_v and not has_c and not has_t:
        add(eid, 'E9_missing_all_specs', 'medium', 'характеристики', '', '',
            'нет ни напряжения, ни ёмкости, ни технологии — ни в названии, ни в свойствах',
            'заполнить ключевые характеристики в 1С')

# ---- F. implausible voltage ----------------------------------------------
for eid, r in focus.items():
    pv = num(props.get(eid, {}).get('VOLTAGE', ''))
    if pv is not None and pv > 0 and not plausible_voltage(pv):
        add(eid, 'E10_implausible_voltage', 'low', 'напряжение', '',
            props[eid]['VOLTAGE'], f'напряжение {pv} В не кратно типовому напряжению ячейки',
            'проверить значение напряжения')

# ---- write outputs -------------------------------------------------------
sev_order = {'high': 0, 'medium': 1, 'low': 2}
findings.sort(key=lambda x: (sev_order[x['severity']], x['error_class'], x['name']))

out_csv = os.path.join(GEN, 'rb-nomenclature-findings.csv')
cols = ['legacy_element_id', 'name', 'legacy_url_candidate', 'error_class',
        'severity', 'field', 'value_in_name', 'value_in_property', 'note',
        'suggested_action']
with open(out_csv, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(findings)

by_class = Counter(x['error_class'] for x in findings)
by_sev = Counter(x['severity'] for x in findings)
affected = len(set(x['legacy_element_id'] for x in findings))
summary = {
    'focus_rows_audited': len(focus),
    'total_findings': len(findings),
    'affected_products': affected,
    'by_severity': dict(by_sev),
    'by_class': dict(by_class.most_common()),
    'output_csv': out_csv,
    'note': 'read-only audit; fix in 1C and legacy site, then re-run extractor+manifest+audit',
}
with open(os.path.join(GEN, 'rb-nomenclature-findings-summary.json'),
          'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

# ---- human-readable report -----------------------------------------------
CLASS_INFO = {
    'E1_voltage_mismatch': ('Напряжение: название ≠ свойство',
        'Напряжение в названии не совпадает с полем VOLTAGE в базе.'),
    'E2_capacity_mismatch': ('Ёмкость: название ≠ свойство',
        'Ёмкость в названии не совпадает с полем ёмкости. Крупные расхождения '
        '(>20%) почти наверняка ошибка; мелкие могут быть разным режимом разряда.'),
    'E3_technology_family_mismatch': ('Химия/технология: грубое расхождение',
        'Семейство технологии из названия не совпадает с хим.составом в базе '
        '(например, литий против никеля) — вероятно, разные товары под одной карточкой.'),
    'E4_technology_subtype_mismatch': ('Технология: AGM ≠ GEL',
        'Тип в названии не совпадает с полем TEHNOLOGY (AGM и GEL — разные).'),
    'E5_identity_collision_contradictory': ('Один артикул — разные товары',
        'Один код модели у товаров с РАЗНЫМИ характеристиками '
        '(варианты с/без электролита, AGM/GEL, разная ёмкость). Дать разные артикулы/варианты.'),
    'E6_identity_collision_duplicate': ('Один артикул — вероятный дубль',
        'Один код модели и совпадающие характеристики — возможно, дубль карточки.'),
    'E7_duplicate_name': ('Полностью одинаковые названия',
        'Несколько карточек с идентичным названием.'),
    'E8_mixed_script_token': ('Смешение латиницы и кириллицы',
        'В коде модели смешаны латинские и кириллические буквы (I/О/С/Р/Н/М/К/В/Т/Х). '
        'Ломает поиск и группировку; привести к одному алфавиту.'),
    'E9_missing_all_specs': ('Нет ключевых характеристик',
        'У активного товара нет ни напряжения, ни ёмкости, ни технологии.'),
    'E10_implausible_voltage': ('Подозрительное напряжение',
        'Напряжение не кратно типовому напряжению ячейки.'),
}
COLLISION_CLASSES = {'E5_identity_collision_contradictory',
                     'E6_identity_collision_duplicate', 'E7_duplicate_name'}

lines = []
lines.append('# Аудит номенклатуры RB — нестыковки для исправления в 1С и на сайте')
lines.append('')
lines.append(f'Автоматическая read-only проверка {summary["focus_rows_audited"]} '
             f'позиций фокуса. Найдено проблем в **{affected} товарах**. Источник '
             'не изменялся. После правок в 1С и на старом сайте перегенерируйте '
             'выгрузку и запустите `scripts/audit-rb-nomenclature.py` заново.')
lines.append('')
lines.append('Полный список с ID и URL: `docs/audits/generated/rb-nomenclature-findings.csv`.')
lines.append('')
lines.append('| Класс | Проблем | Строк | Важность |')
lines.append('| --- | ---: | ---: | --- |')
for cls, (title, _) in CLASS_INFO.items():
    rs = [x for x in findings if x['error_class'] == cls]
    if not rs:
        continue
    if cls in COLLISION_CLASSES:
        issues = len(set(x['value_in_property'] for x in rs))
    else:
        issues = len(rs)
    sev = rs[0]['severity']
    lines.append(f'| {title} | {issues} | {len(rs)} | {sev} |')
lines.append('')

for cls, (title, desc) in CLASS_INFO.items():
    rs = [x for x in findings if x['error_class'] == cls]
    if not rs:
        continue
    lines.append(f'## {title}')
    lines.append('')
    lines.append(desc)
    lines.append('')
    if cls in COLLISION_CLASSES:
        seen = set()
        for x in rs:
            if x['value_in_property'] in seen:
                continue
            seen.add(x['value_in_property'])
            partners = x['value_in_property'].replace('||', '↔')
            lines.append(f'- **{x["value_in_name"]}** — {partners}')
    else:
        for x in rs:
            url = x['legacy_url_candidate'] or '—'
            detail = x['note']
            lines.append(f'- #{x["legacy_element_id"]} `{x["name"]}` ({url}) — {detail}')
    lines.append('')

report_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'docs', 'imports', '2026-07-16-rb-nomenclature-findings.md')
os.makedirs(os.path.dirname(report_path), exist_ok=True)
with open(report_path, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines))

# ---- Google-Sheets-ready workbook ----------------------------------------
# Refresh docs/imports/microchips-nomenclature-fixes.xlsx on every run.
# Non-fatal: the CSV + markdown report above are the primary outputs, so a
# missing openpyxl only skips the workbook instead of failing the audit.
xlsx_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'docs', 'imports', 'microchips-nomenclature-fixes.xlsx')
_builder = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'build-nomenclature-xlsx.py')
try:
    _spec = importlib.util.spec_from_file_location('build_nomenclature_xlsx', _builder)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)  # raises ImportError if openpyxl is absent
    _mod.build_xlsx(findings, xlsx_path, focus_count=len(focus))
    print('xlsx:', xlsx_path)
except ImportError:
    print('[warn] openpyxl not installed — skipped xlsx workbook; '
          'install with: pip install openpyxl', file=sys.stderr)

print(json.dumps(summary, ensure_ascii=False, indent=2))
print('report:', report_path)
