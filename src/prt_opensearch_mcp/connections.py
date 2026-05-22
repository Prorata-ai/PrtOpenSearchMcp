"""OpenSearch async client wrapper."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from opensearchpy import AsyncOpenSearch

from .config import OpenSearchProfile, Settings
from .query_guard import QueryRejectedError, validate_get_path, validate_search_body


class OpenSearchManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: Dict[str, AsyncOpenSearch] = {}

    async def open(self) -> None:
        for name, profile in self._settings.profiles.items():
            auth = None
            if profile.username and profile.password:
                auth = (profile.username, profile.password)
            self._clients[name] = AsyncOpenSearch(
                hosts=profile.hosts,
                http_auth=auth,
                use_ssl=profile.use_ssl,
                verify_certs=profile.verify_certs,
                ssl_show_warn=False,
            )

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()

    def _resolve(self, connection: Optional[str]) -> tuple[str, OpenSearchProfile]:
        name = connection or self._settings.default_connection
        if name not in self._clients:
            raise ValueError(f"Unknown connection {name!r}. Available: {list(self._clients)}")
        return name, self._settings.profiles[name]

    def list_connections(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "hosts": profile.hosts,
                "defaultAlias": profile.default_alias,
                "hasIndexingSearchApi": bool(profile.indexing_search_url),
            }
            for name, profile in self._settings.profiles.items()
        ]

    async def ping_cluster(self, connection: Optional[str] = None) -> Dict[str, Any]:
        name, profile = self._resolve(connection)
        client = self._clients[name]
        info = await client.info()
        health = await client.cluster.health()
        return {
            "clusterName": info.get("cluster_name"),
            "version": info.get("version", {}).get("number"),
            "status": health.get("status"),
            "alias": profile.default_alias,
        }

    async def list_aliases(self, connection: Optional[str] = None) -> List[Dict[str, Any]]:
        name, _ = self._resolve(connection)
        client = self._clients[name]
        raw = await client.indices.get_alias(index="*")
        out = []
        for index_name, data in raw.items():
            for alias_name in (data.get("aliases") or {}):
                out.append({"index": index_name, "alias": alias_name})
        return sorted(out, key=lambda x: (x["alias"], x["index"]))

    async def list_indices(
        self, connection: Optional[str] = None, pattern: str = "*"
    ) -> List[Dict[str, Any]]:
        name, _ = self._resolve(connection)
        client = self._clients[name]
        indices = await client.cat.indices(index=pattern, format="json", h="index,docs.count,store.size")
        return indices if isinstance(indices, list) else []

    async def get_mapping(
        self,
        connection: Optional[str] = None,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        name, profile = self._resolve(connection)
        client = self._clients[name]
        index = target or profile.default_alias
        return await client.indices.get_mapping(index=index)

    async def search(
        self,
        connection: Optional[str] = None,
        alias: Optional[str] = None,
        body: Optional[Dict[str, Any]] = None,
        max_hits: Optional[int] = None,
    ) -> Dict[str, Any]:
        name, profile = self._resolve(connection)
        client = self._clients[name]
        index = alias or profile.default_alias
        guarded = validate_search_body(
            body or {"query": {"match_all": {}}},
            max_size=max_hits or self._settings.max_hits,
            hard_max=self._settings.hard_max_hits,
        )
        resp = await client.search(index=index, body=guarded)
        hits = resp.get("hits", {})
        return {
            "took": resp.get("took"),
            "total": hits.get("total"),
            "hits": [_shrink_hit(h) for h in hits.get("hits", [])],
            "index": index,
        }

    async def get_document(
        self,
        connection: Optional[str] = None,
        alias: Optional[str] = None,
        doc_id: str = "",
    ) -> Dict[str, Any]:
        if not doc_id:
            raise ValueError("doc_id is required")
        name, profile = self._resolve(connection)
        client = self._clients[name]
        index = alias or profile.default_alias
        path = f"{index}/_doc/{doc_id}"
        validate_get_path(path)
        resp = await client.get(index=index, id=doc_id)
        return {"found": resp.get("found", True), "id": doc_id, "source": resp.get("_source")}

    async def list_chunks_for_document(
        self,
        connection: Optional[str] = None,
        alias: Optional[str] = None,
        document_id: str = "",
        max_hits: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not document_id:
            raise ValueError("document_id is required")
        body = {
            "query": {
                "bool": {
                    "should": [
                        {"term": {"document_metadata.id": document_id}},
                        {"term": {"document_id": document_id}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "sort": [{"chunk_metadata.idx": "asc"}, {"chunk_index": "asc"}],
        }
        return await self.search(connection, alias, body, max_hits=max_hits)

    async def count_chunks(
        self,
        connection: Optional[str] = None,
        alias: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        name, profile = self._resolve(connection)
        client = self._clients[name]
        index = alias or profile.default_alias
        if document_id:
            body = {
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"document_metadata.id": document_id}},
                            {"term": {"document_id": document_id}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            }
        else:
            body = {"query": {"match_all": {}}}
        guarded = validate_search_body(body, max_size=0, hard_max=0)
        guarded["size"] = 0
        resp = await client.search(index=index, body=guarded)
        total = resp.get("hits", {}).get("total")
        if isinstance(total, dict):
            total = total.get("value")
        return {"index": index, "documentId": document_id, "count": total}

    async def search_fulltext(
        self,
        connection: Optional[str] = None,
        alias: Optional[str] = None,
        query_text: str = "",
        publisher_id: Optional[str] = None,
        max_hits: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not query_text.strip():
            raise ValueError("query is required")
        must: List[Dict[str, Any]] = [
            {
                "multi_match": {
                    "query": query_text,
                    "fields": ["content^2", "content_original^2", "chunk_content"],
                }
            }
        ]
        if publisher_id:
            must.append(
                {
                    "bool": {
                        "should": [
                            {"term": {"publisher_metadata.id": publisher_id}},
                            {"term": {"publisher_id": publisher_id}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )
        body = {"query": {"bool": {"must": must, "filter": [{"term": {"include": True}}]}}}
        return await self.search(connection, alias, body, max_hits=max_hits)


def _shrink_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    source = hit.get("_source") or {}
    content = source.get("content") or source.get("chunk_content") or ""
    if isinstance(content, str) and len(content) > 500:
        content = content[:500] + "..."
    return {
        "id": hit.get("_id"),
        "index": hit.get("_index"),
        "score": hit.get("_score"),
        "contentPreview": content,
        "documentId": (source.get("document_metadata") or {}).get("id") or source.get("document_id"),
        "chunkMetadata": source.get("chunk_metadata"),
    }
