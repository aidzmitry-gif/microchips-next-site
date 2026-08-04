#!/usr/bin/env python3
"""Build a non-destructive canonical registry for the full product catalog.

The registry is a source-of-truth staging artifact, not a publication file.
Every Bitrix product remains a row.  It may be linked to 1C or flagged as a
duplicate candidate, but it is never silently merged by a fuzzy name match.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

FIELDS = [
    "registry_id", "bitrix_id", "is_active", "name", "legacy_section_path",
    "legacy_url", "one_c_code", "one_c_article", "one_c_name", "one_c_path",
    "match_method", "match_score", "identity_status", "duplicate_candidate_key",
    "publication_status", "decision", "reason",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def duplicate_membership(path: Path) -> dict[str, str]:
    membership: dict[str, str] = {}
    for row in load_csv(path):
        key = row["candidate_key"]
        for bitrix_id in row["bitrix_ids"].split("|"):
            if bitrix_id:
                membership[bitrix_id] = key
    return membership


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bitrix", type=Path, required=True)
    parser.add_argument("--duplicates", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = load_csv(args.bitrix)
    memberships = duplicate_membership(args.duplicates)
    by_one_c: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = row.get("1С-код", "").strip()
        if code:
            by_one_c[code].append(row)

    result: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()
    for row in sorted(rows, key=lambda item: int(item["Bitrix ID"])):
        bitrix_id = row["Bitrix ID"]
        active = row.get("Активен", "").upper() == "Y"
        code = row.get("1С-код", "").strip()
        method = row.get("match_method", "").strip() or "unknown"
        duplicate_key = memberships.get(bitrix_id, "")
        reasons: list[str] = []

        if not active:
            identity_status = "inactive_source"
            publication = "do_not_publish"
            decision = "retain_for_redirect_audit"
            reasons.append("Неактивная запись Bitrix сохраняется только для миграционного аудита.")
        elif duplicate_key:
            identity_status = "duplicate_candidate"
            publication = "do_not_publish"
            decision = "verify_primary_identity"
            reasons.append("Совпадение нормализованного имени/модели не является основанием для слияния.")
        elif not code:
            identity_status = "unresolved_identity"
            publication = "do_not_publish"
            decision = "research_manufacturer_source"
            reasons.append("Нет доказуемой связи с 1С или первичного идентификатора.")
        elif len(by_one_c[code]) > 1:
            identity_status = "one_c_collision_candidate"
            publication = "do_not_publish"
            decision = "verify_one_c_cardinality"
            reasons.append("Один код 1С связан с несколькими строками Bitrix.")
        elif method == "exact_name":
            identity_status = "linked_exact_name"
            publication = "needs_content_quality_gate"
            decision = "retain_single_source_row"
            reasons.append("Связь основана на полном совпадении названия; перед публикацией нужны данные производителя.")
        else:
            identity_status = "linked_candidate"
            publication = "do_not_publish"
            decision = "verify_primary_identity"
            reasons.append(f"Связь получена методом {method}; автоматическая публикация запрещена.")

        status_counts[identity_status] += 1
        result.append({
            "registry_id": f"bitrix:{bitrix_id}",
            "bitrix_id": bitrix_id,
            "is_active": "true" if active else "false",
            "name": row.get("Название (сайт)", ""),
            "legacy_section_path": row.get("Раздел", ""),
            "legacy_url": row.get("Ссылка", ""),
            "one_c_code": code,
            "one_c_article": row.get("1С-артикул", ""),
            "one_c_name": row.get("1С-наименование", ""),
            "one_c_path": row.get("1С-путь", ""),
            "match_method": method,
            "match_score": row.get("match_score", ""),
            "identity_status": identity_status,
            "duplicate_candidate_key": duplicate_key,
            "publication_status": publication,
            "decision": decision,
            "reason": " ".join(reasons),
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(result)
    summary_path = args.out.with_name(args.out.stem + "-summary.json")
    summary_path.write_text(json.dumps({
        "rows": len(result),
        "active_rows": sum(row["is_active"] == "true" for row in result),
        "identity_status": dict(sorted(status_counts.items())),
        "invariant": "The registry has one row per Bitrix ID; no fuzzy-match merge occurs.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
