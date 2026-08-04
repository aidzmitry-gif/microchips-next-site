#!/usr/bin/env python3
"""Expand reviewed manufacturer series definitions into the three gated RB manifests."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def slugify(value: str) -> str:
    # A plus sign is identity-bearing in manufacturer MPNs (for example,
    # 12HX650F-FR+). Dropping it would reserve the same storefront path as the
    # non-plus model, so preserve the distinction in an URL-safe form.
    value = value.replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not value.get("site_key") or not value.get("locale"):
        raise ValueError("source schema_version/site_key/locale are required")
    if not isinstance(value.get("series"), list) or not value["series"]:
        raise ValueError("source requires at least one series")
    return value


def build(source: dict) -> tuple[dict, dict, dict]:
    candidates: list[dict] = []
    descriptions: list[dict] = []
    previews: list[dict] = []
    seen: set[str] = set()

    for series in source["series"]:
        for field in ("manufacturer", "series", "source_url", "technology"):
            if not isinstance(series.get(field), str) or not series[field].strip():
                raise ValueError(f"series requires {field}")
        if not str(series["source_url"]).startswith("https://"):
            raise ValueError("source_url must be HTTPS")
        if not isinstance(series.get("facts"), dict) or not series["facts"]:
            raise ValueError("series requires facts")
        models = series.get("models")
        if not isinstance(models, list) or not models:
            raise ValueError("series requires models")
        model_facts = series.get("model_facts", {})
        if not isinstance(model_facts, dict):
            raise ValueError("model_facts must be an object keyed by exact model")
        unknown_fact_models = set(model_facts) - set(models)
        if unknown_fact_models:
            raise ValueError(
                "model_facts contains models absent from models: "
                + ", ".join(sorted(unknown_fact_models))
            )
        for fact_model, facts in model_facts.items():
            if not isinstance(facts, dict) or not facts:
                raise ValueError(f"model_facts[{fact_model}] must be a non-empty object")
        model_labels = series.get("model_labels", {})
        if not isinstance(model_labels, dict):
            raise ValueError("model_labels must be an object keyed by exact model")
        unknown_label_models = set(model_labels) - {
            model for model in models if isinstance(model, str)
        }
        if unknown_label_models:
            raise ValueError(
                "model_labels contains models absent from models: "
                + ", ".join(sorted(unknown_label_models))
            )
        for label_model, label in model_labels.items():
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"model_labels[{label_model}] must be a non-empty string")

        for model in models:
            if not isinstance(model, str) or not model.strip():
                raise ValueError("model must be a non-empty string")
            model = model.strip()
            identity = model.casefold()
            if identity in seen:
                raise ValueError(f"repeated model: {model}")
            seen.add(identity)
            manufacturer = series["manufacturer"].strip()
            slug = slugify(f"{manufacturer}-{model}")
            external_id = f"manufacturer:{manufacturer.lower()}:{model}"
            name_template = series.get("name_template", "Аккумулятор {manufacturer} {model} для резервного питания")
            if (
                not isinstance(name_template, str)
                or "{manufacturer}" not in name_template
                or ("{model}" not in name_template and "{label}" not in name_template)
            ):
                raise ValueError(
                    "name_template must contain {manufacturer} and either {model} or {label}"
                )
            label = model_labels.get(model, model).strip()
            name = name_template.format(manufacturer=manufacturer, model=model, label=label)
            category_external_id = series.get("category_external_id", source["category_external_id"])
            category_slug = series.get("category_slug", source["category_slug"])
            technical_attributes = {
                **series["facts"],
                **model_facts.get(model, {}),
            }
            common = {
                "external_id": external_id,
                "manufacturer": manufacturer,
                "mpn": model,
                "source_url": series["source_url"].strip(),
            }
            candidates.append({
                **common,
                "name": name,
                "slug": slug,
                "category_external_id": category_external_id,
                "technical_attributes": technical_attributes,
            })
            descriptions.append({
                **common,
                "technology": series["technology"].strip(),
                "display_name": name,
                "technical_attributes": technical_attributes,
            })
            previews.append({
                **common,
                "category_slug": category_slug,
                "product_slug": slug,
            })

    return (
        {"schema_version": 1, "site_key": source["site_key"], "products": candidates},
        {"schema_version": 1, "locale": source["locale"], "products": descriptions},
        {"locale": source["locale"], "products": previews},
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate_output", type=Path)
    parser.add_argument("description_output", type=Path)
    parser.add_argument("preview_output", type=Path)
    args = parser.parse_args()
    manifests = build(load(args.source))
    for path, payload in zip(
        (args.candidate_output, args.description_output, args.preview_output), manifests, strict=True
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
