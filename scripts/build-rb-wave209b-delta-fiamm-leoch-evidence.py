#!/usr/bin/env python3
"""Build fail-closed Wave209-B evidence for Delta, Fiamm and Leoch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/audits/generated/rb-b2b-next-source-batch-wave208.csv"
DELTA = ROOT / "docs/audits/generated/rb-delta-wave198-official-evidence.csv"
REGISTRY = ROOT / "docs/audits/generated/full-catalog-canonical-registry.csv"
LIVE = ROOT / "docs/audits/generated/wave209b-live-identity-collisions.json"
OUTPUT = ROOT / "docs/audits/generated/wave209b-delta-fiamm-leoch-evidence.csv"
EXCLUSIONS = ROOT / "docs/audits/generated/wave209b-automotive-starter-exclusions.csv"
SUMMARY = ROOT / "docs/audits/generated/wave209b-delta-fiamm-leoch-summary.json"
MANIFEST = ROOT / "docs/imports/rb-verified-oem-identities-wave209b-delta-2026-07-29.json"
DRY_RUN = ROOT / "docs/audits/generated/wave209b-laravel-dry-run.json"
EXPECTED = {"Delta": 80, "Fiamm": 33, "Leoch": 23}

FIELDS = [
    "batch", "product_external_id", "name", "manufacturer_cluster", "model_candidate",
    "partition", "source_tier", "source_publisher", "source_url", "source_assertion",
    "verified_facts", "snapshot_path", "snapshot_sha256", "conflict_reason",
    "duplicate_cluster_ids", "duplicate_decision", "safe_to_apply",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", unicodedata.normalize("NFKC", value).upper())


def claimed_number(name: str, unit: str) -> str:
    match = re.search(rf"([0-9]+(?:[.,][0-9]+)?)\s*{unit}", name, re.I)
    return match.group(1).replace(",", ".") if match else ""


def model_from_name(name: str, maker: str) -> str:
    tail = re.split(rf"\b{re.escape(maker)}\b", name, maxsplit=1, flags=re.I)
    if len(tail) != 2:
        return ""
    return re.split(r"\s+(?:для\b|\()", tail[1], maxsplit=1, flags=re.I)[0].strip()


def prior_wave206_ids() -> tuple[set[str], list[str]]:
    found: set[str] = set()
    files: list[str] = []
    for path in sorted((ROOT / "docs/audits/generated").glob("*wave206*evidence*.csv")):
        files.append(path.relative_to(ROOT).as_posix())
        for row in rows(path):
            value = row.get("product_external_id") or row.get("external_id") or ""
            if value:
                found.add(value)
    return found, files


def is_automotive(row: dict[str, str]) -> bool:
    haystack = " ".join([row.get("name", ""), row.get("category_key", ""), row.get("series_bucket", "")])
    return bool(re.search(r"автомоб|стартер|мото|starting|starter|cranking", haystack, re.I))


def local_delta_snapshot(source_path: str) -> Path:
    # Older generated evidence stores an absolute path; bind it to this checkout.
    return ROOT / "docs/audits/sources/delta-wave198" / Path(source_path).name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provisional", action="store_true")
    args = parser.parse_args()

    prior_ids, prior_files = prior_wave206_ids()
    scoped = [row for row in rows(INPUT) if row["manufacturer_cluster"] in EXPECTED]
    overlap = sorted({row["product_external_id"] for row in scoped} & prior_ids)
    scoped = [row for row in scoped if row["product_external_id"] not in prior_ids]
    counts = Counter(row["manufacturer_cluster"] for row in scoped)
    if counts != Counter(EXPECTED) or len(scoped) != 136 or overlap:
        raise SystemExit(f"Wave209-B scope drift: rows={len(scoped)}, counts={counts}, overlap={overlap}")

    excluded = [row for row in scoped if is_automotive(row)]
    candidates = [row for row in scoped if not is_automotive(row)]
    with EXCLUSIONS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["product_external_id", "name", "reason"], lineterminator="\n")
        writer.writeheader()
        writer.writerows({"product_external_id": row["product_external_id"], "name": row["name"], "reason": "automotive_or_starter_scope"} for row in excluded)

    delta_by_id = {row["external_id"]: row for row in rows(DELTA)}
    live = json.loads(LIVE.read_text(encoding="utf-8-sig"))
    live_collisions = defaultdict(list)
    for item in live["collisions"]:
        live_collisions[item["candidate_external_id"]].append(item["conflicting_external_id"])

    registry = rows(REGISTRY)
    registry_groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for candidate in candidates:
        maker = candidate["manufacturer_cluster"]
        model = model_from_name(candidate["name"], maker)
        if not model:
            continue
        token = norm(model)
        for item in registry:
            if re.search(rf"\b{re.escape(maker)}\b", item["name"], re.I) and token in norm(item["name"]):
                registry_groups[(maker, token)].add(item["registry_id"])

    output: list[dict[str, str]] = []
    preliminary_exact = 0
    for candidate in candidates:
        external_id = candidate["product_external_id"]
        maker = candidate["manufacturer_cluster"]
        model = model_from_name(candidate["name"], maker)
        partition = "no_evidence"
        source_tier = "none"
        publisher = url = assertion = facts = snapshot_rel = snapshot_hash = ""
        reason = "No pinned first-party page or catalogue proves the exact offered model."
        exact = False

        evidence = delta_by_id.get(external_id) if maker == "Delta" else None
        if evidence:
            snapshot = local_delta_snapshot(evidence["source_snapshot_path"])
            if not snapshot.is_file() or sha256(snapshot) != evidence["source_sha256"]:
                raise SystemExit(f"Delta pinned snapshot mismatch: {external_id}")
            source_tier = "manufacturer_primary"
            publisher = evidence["publisher"]
            url = evidence["source_url"]
            assertion = evidence["evidence_kind"]
            snapshot_rel = snapshot.relative_to(ROOT).as_posix()
            snapshot_hash = evidence["source_sha256"]
            model = evidence["model"]
            claimed_v = claimed_number(candidate["name"], "V")
            claimed_ah = claimed_number(candidate["name"], "Ah")
            model_is_exact = norm(evidence["model"]) in norm(candidate["name"])
            voltage_agrees = not claimed_v or claimed_v == evidence["voltage_v"]
            if model_is_exact and voltage_agrees and claimed_ah == evidence["capacity_ah"]:
                partition = "exact"
                exact = True
                preliminary_exact += 1
                facts = f"manufacturer=DELTA|mpn={model}|voltage_v={evidence['voltage_v']}|capacity_ah={evidence['capacity_ah']}"
                reason = ""
            else:
                partition = "conflict"
                reason = f"Official page states {evidence['voltage_v']}V/{evidence['capacity_ah']}Ah; legacy title claims {claimed_v or '?'}V/{claimed_ah or '?'}Ah."
        elif maker == "Fiamm":
            reason = "Pinned fiamm.ru pages are distributor evidence, not manufacturer-primary identity evidence; fail-closed hold."
        elif maker == "Leoch":
            reason = "No pinned Leoch manufacturer PDF/page for the exact FT/DJW/DJM model is present in the evidence store."

        token = norm(model)
        peers = sorted(item for item in registry_groups.get((maker, token), set()) if item != external_id)
        peers = sorted(set(peers + live_collisions.get(external_id, [])))
        safe = exact and not peers
        decision = "hold_live_or_registry_collision" if peers else "unique_exact_identity" if exact else "not_applicable"
        output.append({
            "batch": "wave209b_delta_fiamm_leoch", "product_external_id": external_id,
            "name": candidate["name"], "manufacturer_cluster": maker, "model_candidate": model,
            "partition": partition, "source_tier": source_tier, "source_publisher": publisher,
            "source_url": url, "source_assertion": assertion, "verified_facts": facts,
            "snapshot_path": snapshot_rel, "snapshot_sha256": snapshot_hash,
            "conflict_reason": reason, "duplicate_cluster_ids": "|".join(peers),
            "duplicate_decision": decision, "safe_to_apply": "true" if safe else "false",
        })

    if live.get("candidate_rows_checked") != preliminary_exact:
        raise SystemExit(f"Live collision guard coverage mismatch: expected {preliminary_exact}, got {live.get('candidate_rows_checked')}")

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader(); writer.writerows(output)

    manifest_rows = []
    for row in output:
        if row["safe_to_apply"] != "true":
            continue
        manifest_rows.append({
            "external_id": row["product_external_id"], "current_name": row["name"],
            "manufacturer": "DELTA", "mpn": row["model_candidate"], "source_url": row["source_url"],
            "source_kind": "official_manufacturer_product_page", "source_publisher": row["source_publisher"],
            "checked_at": "2026-07-29", "product_type": "industrial stationary battery",
            "source_snapshot_path": (Path("../audits") / Path(row["snapshot_path"]).relative_to("docs/audits")).as_posix(),
            "source_snapshot_sha256": row["snapshot_sha256"],
        })
    MANIFEST.write_text(json.dumps({"schema_version": 1, "site_key": "microchips-by", "products": manifest_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    verified = False
    if DRY_RUN.is_file():
        dry = json.loads(DRY_RUN.read_text(encoding="utf-8-sig"))
        verified = dry.get("exit_code") == 0 and dry.get("manifest_sha256") == sha256(MANIFEST) and dry.get("records") == len(manifest_rows) and dry.get("mode") == "dry_run" and dry.get("commercial_fields_changed") == 0 and dry.get("publication_fields_changed") == 0
    if not args.provisional and not verified:
        raise SystemExit("Wave209-B manifest lacks matching successful Laravel dry-run evidence")

    parts = Counter(row["partition"] for row in output)
    summary = {
        "schema_version": 1, "batch": "wave209b_delta_fiamm_leoch", "created_at": "2026-07-29",
        "input": {"path": INPUT.relative_to(ROOT).as_posix(), "sha256": sha256(INPUT), "rows": len(scoped), "manufacturer_counts": dict(sorted(counts.items()))},
        "wave206_exclusion": {"files": prior_files, "overlap_rows": len(overlap), "overlap_ids": overlap},
        "scope_exclusion": {"automotive_or_starter_rows": len(excluded), "artifact": EXCLUSIONS.relative_to(ROOT).as_posix()},
        "sources": {"delta_evidence": DELTA.relative_to(ROOT).as_posix(), "delta_evidence_sha256": sha256(DELTA), "fiamm_policy": "official_distributor_not_promotable", "leoch_policy": "no_pinned_primary_snapshot_fail_closed"},
        "canonical_registry": {"path": REGISTRY.relative_to(ROOT).as_posix(), "sha256": sha256(REGISTRY), "rows": len(registry)},
        "live_collision_guard": {"path": LIVE.relative_to(ROOT).as_posix(), "sha256": sha256(LIVE), "candidate_rows_checked": live["candidate_rows_checked"], "collision_rows": len(live["collisions"])},
        "output": {"path": OUTPUT.relative_to(ROOT).as_posix(), "sha256": sha256(OUTPUT), "rows": len(output)},
        "partition_counts": dict(sorted(parts.items())),
        "safe_to_apply": {"rows": len(manifest_rows), "external_ids": [row["external_id"] for row in manifest_rows]},
        "manifest": {"path": MANIFEST.relative_to(ROOT).as_posix(), "sha256": sha256(MANIFEST), "rows": len(manifest_rows), "laravel_dry_run_verified": verified},
        "policy": {"manufacturer_primary_only_for_manifest": True, "full_registry_and_live_collision_guards": True, "automotive_and_starter_excluded": True, "database_mutations": 0},
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(output), "partitions": dict(parts), "safe": len(manifest_rows), "dry_run_verified": verified}, ensure_ascii=False))


if __name__ == "__main__":
    main()
