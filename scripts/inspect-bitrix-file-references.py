#!/usr/bin/env python3
"""Read named Bitrix b_file records from a gzipped MySQL dump without mutation.

The catalogue migration must prove the legacy file reference before a copied
asset can become a candidate for visual review.  This narrow tool validates
the b_file column order, streams the dump and prints only the requested rows.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path


REQUIRED_COLUMNS = {
    "ID": 0,
    "CONTENT_TYPE": 6,
    "SUBDIR": 7,
    "FILE_NAME": 8,
    "ORIGINAL_NAME": 9,
}


def mysql_unquote(token: str) -> str | None:
    token = token.strip()
    if token == "NULL":
        return None
    if len(token) < 2 or token[0] != "'" or token[-1] != "'":
        return token
    raw = token[1:-1]
    result: list[str] = []
    index = 0
    escapes = {"0": "\0", "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}
    while index < len(raw):
        char = raw[index]
        if char != "\\" or index == len(raw) - 1:
            result.append(char)
            index += 1
            continue
        index += 1
        result.append(escapes.get(raw[index], raw[index]))
        index += 1
    return "".join(result)


def tuples(statement: str) -> list[str]:
    found: list[str] = []
    depth = 0
    begin = -1
    quoted = False
    escaped = False
    for index, char in enumerate(statement):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                quoted = False
            continue
        if char == "'":
            quoted = True
        elif char == "(":
            if depth == 0:
                begin = index
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and begin >= 0:
                found.append(statement[begin : index + 1])
    if quoted or depth != 0:
        raise ValueError("Unclosed tuple or string in b_file INSERT")
    return found


def values(tuple_text: str) -> list[str | None]:
    body = tuple_text[1:-1]
    tokens: list[str] = []
    current: list[str] = []
    quoted = False
    escaped = False
    for char in body:
        if quoted:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "'":
                quoted = False
        elif char == "'":
            quoted = True
            current.append(char)
        elif char == ",":
            tokens.append("".join(current))
            current = []
        else:
            current.append(char)
    if quoted:
        raise ValueError("Unclosed string in b_file tuple")
    tokens.append("".join(current))
    return [mysql_unquote(token) for token in tokens]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", type=Path, required=True)
    ids_group = parser.add_mutually_exclusive_group(required=True)
    ids_group.add_argument("--ids", nargs="+", help="Bitrix b_file IDs")
    ids_group.add_argument("--ids-file", type=Path, help="UTF-8 file with one Bitrix b_file ID per line")
    parser.add_argument("--output", type=Path, help="Optional JSON output path; stdout remains the default")
    args = parser.parse_args()
    supplied_ids = args.ids or [
        line.strip()
        for line in args.ids_file.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    wanted = set(supplied_ids)
    if not wanted or any(not file_id.isdigit() for file_id in wanted):
        raise ValueError("Requested b_file IDs must be non-empty decimal values")
    schema: list[str] = []
    in_schema = False
    capturing = False
    chunks: list[str] = []
    rows: list[dict[str, str | None]] = []

    with gzip.open(args.dump, "rt", encoding="utf-8", errors="strict") as stream:
        for line in stream:
            if not in_schema and re.match(r"^CREATE TABLE `b_file` \(", line):
                in_schema = True
                continue
            if in_schema:
                if re.match(r"^\) ENGINE=", line):
                    in_schema = False
                    for name, index in REQUIRED_COLUMNS.items():
                        if len(schema) <= index or schema[index] != name:
                            raise ValueError(f"b_file schema drift at {index}: expected {name!r}")
                    continue
                match = re.match(r"^\s*`([^`]+)`", line)
                if match:
                    schema.append(match.group(1))
                continue
            if not capturing and line.startswith("INSERT INTO `b_file` VALUES"):
                capturing = True
                chunks.append(line.split("VALUES", 1)[1])
            elif capturing:
                chunks.append(line)
            else:
                continue
            if capturing and line.rstrip().endswith(";"):
                statement = "".join(chunks).rstrip().removesuffix(";")
                for item in tuples(statement):
                    row = values(item)
                    if row[0] not in wanted:
                        continue
                    subdir, file_name = row[7], row[8]
                    rows.append(
                        {
                            "file_id": row[0],
                            "content_type": row[6],
                            "subdir": subdir,
                            "file_name": file_name,
                            "original_name": row[9],
                            "legacy_upload_path": f"upload/{subdir}/{file_name}" if subdir and file_name else None,
                        }
                    )
                capturing = False
                chunks = []
                if {str(row["file_id"]) for row in rows} == wanted:
                    break
    missing = sorted(wanted - {str(row["file_id"]) for row in rows})
    if missing:
        raise ValueError(f"Requested b_file IDs not found: {', '.join(missing)}")
    rendered = json.dumps(sorted(rows, key=lambda row: int(str(row["file_id"]))), ensure_ascii=False, indent=2) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
