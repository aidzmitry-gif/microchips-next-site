#!/usr/bin/env python3
"""Clean, brand-safe match of site products to 1C nomenclature.

Matches on MODEL SIGNATURES: alnum token-windows that contain BOTH a letter and
a digit and are >=6 chars (e.g. GP1272F2, DTM12032, 12FGH23). A bare number
("1211") is never a signature, so "Корпус PJ-1211" can no longer collide with a
battery "Delta CT 1211" — the failure mode found in the previous match pass.

Inputs are two CSVs exported from the comparison sheet:
  site: columns include 'Bitrix ID','Название (сайт)','Бренд','MPN','1С-код'(prev)
  1c  : clean 3-col 'Код','Артикул','Наименование'
Outputs matched / unmatched-site / a diff against the sheet's existing 1С-код.

Usage: python scripts/match-1c-site-v2.py <site.csv> <1c_clean.csv> --out DIR
"""
from __future__ import annotations
import argparse, csv, os, re

def alnum(s: str) -> str:
    return re.sub(r"[^0-9A-Za-zА-Яа-яЁё]", "", s or "").upper()

def signatures(name: str) -> set[str]:
    toks = [t for t in re.split(r"[^0-9A-Za-zА-Яа-яЁё]+", name or "") if t]
    out: set[str] = set()
    for i in range(len(toks)):
        for w in range(1, 5):
            if i + w <= len(toks):
                m = alnum("".join(toks[i:i + w]))
                if 6 <= len(m) <= 18 and re.search(r"[A-ZА-Я]", m) and re.search(r"\d", m):
                    out.add(m)
    return out

def brand_tokens(name: str, brand: str) -> set[str]:
    src = (brand or "").strip() or " ".join((name or "").split()[1:3])
    return {alnum(t) for t in re.split(r"[^0-9A-Za-zА-Яа-яЁё]+", src) if len(t) >= 3}

def load(path, enc="utf-8-sig"):
    with open(path, encoding=enc, newline="") as fh:
        return list(csv.DictReader(fh))

def col(row, *names):
    for n in names:
        for k in row:
            if n.lower() in k.strip().lower():
                return (row[k] or "").strip()
    return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site_csv"); ap.add_argument("one_c_csv")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    site = load(a.site_csv)
    onec = load(a.one_c_csv)

    # index 1C items by signature
    idx: dict[str, list[dict]] = {}
    for c in onec:
        c["_name"] = col(c, "наименование", "название")
        c["_code"] = col(c, "код")
        c["_art"] = col(c, "артикул")
        c["_sigs"] = signatures(c["_name"]) | ({alnum(c["_art"])} if len(alnum(c["_art"])) >= 6 else set())
        for s in c["_sigs"]:
            idx.setdefault(s, []).append(c)

    # A signature shared by many distinct 1C codes is generic (brand+voltage like
    # "VENTURAGP12") and must NOT beat a rare, specific one ("GP12100").
    dfsig = {s: len({c["_code"] for c in lst}) for s, lst in idx.items()}

    matched, unmatched = [], []
    agree = differ = new = 0
    for s in site:
        sname = col(s, "название", "наименование")
        sbrand = col(s, "бренд")
        prev = col(s, "1с-код")
        bid = col(s, "bitrix id", "bitrix")
        ssigs = signatures(sname)
        sbrands = brand_tokens(sname, sbrand)

        # collect 1C candidates sharing a signature; score by best shared sig len + brand
        cand: dict[str, tuple] = {}
        for sig in ssigs:
            spec = dfsig.get(sig, 99) <= 2          # rare == discriminating
            for c in idx.get(sig, []):
                bok = bool(sbrands & brand_tokens(c["_name"], ""))
                score = (1 if bok else 0, 1 if spec else 0, len(sig))
                key = c["_code"]
                if key not in cand or score > cand[key][0]:
                    cand[key] = (score, c, sig, bok, spec)

        if not cand:
            unmatched.append((bid, sname, sbrand))
            continue
        # prefer brand-confirmed, then specific (rare) signature, then longer
        score, c, sig, bok, spec = max(cand.values(), key=lambda x: x[0])
        if (bok and spec and len(sig) >= 6) or (spec and len(sig) >= 10):
            conf = 0.95
        elif spec and len(sig) >= 6:
            conf = 0.85
        else:
            conf = 0.6                              # generic signature -> review
        method = ("sig+brand" if bok else "sig") + ("" if spec else "+generic")
        cmp = "new"
        if prev:
            cmp = "agree" if prev == c["_code"] else "differ"
        if cmp == "agree": agree += 1
        elif cmp == "differ": differ += 1
        else: new += 1
        matched.append([bid, sname, sbrand, c["_code"], c["_art"], c["_name"],
                        sig, "yes" if bok else "no", conf, method, prev, cmp])

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "match-v2-matched.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Bitrix ID", "Название сайта", "Бренд", "1С-код", "1С-Артикул",
                    "1С-Наименование", "signature", "brand_ok", "confidence", "method",
                    "1С-код(было Cursor)", "сравнение"])
        w.writerows(matched)
    with open(os.path.join(a.out, "match-v2-unmatched-site.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh); w.writerow(["Bitrix ID", "Название сайта", "Бренд"]); w.writerows(unmatched)

    hi = sum(1 for m in matched if m[8] >= 0.9)
    print(f"Сайт позиций: {len(site)}")
    print(f"Сопоставлено: {len(matched)}  (высокая уверенность >=0.9: {hi})")
    print(f"Не сопоставлено: {len(unmatched)}")
    print(f"Сверка с матчами Cursor: совпало={agree}, РАСХОЖДЕНИЕ={differ}, новых(Cursor не нашёл)={new}")

if __name__ == "__main__":
    main()
