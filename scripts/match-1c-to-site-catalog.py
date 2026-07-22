#!/usr/bin/env python3
"""Match a 1C nomenclature export against the site catalog (Bitrix products).

The two sides share NO common identifier (that is the whole Gate-0 problem), so
matching is by product model code and name:
  1. article_in_name : 1C `Артикул` (alnum-normalized, >=4 chars) occurs inside
     the site product name  -> high confidence.
  2. mpn_eq_article  : site MPN candidate == 1C `Артикул` (alnum-equal) -> highest.
  3. name_similarity : token-set containment between the two names over a
     threshold -> medium; reported for human review, never auto-trusted blindly.

Nothing is invented: unmatched rows on BOTH sides are written out explicitly so
coverage is honest. Confidence + method travel with every match.

Usage:
  python scripts/match-1c-to-site-catalog.py <1c_export.csv> [--out DIR] [--threshold 0.6]

Input 1C CSV: delimiter auto-detected (`,` or `;`); columns found by fuzzy header
match (Код / Артикул / Наименование / Цена). Site side is read from
docs/imports/site-catalog-full-products.csv.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_CSV = os.path.join(REPO, "docs", "imports", "site-catalog-full-products.csv")

# Words that carry no identity — dropped before name-token comparison.
STOP = {
    "аккумулятор", "аккумуляторная", "батарея", "для", "агм", "гелевый", "гелевая",
    "agm", "gel", "opzs", "ah", "mah", "wh", "v", "в", "ач", "мач",
}


def alnum(s: str) -> str:
    """Uppercase, keep only latin/cyrillic letters and digits."""
    return re.sub(r"[^0-9A-ZА-ЯЁ]", "", (s or "").upper())


def name_tokens(s: str) -> set[str]:
    toks = re.split(r"[^0-9a-zA-Zа-яА-ЯёЁ]+", (s or "").lower())
    return {t for t in toks if t and t not in STOP and not re.fullmatch(r"\d{1,2}", t)}


def containment(a: set[str], b: set[str]) -> float:
    """Fraction of the smaller token set covered by the larger."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b))


def sniff_delim(path: str) -> str:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        head = fh.readline()
    return ";" if head.count(";") >= head.count(",") else ","


def find_col(fieldnames: list[str], *needles: str) -> str | None:
    for f in fieldnames:
        low = f.strip().lower()
        if any(n in low for n in needles):
            return f
    return None


def load_1c(path: str) -> list[dict]:
    delim = sniff_delim(path)
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, delimiter=delim)
        rows = list(reader)
        fn = reader.fieldnames or []
    c_code = find_col(fn, "код") or (fn[0] if fn else None)
    c_art = find_col(fn, "артикул", "sku")
    c_name = find_col(fn, "наименование", "название", "name")
    c_price = find_col(fn, "цена", "price")
    if not c_name:
        sys.exit(f"1C CSV: could not find a name column in {fn}")
    out = []
    for r in rows:
        # skip group rows if the export flags them
        grp = find_col(fn, "этогруппа", "isfolder")
        if grp and str(r.get(grp, "")).strip().upper() in {"ИСТИНА", "TRUE", "1", "ДА"}:
            continue
        out.append({
            "code": (r.get(c_code) or "").strip() if c_code else "",
            "article": (r.get(c_art) or "").strip() if c_art else "",
            "name": (r.get(c_name) or "").strip(),
            "price": (r.get(c_price) or "").strip() if c_price else "",
        })
    return out


