#!/usr/bin/env python3
"""Build catalog from PrtOpenSearch .osq templates."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT.parent / "PrtOpenSearch" / "settings"
OUT = ROOT / "catalog" / "generated.json"


def parse_aliases(osq_text: str) -> dict:
    aliases = {}
    for match in re.finditer(r'"([^"]+)"\s*:\s*\{[^}]*"index"\s*:\s*"([^"]+)"', osq_text):
        aliases[match.group(1)] = {"indexPattern": match.group(2)}
    return aliases


def main() -> int:
    aliases = {}
    for path in SETTINGS.rglob("*.osq"):
        text = path.read_text(encoding="utf-8")
        aliases.update(parse_aliases(text))

    payload = {
        "version": 1,
        "aliases": aliases,
        "fields": {
            "v2": {
                "content": "Indexed chunk text",
                "embedding": "kNN vector",
                "document_metadata.id": "Document id",
                "chunk_metadata.contentKind": "narrative | structured_*",
            },
            "v1": {
                "chunk_content": "Chunk text v1.1",
                "document_id": "Document id v1.1",
            },
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
