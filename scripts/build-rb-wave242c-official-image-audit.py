#!/usr/bin/env python3
"""Build the Wave242C official-source image audit for the 44 Wave241 products."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs/audits/generated"
IMPORTS = ROOT / "docs/imports"
MANIFEST = IMPORTS / "rb-source-backed-descriptions-wave241-2026-07-29.json"
ACTIONABLE = GENERATED / "rb-wave241c-new-description-actionable.csv"
PRIOR_REVIEW = GENERATED / "rb-wave235-reviewed-media.csv"
PRIOR_SKIP = GENERATED / "rb-wave237-reviewed-media-skip-ledger.csv"
PRIOR_HOLD_229B = GENERATED / "rb-wave229b-hold-002-visual-review.csv"
PRIOR_REVIEW_229C = GENERATED / "rb-reviewed-legacy-preview-media-wave229c.csv"
RIGHTS_POLICY = ROOT / "docs/audits/2026-07-29-rb-wave241b-media-profile.md"
ASSET_DIR = GENERATED / "rb-wave242c-official-image-audit/assets"
RENDER_DIR = GENERATED / "rb-wave242c-official-image-audit/pages"
SHEET_DIR = GENERATED / "rb-wave242c-official-image-audit/contact-sheets"
LEDGER = GENERATED / "rb-wave242c-official-image-ledger.csv"
CANDIDATE_INDEX = GENERATED / "rb-wave242c-official-image-candidate-index.csv"
SUMMARY = GENERATED / "rb-wave242c-official-image-audit.summary.json"
REPORT = ROOT / "docs/audits/2026-07-29-rb-wave242c-official-image-audit.md"
PROMOTION = IMPORTS / "rb-official-exact-media-wave242c-2026-07-29.json"

INPUT_PINS = {
    MANIFEST: "35c66fcc25b52bc7f36071d788431fe87f0e42e9d00abd4bf1f1d69b2db34ca5",
    ACTIONABLE: "5338ca287b42a60bd732f0c1d0d987cb6d69d2aebef1fb44fa8b57dd47619387",
    PRIOR_REVIEW: "611b166bb32aecfca6f507fa40cd6ab0d1a7503aa2552108a712950eb782823d",
    PRIOR_SKIP: "9e4223a5c394aee82c626e72bc4f75abe5470051b61d5fa0ace7eaad37f4e059",
    PRIOR_HOLD_229B: "6f6a0df844ecf895c80ee7b0a007c3ebb12695c65d3c0d4405d0ae558cc10d08",
    PRIOR_REVIEW_229C: "a3080a9544f46b62015c0e6d33312bcf78ed2cb10437870f7b0d980be0b52007",
    RIGHTS_POLICY: "6f293a4418b184694e17b6bf77d2d769518b7066ae8c8ac6799f14f2880cdf74",
}

APC_LOCAL = {
    "SPD_NCAO-ALAHB6_FL_V": "apc-shared-rbc17-rbc40.jpg",
    "SPD_STOS-7RS4JW_FL_H": "apc-rbc14.jpg",
    "SPD_NCAO-ALAPXU_FL_V": "apc-rbc9.jpg",
    "SPD_MMAE-849RFY_FL_H": "apc-rbc24.jpg",
}

PDF_VISUAL = {
    "EnerSys": (
        "NOT_EXACT_FAMILY_OR_SELECTION_TABLE",
        "CYCLON pages combine family cell photography/diagrams with multi-model selection tables; no complete target part number is readable on a pictured item.",
    ),
    "Sonnenschein": (
        "NOT_EXACT_FAMILY_OR_SELECTION_TABLE",
        "A600/A700 pages use family cell/container visuals and multi-model tables; no complete target A602/A706 model is readable on a pictured item.",
    ),
    "MNB": (
        "NOT_EXACT_FAMILY_OR_SELECTION_TABLE",
        "The two-page catalogue uses series/range product visuals beside multi-model tables; the visual does not independently expose each target exact MPN.",
    ),
    "Panasonic": (
        "EXACT_MODEL_DOCUMENT_PAGE_ONLY",
        "The handbook has model-specific dimensional pages tied to the exact MPN, but the reusable visual is embedded in the copyrighted handbook and no reuse grant is documented.",
    ),
    "Ventura": (
        "NOT_EXACT_FAMILY_OR_SELECTION_TABLE",
        "Catalogue pages show GP/GPL/HRL family product visuals beside tables; the pictured labels do not independently prove each target exact MPN.",
    ),
}

LEDGER_FIELDS = [
    "priority",
    "product_external_id",
    "name",
    "manufacturer",
    "mpn",
    "decision",
    "official_candidate_kind",
    "visual_identity_status",
    "visual_review_note",
    "candidate_source_asset_url",
    "candidate_local_paths",
    "candidate_sha256",
    "candidate_pages",
    "source_url",
    "source_snapshot_path",
    "source_snapshot_sha256",
    "rights_status",
    "rights_evidence_path",
    "rights_evidence_note",
    "prior_legacy_decision",
    "prior_legacy_review_path",
    "prior_no_repeat_path",
    "promotion_eligible",
    "next_action",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise SystemExit(f"SHA drift for {path.relative_to(ROOT)}: {actual} != {expected}")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def normalized(value: str) -> str:
    return "".join(char.casefold() for char in value if char.isalnum())


def resolve_snapshot(value: str) -> Path:
    raw = Path(value)
    if raw.parts and raw.parts[0] == "docs":
        return ROOT / raw
    return (IMPORTS / raw).resolve()


def extract_apc(html_path: Path, mpn: str) -> str:
    text = html.unescape(html_path.read_text(encoding="utf-8-sig", errors="strict"))
    product_id = re.search(r'<meta name="product-id" content="([^"]+)"', text)
    if not product_id or normalized(product_id.group(1)) != normalized(mpn):
        raise SystemExit(f"APC product-id mismatch for {html_path.name}: {mpn}")
    match = re.search(r'"image":\["(https://download\.schneider-electric\.com/files\?[^\"]+)"', text)
    if not match:
        raise SystemExit(f"No APC product image in {html_path.name}")
    return match.group(1)


def apc_local_path(url: str) -> Path:
    for doc_ref, filename in APC_LOCAL.items():
        if doc_ref in url:
            return ASSET_DIR / filename
    raise SystemExit(f"Unmapped APC image URL: {url}")


def pdf_page_hits(path: Path, tokens: list[str]) -> dict[str, list[int]]:
    document = pdfium.PdfDocument(path)
    pages = [normalized(document[index].get_textpage().get_text_range()) for index in range(len(document))]
    hits = {
        token: [index + 1 for index, text in enumerate(pages) if normalized(token) in text]
        for token in tokens
    }
    missing = [token for token, page_numbers in hits.items() if not page_numbers]
    if missing:
        raise SystemExit(f"Missing exact PDF tokens in {path.name}: {missing}")
    return hits


def render_pdf_pages(path: Path, pages: list[int], source_key: str) -> dict[int, Path]:
    document = pdfium.PdfDocument(path)
    result: dict[int, Path] = {}
    for page_number in pages:
        output = RENDER_DIR / f"{source_key}-p{page_number:03d}.png"
        image = document[page_number - 1].render(scale=1.35).to_pil().convert("RGB")
        image.save(output, format="PNG", optimize=False)
        result[page_number] = output
    return result


def contact_sheet(source_key: str, candidates: list[tuple[str, Path]]) -> Path:
    width, height = 360, 300
    columns = min(4, max(1, len(candidates)))
    rows = (len(candidates) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, path) in enumerate(candidates):
        with Image.open(path) as source:
            thumb = ImageOps.contain(source.convert("RGB"), (width - 20, height - 52))
        x = (index % columns) * width
        y = (index // columns) * height
        sheet.paste(thumb, (x + (width - thumb.width) // 2, y + 28))
        draw.text((x + 8, y + 8), label, fill="black")
        draw.rectangle((x, y, x + width - 1, y + height - 1), outline="#777777", width=1)
    output = SHEET_DIR / f"{source_key}.png"
    sheet.save(output, format="PNG", optimize=False)
    return output


def main() -> None:
    for path, expected in INPUT_PINS.items():
        verify(path, expected)
    if PROMOTION.exists():
        raise SystemExit(f"Unexpected stale promotion manifest: {PROMOTION.relative_to(ROOT)}")

    payload = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    products = payload.get("products", [])
    actionable = read_csv(ACTIONABLE)
    if len(products) != 44 or len(actionable) != 44:
        raise SystemExit(f"Wave242C scope drift: manifest={len(products)} actionable={len(actionable)}")
    action_by_id = {row["product_external_id"]: row for row in actionable}
    product_by_id = {row["external_id"]: row for row in products}
    if set(action_by_id) != set(product_by_id):
        raise SystemExit("Wave241 manifest/actionable external-ID mismatch")

    prior_review = {row["external_id"]: row for row in read_csv(PRIOR_REVIEW)}
    prior_skip = {row["external_id"]: row for row in read_csv(PRIOR_SKIP)}
    if any(external_id not in prior_skip for external_id in product_by_id):
        raise SystemExit("Every Wave242C row must retain Wave237 no-repeat evidence")
    prior_paths: dict[str, str] = {}
    for external_id in product_by_id:
        names = [name for name in prior_skip[external_id]["review_ledgers"].split("|") if name]
        matched = False
        for name in names:
            path = GENERATED / name
            if not path.exists():
                raise SystemExit(f"Missing prior media ledger: {name}")
            if any(row.get("external_id") == external_id for row in read_csv(path)):
                matched = True
        if not matched:
            raise SystemExit(f"No exact prior media row for {external_id}: {names}")
        prior_paths[external_id] = "|".join(f"docs/audits/generated/{name}" for name in names)
        if external_id in prior_review and prior_review[external_id]["visual_decision"] != "HOLD":
            raise SystemExit("Wave242C must not reopen a prior legacy PASS")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    SHEET_DIR.mkdir(parents=True, exist_ok=True)

    pdf_groups: dict[Path, list[dict[str, str]]] = defaultdict(list)
    apc_rows: list[dict[str, str]] = []
    for external_id in sorted(action_by_id):
        row = action_by_id[external_id]
        snapshot = resolve_snapshot(row["source_snapshot_path"])
        verify(snapshot, row["source_snapshot_sha256"])
        if snapshot.suffix.casefold() == ".pdf":
            pdf_groups[snapshot].append(row)
        elif snapshot.suffix.casefold() == ".html" and row["manufacturer"] == "APC":
            apc_rows.append(row)
        else:
            raise SystemExit(f"Unsupported official snapshot: {snapshot}")

    candidate_rows: list[dict[str, object]] = []
    product_candidate: dict[str, dict[str, str]] = {}
    sheets: list[Path] = []

    for snapshot, rows in sorted(pdf_groups.items(), key=lambda item: item[0].as_posix()):
        source_key = snapshot.stem
        hits = pdf_page_hits(snapshot, [row["mpn"] for row in rows])
        pages = sorted({page for numbers in hits.values() for page in numbers})
        rendered = render_pdf_pages(snapshot, pages, source_key)
        sheet = contact_sheet(source_key, [(f"{snapshot.name} p.{page}", rendered[page]) for page in pages])
        sheets.append(sheet)
        page_models: dict[int, list[str]] = defaultdict(list)
        for mpn, page_numbers in hits.items():
            for page in page_numbers:
                page_models[page].append(mpn)
        for page in pages:
            candidate_rows.append(
                {
                    "candidate_kind": "official_pdf_page_render",
                    "source_snapshot_path": snapshot.relative_to(ROOT).as_posix(),
                    "source_snapshot_sha256": sha256(snapshot),
                    "source_page": page,
                    "models_on_page": "|".join(sorted(page_models[page])),
                    "source_asset_url": "",
                    "local_path": rendered[page].relative_to(ROOT).as_posix(),
                    "local_sha256": sha256(rendered[page]),
                    "contact_sheet_path": sheet.relative_to(ROOT).as_posix(),
                    "contact_sheet_sha256": sha256(sheet),
                }
            )
        for row in rows:
            status, note = PDF_VISUAL[row["manufacturer"]]
            paths = [rendered[page].relative_to(ROOT).as_posix() for page in hits[row["mpn"]]]
            product_candidate[row["product_external_id"]] = {
                "kind": "official_pdf_page_render",
                "url": "",
                "paths": "|".join(paths),
                "sha": "|".join(sha256(rendered[page]) for page in hits[row["mpn"]]),
                "pages": "|".join(str(page) for page in hits[row["mpn"]]),
                "visual_status": status,
                "visual_note": note,
            }

    apc_assets: dict[Path, list[dict[str, str]]] = defaultdict(list)
    for row in apc_rows:
        snapshot = resolve_snapshot(row["source_snapshot_path"])
        url = extract_apc(snapshot, row["mpn"])
        local = apc_local_path(url)
        if not local.exists():
            raise SystemExit(f"Missing audit-only APC raster: {local.relative_to(ROOT)}")
        with Image.open(local) as image:
            if image.format != "JPEG" or image.width < 500 or image.height < 500:
                raise SystemExit(f"Invalid APC raster: {local.relative_to(ROOT)}")
        apc_assets[local].append(row)

    apc_sheet = contact_sheet(
        "apc-official-rasters",
        [(" / ".join(item["mpn"] for item in rows), local) for local, rows in sorted(apc_assets.items())],
    )
    sheets.append(apc_sheet)
    for local, rows in sorted(apc_assets.items()):
        models = sorted(row["mpn"] for row in rows)
        source_url = extract_apc(resolve_snapshot(rows[0]["source_snapshot_path"]), rows[0]["mpn"])
        candidate_rows.append(
            {
                "candidate_kind": "official_html_linked_raster",
                "source_snapshot_path": "|".join(
                    sorted(resolve_snapshot(row["source_snapshot_path"]).relative_to(ROOT).as_posix() for row in rows)
                ),
                "source_snapshot_sha256": "|".join(sorted(row["source_snapshot_sha256"] for row in rows)),
                "source_page": "",
                "models_on_page": "|".join(models),
                "source_asset_url": source_url,
                "local_path": local.relative_to(ROOT).as_posix(),
                "local_sha256": sha256(local),
                "contact_sheet_path": apc_sheet.relative_to(ROOT).as_posix(),
                "contact_sheet_sha256": sha256(apc_sheet),
            }
        )
        shared = len(models) > 1
        for row in rows:
            if shared:
                visual_status = "NOT_EXACT_SHARED_OFFICIAL_RASTER"
                visual_note = f"The same official raster is assigned to multiple product pages: {', '.join(models)}."
            else:
                visual_status = "EXACT_PAGE_ASSOCIATION_WITHOUT_VISIBLE_MPN"
                visual_note = "The pinned official product page uniquely associates this raster with the APC MPN, but the pictured label shows only generic RBC branding rather than the complete MPN."
            product_candidate[row["product_external_id"]] = {
                "kind": "official_html_linked_raster",
                "url": extract_apc(resolve_snapshot(row["source_snapshot_path"]), row["mpn"]),
                "paths": local.relative_to(ROOT).as_posix(),
                "sha": sha256(local),
                "pages": "",
                "visual_status": visual_status,
                "visual_note": visual_note,
            }

    candidate_fields = [
        "candidate_kind", "source_snapshot_path", "source_snapshot_sha256", "source_page",
        "models_on_page", "source_asset_url", "local_path", "local_sha256",
        "contact_sheet_path", "contact_sheet_sha256",
    ]
    write_csv(CANDIDATE_INDEX, candidate_fields, candidate_rows)

    ledger_rows: list[dict[str, object]] = []
    for external_id, row in sorted(action_by_id.items(), key=lambda item: int(item[1]["priority"])):
        candidate = product_candidate[external_id]
        ledger_rows.append(
            {
                "priority": row["priority"],
                "product_external_id": external_id,
                "name": row["name"],
                "manufacturer": row["manufacturer"],
                "mpn": row["mpn"],
                "decision": "HOLD",
                "official_candidate_kind": candidate["kind"],
                "visual_identity_status": candidate["visual_status"],
                "visual_review_note": candidate["visual_note"],
                "candidate_source_asset_url": candidate["url"],
                "candidate_local_paths": candidate["paths"],
                "candidate_sha256": candidate["sha"],
                "candidate_pages": candidate["pages"],
                "source_url": row["source_url"],
                "source_snapshot_path": resolve_snapshot(row["source_snapshot_path"]).relative_to(ROOT).as_posix(),
                "source_snapshot_sha256": row["source_snapshot_sha256"],
                "rights_status": "NO_DOCUMENTED_REUSE_PERMISSION",
                "rights_evidence_path": RIGHTS_POLICY.relative_to(ROOT).as_posix(),
                "rights_evidence_note": "Pinned manufacturer-primary HTML/PDF proves identity but contains no documented grant permitting Microchips to extract, republish, or commercially reuse the image.",
                "prior_legacy_decision": "HOLD",
                "prior_legacy_review_path": prior_paths[external_id],
                "prior_no_repeat_path": PRIOR_SKIP.relative_to(ROOT).as_posix(),
                "promotion_eligible": "false",
                "next_action": "obtain written manufacturer/distributor permission or a new company-owned exact-MPN image, then perform a fresh visual review",
            }
        )
    if len(ledger_rows) != 44 or any(row["decision"] != "HOLD" for row in ledger_rows):
        raise SystemExit("Wave242C fail-closed cardinality drift")
    write_csv(LEDGER, LEDGER_FIELDS, ledger_rows)

    visual_counts = Counter(str(row["visual_identity_status"]) for row in ledger_rows)
    manufacturer_counts = Counter(str(row["manufacturer"]) for row in ledger_rows)
    summary = {
        "schema_version": 1,
        "wave": "wave242c-official-image-audit",
        "checked_at": "2026-07-29",
        "scope": {"wave241_manifest_products": 44, "prior_legacy_hold_rows": 44},
        "result": {
            "pass_count": 0,
            "hold_count": 44,
            "promotion_manifest": None,
            "visual_identity_status_counts": dict(sorted(visual_counts.items())),
            "manufacturer_counts": dict(sorted(manufacturer_counts.items())),
        },
        "candidate_evidence": {
            "candidate_rows": len(candidate_rows),
            "pdf_page_renders": sum(row["candidate_kind"] == "official_pdf_page_render" for row in candidate_rows),
            "unique_html_linked_rasters": sum(row["candidate_kind"] == "official_html_linked_raster" for row in candidate_rows),
            "contact_sheets": [
                {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)} for path in sorted(sheets)
            ],
        },
        "input_pins": {path.relative_to(ROOT).as_posix(): expected for path, expected in INPUT_PINS.items()},
        "outputs": {
            "ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "rows": 44, "sha256": sha256(LEDGER)},
            "candidate_index": {
                "path": CANDIDATE_INDEX.relative_to(ROOT).as_posix(),
                "rows": len(candidate_rows),
                "sha256": sha256(CANDIDATE_INDEX),
            },
        },
        "safety": {"database_calls": 0, "database_mutations": 0, "apply_performed": False},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = f"""# Wave242-C official-source image audit