def load_site() -> list[dict]:
    if not os.path.exists(SITE_CSV):
        sys.exit(f"Site catalog not found (run build-site-catalog-for-1c-mapping.py): {SITE_CSV}")
    with open(SITE_CSV, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        name = r.get("Название", "")
        out.append({
            "bitrix_id": r.get("Bitrix ID", ""),
            "name": name,
            "mpn": (r.get("MPN? (кандидат)") or "").strip(),
            "brand": (r.get("Бренд? (кандидат)") or "").strip(),
            "name_alnum": alnum(name),
            "tokens": name_tokens(name),
        })
    return out


def match(one_c: list[dict], site: list[dict], threshold: float) -> tuple[list[dict], list[dict], list[dict]]:
    site_by_mpn: dict[str, list[dict]] = {}
    for s in site:
        if s["mpn"]:
            site_by_mpn.setdefault(alnum(s["mpn"]), []).append(s)

    matched, unmatched_1c = [], []
    site_hit: set[str] = set()

    for c in one_c:
        art = alnum(c["article"])
        ctoks = name_tokens(c["name"])
        best = None  # (site, method, confidence)

        # A model code can be shared across brands (e.g. "GP1272 F2" exists for
        # CSB, WBR, ...), so whenever more than one site product carries it we
        # must let the 1C name (which contains the brand) pick the right one.
        def disambiguate(cands: list[dict]) -> tuple[dict, bool]:
            if len(cands) == 1:
                return cands[0], True
            ranked = sorted(cands, key=lambda s: containment(ctoks, s["tokens"]), reverse=True)
            top = containment(ctoks, ranked[0]["tokens"])
            second = containment(ctoks, ranked[1]["tokens"])
            return ranked[0], (top > second)  # unambiguous only if a clear winner

        # 2. exact MPN == article (brand-disambiguated)
        if art and len(art) >= 4 and art in site_by_mpn:
            pick, clear = disambiguate(site_by_mpn[art])
            best = (pick, "mpn_eq_article" if clear else "mpn_eq_article_ambiguous",
                    0.98 if clear else 0.75)

        # 1. article substring of site name (brand-disambiguated)
        if best is None and art and len(art) >= 4:
            cands = [s for s in site if art in s["name_alnum"]]
            if cands:
                pick, clear = disambiguate(cands)
                best = (pick, "article_in_name" if clear else "article_in_name_ambiguous",
                        0.95 if clear else 0.8)

        # 3. name similarity
        if best is None:
            scored = [(containment(ctoks, s["tokens"]), s) for s in site]
            scored.sort(key=lambda x: x[0], reverse=True)
            if scored and scored[0][0] >= threshold:
                best = (scored[0][1], "name_similarity", round(scored[0][0], 2))

        if best:
            s, method, conf = best
            site_hit.add(s["bitrix_id"])
            matched.append({
                "bitrix_id": s["bitrix_id"], "site_name": s["name"],
                "one_c_code": c["code"], "one_c_article": c["article"], "one_c_name": c["name"],
                "price_1c": c["price"], "method": method, "confidence": conf,
            })
        else:
            unmatched_1c.append(c)

    unmatched_site = [s for s in site if s["bitrix_id"] not in site_hit]
    return matched, unmatched_site, unmatched_1c


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("one_c_csv")
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "imports"))
    ap.add_argument("--threshold", type=float, default=0.6)
    args = ap.parse_args()

    site = load_site()
    one_c = load_1c(args.one_c_csv)
    matched, un_site, un_1c = match(one_c, site, args.threshold)

    os.makedirs(args.out, exist_ok=True)

    def write(path, rows, header):
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            for r in rows:
                w.writerow(r)

    write(os.path.join(args.out, "match-1c-matched.csv"),
          [[m["bitrix_id"], m["site_name"], m["one_c_code"], m["one_c_article"],
            m["one_c_name"], m["price_1c"], m["method"], m["confidence"]] for m in matched],
          ["Bitrix ID", "Название сайта", "1С-код", "1С-Артикул", "1С-Наименование",
           "1С-Цена", "метод", "уверенность"])
    write(os.path.join(args.out, "match-1c-unmatched-site.csv"),
          [[s["bitrix_id"], s["name"]] for s in un_site], ["Bitrix ID", "Название сайта"])
    write(os.path.join(args.out, "match-1c-unmatched-1c.csv"),
          [[c["code"], c["article"], c["name"]] for c in un_1c],
          ["1С-код", "1С-Артикул", "1С-Наименование"])

    high = sum(1 for m in matched if m["confidence"] >= 0.9)
    print(f"1С позиций (товары): {len(one_c)}")
    print(f"Сайт позиций: {len(site)}")
    print(f"Сопоставлено: {len(matched)}  (высокая уверенность >=0.9: {high})")
    print(f"  по методам: " + ", ".join(
        f"{m}={sum(1 for x in matched if x['method']==m)}"
        for m in sorted({x['method'] for x in matched})) if matched else "  —")
    print(f"Сайт без пары: {len(un_site)}")
    print(f"1С без пары: {len(un_1c)}")
    print(f"Файлы: match-1c-matched.csv / -unmatched-site.csv / -unmatched-1c.csv в {args.out}")


if __name__ == "__main__":
    main()
