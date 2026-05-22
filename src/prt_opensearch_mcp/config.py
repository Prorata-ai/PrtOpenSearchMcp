"""OpenSearch MCP configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class OpenSearchProfile:
    name: str
    hosts: List[str]
    default_alias: str
    username: Optional[str] = None
    password: Optional[str] = None
    use_ssl: bool = True
    verify_certs: bool = True
    indexing_search_url: Optional[str] = None


@dataclass(frozen=True)
class Settings:
    profiles: Dict[str, OpenSearchProfile]
    default_connection: str
    default_alias: str
    max_hits: int
    hard_max_hits: int
    catalog_path: Optional[str]


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


def load_settings() -> Settings:
    names = [n.strip() for n in os.getenv("PRT_OS_MCP_CONNECTIONS", "local").split(",") if n.strip()]
    profiles: Dict[str, OpenSearchProfile] = {}

    for name in names:
        prefix = f"PRT_OS_MCP_{name.upper()}"
        url = os.getenv(f"{prefix}_URL", os.getenv(f"{prefix}_HOSTS", "")).strip()
        if not url:
            raise ValueError(f"Missing {prefix}_URL or {prefix}_HOSTS")
        hosts = [h.strip() for h in url.split(",") if h.strip()]
        alias = os.getenv(f"{prefix}_DEFAULT_ALIAS", os.getenv("PRT_OS_MCP_DEFAULT_ALIAS", "documents_search_alias_v2"))
        verify = os.getenv(f"{prefix}_VERIFY_SSL", "true").lower() in ("1", "true", "yes")
        use_ssl = os.getenv(f"{prefix}_USE_SSL", "true").lower() in ("1", "true", "yes")
        profiles[name] = OpenSearchProfile(
            name=name,
            hosts=hosts,
            default_alias=alias.strip(),
            username=os.getenv(f"{prefix}_USER") or None,
            password=os.getenv(f"{prefix}_PASSWORD") or None,
            use_ssl=use_ssl,
            verify_certs=verify,
            indexing_search_url=os.getenv(f"{prefix}_INDEXING_SEARCH_URL") or os.getenv("PRT_OS_MCP_INDEXING_SEARCH_URL"),
        )

    default = os.getenv("PRT_OS_MCP_DEFAULT_CONNECTION", names[0]).strip()
    if default not in profiles:
        raise ValueError(f"PRT_OS_MCP_DEFAULT_CONNECTION={default!r} not in profiles")

    catalog = os.getenv("PRT_OS_MCP_CATALOG_PATH", "").strip() or None
    if catalog is None:
        repo = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "catalog",
            "generated.json",
        )
        if os.path.isfile(repo):
            catalog = repo

    return Settings(
        profiles=profiles,
        default_connection=default,
        default_alias=os.getenv("PRT_OS_MCP_DEFAULT_ALIAS", "documents_search_alias_v2"),
        max_hits=_env_int("PRT_OS_MCP_MAX_HITS", 50),
        hard_max_hits=_env_int("PRT_OS_MCP_HARD_MAX_HITS", 200),
        catalog_path=catalog,
    )
