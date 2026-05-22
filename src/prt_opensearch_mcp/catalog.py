"""Field catalog for v1.1 and v2 chunk indices."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


V2_FIELDS = {
    "content": "Indexed chunk text (with optional context)",
    "content_original": "Original chunk text",
    "embedding": "kNN vector for semantic search",
    "document_metadata.id": "Document id (v2)",
    "document_metadata.title": "Document title",
    "chunk_metadata.id": "Chunk id",
    "chunk_metadata.idx": "Chunk index order",
    "chunk_metadata.contentKind": "narrative | structured_summary | structured_child",
    "publisher_metadata.name": "Publisher name",
    "content_metadata.page_content_profile": "hybrid | narrative_only | structured_only",
    "include": "Boolean soft-delete flag",
}

V1_FIELDS = {
    "chunk_content": "Chunk text (v1.1)",
    "chunk_embedding": "kNN vector 1024-dim (v1.1)",
    "document_id": "Document id (v1.1)",
    "publisher_id": "Publisher id",
}


def load_catalog(path: str | None) -> Dict[str, Any]:
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"aliases": {}, "fields": {"v2": V2_FIELDS, "v1": V1_FIELDS}}


def search_catalog(catalog: Dict[str, Any], query: str) -> List[Dict[str, str]]:
    q = query.lower().strip()
    hits: List[Dict[str, str]] = []
    for version, fields in (catalog.get("fields") or {"v2": V2_FIELDS, "v1": V1_FIELDS}).items():
        for name, desc in fields.items():
            if q in name.lower() or q in desc.lower():
                hits.append({"version": version, "field": name, "description": desc})
    for alias, meta in (catalog.get("aliases") or {}).items():
        if q in alias.lower() or q in str(meta).lower():
            hits.append({"version": "alias", "field": alias, "description": str(meta)})
    return hits[:30]


def catalog_markdown(catalog: Dict[str, Any]) -> str:
    lines = ["# ProRata OpenSearch catalog", ""]
    for version, fields in (catalog.get("fields") or {"v2": V2_FIELDS}).items():
        lines.append(f"## Schema {version}")
        for name, desc in sorted(fields.items()):
            lines.append(f"- `{name}`: {desc}")
        lines.append("")
    return "\n".join(lines)
