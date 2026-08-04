#!/usr/bin/env python3
"""Build a non-importable FANSO image-rights blocker manifest for wave80."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


CHECKED_AT = "2026-07-27"
RIGHTS_SOURCE_URL = "https://www.fansobattery.com/?list_72%2F780.html="


MODELS: dict[str, dict[str, str]] = {
    "ER14250H": {
        "page": "https://www.fansobattery.com/?list_43%2F507.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20230907/1694071967766208.jpg",
        "visual": "Один базовый цилиндрический элемент с маркировкой ER14250H 3.6V; разъёмы и провода не показаны.",
    },
    "ER14335H": {
        "page": "https://www.fansobattery.com/?list_43%2F508.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20250313/1741831243119988.jpg",
        "visual": "Два ракурса базового элемента ER14335H 3.6V; изображение не подтверждает комплект из двух элементов.",
    },
    "ER14505H": {
        "page": "https://www.fansobattery.com/?list_43%2F506.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20230907/1694071930330548.jpg",
        "visual": "Один базовый цилиндрический элемент с маркировкой ER14505H 3.6V; разъёмы и провода не показаны.",
    },
    "ER17505H": {
        "page": "https://www.fansobattery.com/?list_43%2F505.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20250313/1741844221778234.jpg",
        "visual": "Два ракурса базового элемента ER17505H 3.6V; изображение не подтверждает комплект из двух элементов.",
    },
    "ER18505H": {
        "page": "https://www.fansobattery.com/?list_43%2F504.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20230907/1694071828236852.jpg",
        "visual": "Один базовый цилиндрический элемент с маркировкой ER18505H 3.6V; разъёмы и провода не показаны.",
    },
    "ER26500H": {
        "page": "https://www.fansobattery.com/?list_43%2F503.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20230907/1694070458150752.jpg",
        "visual": "Два ракурса базового элемента ER26500H 3.6V; изображение не подтверждает комплект из двух элементов.",
    },
    "ER34615H": {
        "page": "https://www.fansobattery.com/?list_43%2F502.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20230907/1694067554168940.jpg",
        "visual": "Один базовый цилиндрический элемент с маркировкой ER34615H 3.6V; разъёмы и провода не показаны.",
    },
    "ER18505M": {
        "page": "https://www.fansobattery.com/?list_44%2F511.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20230907/1694072247461053.jpg",
        "visual": "Один базовый цилиндрический элемент с маркировкой ER18505M 3.6V; разъёмы и провода не показаны.",
    },
    "ER34615M": {
        "page": "https://www.fansobattery.com/?list_44%2F509.html=",
        "asset": "https://www.fansobattery.com/static/upload/image/20230907/1694072382558684.jpg",
        "visual": "Один базовый цилиндрический элемент с маркировкой ER34615M 3.6V; разъёмы и провода не показаны.",
    },
}


LIMITATION = (
    "Даже после получения прав изображение базовой модели не подтверждает разъём, "
    "клеммы, выводы, длину или цвет проводов, исполнение /S, /P, LD, PF/PT, "
    "комплектность, схему сборки, совместимость или страну происхождения конкретной позиции."
)


def blocked_row(source: dict[str, object], model: str) -> dict[str, object]:
    mapping = MODELS[model]
    return {
        "external_id": str(source["external_id"]),
        "manufacturer": "FANSO",
        "identity_scope": "model_core",
        "source_scope": "model_core",
        "model_core": model,
        "candidate_status": "blocked_rights",
        "review_status": "needs_written_permission",
        "publication_status": "blocked",
        "source_page_url": mapping["page"],
        "source_asset_url": mapping["asset"],
        "source_kind": f"official FANSO {model} product-page primary gallery image",
        "safe_alt_if_rights_granted": (
            f"Литиевый элемент FANSO {model} — изображение производителя"
        ),
        "visual_observation": mapping["visual"],
        "limitation": LIMITATION,
        "rights_status": "no_written_permission",
        "rights_source_url": RIGHTS_SOURCE_URL,
        "required_action": (
            "Получить явное письменное разрешение FANSO на коммерческое копирование, "
            "локальное хранение, изменение и публикацию изображения."
        ),
        "remote_check": {
            "checked_at": CHECKED_AT,
            "http_status": 200,
            "mime_type": "image/jpeg",
            "observed_pixel_width": 560,
            "observed_pixel_height": 422,
            "local_copy_retained": False,
        },
    }


def build_payload(
    wave80_products: Iterable[dict[str, object]], expected: int
) -> dict[str, object]:
    blocked: list[dict[str, object]] = []
    seen: set[str] = set()
    for source in wave80_products:
        external_id = str(source.get("external_id", "")).strip()
        model = str(source.get("model_core", "")).strip()
        if not external_id:
            raise RuntimeError("wave80 row has no external_id")
        if external_id in seen:
            raise RuntimeError(f"wave80 repeats external_id {external_id}")
        seen.add(external_id)
        if source.get("manufacturer") != "FANSO":
            raise RuntimeError(f"wave80 row is not FANSO: {external_id}")
        if source.get("identity_scope") != "model_core":
            raise RuntimeError(f"wave80 row escaped model_core scope: {external_id}")
        if model not in MODELS:
            raise RuntimeError(f"wave80 row has unsupported FANSO model: {external_id}/{model}")
        blocked.append(blocked_row(source, model))

    if len(blocked) != expected:
        raise RuntimeError(f"Expected {expected} blocked FANSO candidates, got {len(blocked)}")

    return {
        "schema_version": 1,
        "manifest_kind": "blocked_image_rights_audit",
        "stage_source_image_candidates_compatible": False,
        "purpose": (
            "FANSO official image URLs are recorded for provenance only. The manufacturer "
            "requires written permission; no local copy, ProductMedia import or publication is authorized."
        ),
        "locale": "ru-BY",
        "rights_evidence": {
            "source_url": RIGHTS_SOURCE_URL,
            "checked_at": CHECKED_AT,
            "finding": (
                "FANSO states that website images and other information are protected and "
                "unauthorized use is prohibited without express written consent."
            ),
            "permission_status": "not_obtained",
        },
        "blocked_candidates": blocked,
    }


def serialize_payload(payload: dict[str, object]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wave80", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expected", type=int, default=27)
    args = parser.parse_args()

    source = json.loads(args.wave80.read_text(encoding="utf-8"))
    if not isinstance(source, dict) or not isinstance(source.get("products"), list):
        raise RuntimeError("wave80 manifest must contain a products list")
    payload = build_payload(source["products"], args.expected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(serialize_payload(payload))
    print(
        json.dumps(
            {
                "blocked_candidates": len(payload["blocked_candidates"]),
                "unique_remote_assets": len(
                    {row["source_asset_url"] for row in payload["blocked_candidates"]}
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
