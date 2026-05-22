# PrtOpenSearch MCP Server

MCP server for **ProRata OpenSearch** chunk indices (`documents_search_alias_v2`). Supports **stdio** (Cursor) and **HTTP** (cloud).

## Prerequisites

1. OpenSearch running (e.g. `PrtIndexingDomain` → `docker-compose up -d indexing-opensearch` on port 9200).
2. Python 3.12+.

## Install

```bash
cd ProRata
pip install -e ./PrtMcpCommon -e ./PrtOpenSearchMcp
python PrtOpenSearchMcp/scripts/build_catalog.py
```

## Run locally (stdio)

```bash
export PRT_OS_MCP_LOCAL_URL=https://localhost:9200
export PRT_OS_MCP_LOCAL_VERIFY_SSL=false
export PRT_OS_MCP_LOCAL_USER=admin
export PRT_OS_MCP_LOCAL_PASSWORD="${OPENSEARCH_INITIAL_ADMIN_PASSWORD}"
python -m prt_opensearch_mcp --transport stdio
```

## Run cloud-style (HTTP)

```bash
export PRT_OS_MCP_LOCAL_URL=https://localhost:9200
export PRT_OS_MCP_LOCAL_VERIFY_SSL=false
export PRT_MCP_API_KEY=dev-secret
export PRT_MCP_TRANSPORT=http
export PRT_MCP_PORT=8081
python -m prt_opensearch_mcp --transport http
```

- MCP: `http://localhost:8081/mcp` with header `Authorization: Bearer dev-secret`
- Health: `GET /healthz`, `GET /readyz`

## Cursor

See [mcp.json.example](mcp.json.example) for stdio and remote HTTP entries.

## Tools

| Tool | Description |
|------|-------------|
| `list_connections` | Profiles and default alias |
| `ping_cluster` | Cluster health |
| `list_aliases` / `list_indices` | Index discovery |
| `get_mapping` | Mapping for alias |
| `get_chunk_by_id` | `_doc` by chunk id |
| `list_chunks_for_document` | Chunks for `document_id` |
| `count_chunks` | Chunk count |
| `search_fulltext` | BM25 on content fields |
| `execute_search_dsl` | Guarded raw search JSON |
| `search_catalog` | Field glossary |