The 44 products from the Wave241 description manifest were checked only against their already SHA-pinned manufacturer-primary HTML/PDF evidence. Their company-owned legacy images were not reviewed again: 39 have Wave235 `HOLD`, five retain earlier Wave229B/229C HOLD/REJECT evidence, and all 44 are pinned by the Wave237 no-repeat ledger.

## Result

- PASS: **0**; no promotion manifest was created.
- HOLD: **44**.
- Official visual candidates: **{len(candidate_rows)}** ({summary['candidate_evidence']['pdf_page_renders']} rendered PDF pages and {summary['candidate_evidence']['unique_html_linked_rasters']} unique APC rasters).
- Every pinned official source lacks a documented image-reuse grant for Microchips. Manufacturer ownership/public availability is not permission to republish commercially.
- APC RBC17 and RBC40 share the same official raster, so that asset is not exact-model evidence for either product.

The audit-only extracts remain under the ignored `docs/audits/generated/rb-wave242c-official-image-audit/` zone. They are evidence, not publishable media.

## Artifacts

- `{LEDGER.relative_to(ROOT).as_posix()}` — full 44-row decision ledger.
- `{CANDIDATE_INDEX.relative_to(ROOT).as_posix()}` — page/raster hashes and contact-sheet pins.
- `{SUMMARY.relative_to(ROOT).as_posix()}` — deterministic counters and input/output hashes.

No database query, database mutation, media apply, publication action, or commit was performed.
"""
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps(summary["result"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
