"""MCP server for OpenSearch."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from .catalog import catalog_markdown, load_catalog, search_catalog
from .config import load_settings
from .connections import OpenSearchManager
from .query_guard import QueryRejectedError, parse_search_json

_os: Optional[OpenSearchManager] = None
_catalog: Dict[str, Any] = {}


def _get_os() -> OpenSearchManager:
    if _os is None:
        raise RuntimeError("OpenSearch manager not initialized")
    return _os


@asynccontextmanager
async def server_lifespan(_app: Server) -> AsyncIterator[None]:
    global _os, _catalog
    settings = load_settings()
    _catalog = load_catalog(settings.catalog_path)
    _os = OpenSearchManager(settings)
    await _os.open()
    try:
        yield
    finally:
        await _os.close()
        _os = None


def create_server() -> Server:
    return Server("prt-opensearch", lifespan=server_lifespan)


server = create_server()


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(name="list_connections", description="OpenSearch connection profiles.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="ping_cluster", description="Cluster info and health.", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}}}),
        Tool(name="list_aliases", description="List index aliases.", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}}}),
        Tool(name="list_indices", description="List indices (cat API).", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}, "pattern": {"type": "string", "default": "*"}}}),
        Tool(name="get_mapping", description="Index mapping for alias or index name.", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}, "target": {"type": "string"}}}),
        Tool(name="get_chunk_by_id", description="Get document by chunk _id.", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}, "alias": {"type": "string"}, "doc_id": {"type": "string"}}, "required": ["doc_id"]}),
        Tool(name="list_chunks_for_document", description="All chunks for a document_id (v1 + v2 fields).", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}, "alias": {"type": "string"}, "document_id": {"type": "string"}, "max_hits": {"type": "integer"}}, "required": ["document_id"]}),
        Tool(name="count_chunks", description="Count chunks for optional document_id.", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}, "alias": {"type": "string"}, "document_id": {"type": "string"}}}),
        Tool(name="search_fulltext", description="BM25 search on chunk content fields.", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}, "alias": {"type": "string"}, "query": {"type": "string"}, "publisher_id": {"type": "string"}, "max_hits": {"type": "integer"}}, "required": ["query"]}),
        Tool(name="execute_search_dsl", description="Run guarded search JSON against an alias.", inputSchema={"type": "object", "properties": {"connection": {"type": "string"}, "alias": {"type": "string"}, "body": {"type": "object"}, "max_hits": {"type": "integer"}}, "required": ["body"]}),
        Tool(name="search_catalog", description="Search field glossary.", inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
    ]


def _text(payload: Any) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    os_mgr = _get_os()
    args = arguments or {}
    try:
        if name == "list_connections":
            return _text(os_mgr.list_connections())
        if name == "ping_cluster":
            return _text(await os_mgr.ping_cluster(args.get("connection")))
        if name == "list_aliases":
            return _text(await os_mgr.list_aliases(args.get("connection")))
        if name == "list_indices":
            return _text(await os_mgr.list_indices(args.get("connection"), args.get("pattern", "*")))
        if name == "get_mapping":
            return _text(await os_mgr.get_mapping(args.get("connection"), args.get("target")))
        if name == "get_chunk_by_id":
            return _text(await os_mgr.get_document(args.get("connection"), args.get("alias"), args.get("doc_id", "")))
        if name == "list_chunks_for_document":
            return _text(
                await os_mgr.list_chunks_for_document(
                    args.get("connection"),
                    args.get("alias"),
                    args.get("document_id", ""),
                    args.get("max_hits"),
                )
            )
        if name == "count_chunks":
            return _text(
                await os_mgr.count_chunks(
                    args.get("connection"), args.get("alias"), args.get("document_id")
                )
            )
        if name == "search_fulltext":
            return _text(
                await os_mgr.search_fulltext(
                    args.get("connection"),
                    args.get("alias"),
                    args.get("query", ""),
                    args.get("publisher_id"),
                    args.get("max_hits"),
                )
            )
        if name == "execute_search_dsl":
            body = args.get("body")
            if isinstance(body, str):
                body = parse_search_json(body)
            return _text(
                await os_mgr.search(
                    args.get("connection"), args.get("alias"), body, args.get("max_hits")
                )
            )
        if name == "search_catalog":
            return _text({"query": args.get("query"), "hits": search_catalog(_catalog, args.get("query", ""))})
        raise ValueError(f"Unknown tool: {name}")
    except QueryRejectedError as e:
        return _text({"error": str(e), "type": "QueryRejectedError"})
    except Exception as e:
        return _text({"error": str(e), "type": type(e).__name__})


@server.list_resources()
async def list_resources() -> List[Resource]:
    return [
        Resource(uri="prt-os://catalog", name="OpenSearch catalog", description="Field glossary", mimeType="text/markdown"),
        Resource(uri="prt-os://domain/chunks", name="Chunk index", description="v2 chunk document shape", mimeType="text/markdown"),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "prt-os://catalog":
        return catalog_markdown(_catalog)
    if uri == "prt-os://domain/chunks":
        return (
            "# Chunk index (v2)\n\n"
            "- `content` / `content_original` — searchable text\n"
            "- `embedding` — kNN vector\n"
            "- `document_metadata.id` — document id\n"
            "- `chunk_metadata.contentKind` — narrative vs structured\n"
            "- Default alias: `documents_search_alias_v2`\n"
        )
    raise ValueError(f"Unknown resource: {uri}")


async def readiness_check() -> str | None:
    try:
        await _get_os().ping_cluster()
        return None
    except Exception as exc:
        return str(exc)
