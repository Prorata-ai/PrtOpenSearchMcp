"""Guard OpenSearch search DSL (read-only)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

_FORBIDDEN_KEYS = frozenset(
    {
        "script",
        "delete_by_query",
        "update_by_query",
        "reindex",
        "bulk",
        "scroll",
    }
)

_FORBIDDEN_QUERY_KEYS = frozenset({"delete", "update", "index"})


class QueryRejectedError(ValueError):
    pass


def validate_search_body(body: Dict[str, Any], *, max_size: int, hard_max: int) -> Dict[str, Any]:
    if not isinstance(body, dict):
        raise QueryRejectedError("Search body must be a JSON object")

    for key in body:
        if key.lower() in _FORBIDDEN_KEYS:
            raise QueryRejectedError(f"Forbidden key: {key}")

    query = body.get("query")
    if isinstance(query, dict):
        for key in query:
            if key.lower() in _FORBIDDEN_QUERY_KEYS:
                raise QueryRejectedError(f"Forbidden query clause: {key}")

    capped = min(max_size, hard_max)
    out = dict(body)
    size = out.get("size", capped)
    if not isinstance(size, int) or size < 0:
        size = capped
    out["size"] = min(size, capped)
    if "from" in out and isinstance(out["from"], int):
        out["from"] = min(out["from"], 1000)
    return out


def validate_get_path(path: str) -> None:
    if not re.match(r"^[_a-zA-Z0-9\-./%]+$", path):
        raise QueryRejectedError("Invalid path")
    lowered = path.lower()
    for bad in ("_bulk", "_delete", "_update", "_cluster/settings"):
        if bad in lowered:
            raise QueryRejectedError(f"Forbidden path segment: {bad}")


def parse_search_json(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise QueryRejectedError(f"Invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise QueryRejectedError("Search body must be an object")
    return data
