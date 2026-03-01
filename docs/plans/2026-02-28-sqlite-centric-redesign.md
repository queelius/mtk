# mtk v0.3.0: SQLite-Centric Redesign

**Date:** 2026-02-28
**Status:** Approved

## Summary

Simplify mtk by removing the LLM command group and graph export, replacing the
domain-specific MCP tools with a pure-SQL MCP server (`run_sql` + `get_schema`),
and adding an HTML Single File Application export.

## Changes

### 1. Remove LLM Command Group

Delete entirely:
- `src/mtk/llm/` (providers.py, classifier.py, __init__.py)
- LLM CLI sub-app in `cli/main.py` (~lines 1444-1700)
- Any LLM-related tests

Rationale: LLM interaction happens through MCP. The LLM client connects via MCP,
queries data with `run_sql`, and does classification/summarization natively.
Bundling an Ollama provider is redundant.

### 2. Remove Graph Export

Delete from `src/mtk/people/relationships.py`:
- `NetworkNode`, `NetworkEdge` dataclasses
- `build_network()`, `export_network_gexf()`, `export_network_json()`,
  `export_network_graphml()` methods

Delete from CLI:
- `graph` command in `cli/main.py`

Keep (used by relationship queries, which are still useful via SQL):
- `CorrespondenceStats` dataclass
- `get_top_correspondents()`, `get_correspondent_stats()`,
  `get_correspondence_timeline()` methods (used by CLI `people` commands)

### 3. Redesign MCP Server — Pure SQL

Replace all 13 domain-specific MCP tools with 2 tools:

**`run_sql`** — Execute SQL against the mtk database
- Input: `sql` (string, required), `readonly` (boolean, default true)
- When `readonly=true`: only SELECT queries allowed (enforced)
- When `readonly=false`: full SQL including INSERT/UPDATE/DELETE
- Returns: JSON array of row objects, or `{affected_rows: N}` for mutations
- Includes FTS5 support (queries against `emails_fts` table work)

**`get_schema`** — Return the full database schema
- Input: none
- Returns: DDL for all tables (including FTS5), plus column descriptions
  and relationship documentation as structured JSON
- This is what the LLM reads first to understand the data model

Delete:
- `src/mtk/mcp/tools.py` (all 13 domain handlers)
- `src/mtk/mcp/resources.py` (resource handlers)
- `src/mtk/mcp/validation.py` (argument validation helpers)
- All MCP resource templates (mtk://email/{id}, etc.)

Keep/modify:
- `src/mtk/mcp/__init__.py` — stdio transport entry point (unchanged)
- `src/mtk/mcp/__main__.py` — entry point (unchanged)
- `src/mtk/mcp/server.py` — rewrite to register just 2 tools, no resources

Transport: stdio (already is).

### 4. Add `mtk export html` — Single File Application

New file: `src/mtk/export/html_export.py`

Generates a self-contained HTML file containing:
- The full SQLite database embedded as base64
- sql.js (SQLite WASM) loaded from CDN
- A minimal email client UI: inbox, email detail, thread view, search,
  tag filtering, people list
- All in a single .html file

CLI: `mtk export html <output.html> [--query QUERY] [--privacy]`

### 5. Add arkiv Import/Export

arkiv is the universal personal data format in the longecho ecosystem. JSONL
records with `mimetype`, `content`, `uri`, `timestamp`, `metadata` fields.
See `../arkiv/SPEC.md` for the full specification.

**Export** (`mtk export arkiv <output.jsonl>`):
Each email becomes one arkiv record:
```jsonl
{"mimetype": "message/rfc822", "content": "<body_text>", "uri": "mtk://email/<message_id>", "timestamp": "<date_iso>", "metadata": {"subject": "...", "from_addr": "...", "from_name": "...", "to": "...", "thread_id": "...", "tags": [...], "message_id": "...", "has_attachments": true}}
```

Options:
- `--query QUERY` — filter emails to export
- `--privacy` — apply privacy rules
- `--include-body / --no-body` — include full body text or just metadata
  (default: include body)

Also generates a sibling `schema.yaml` describing the metadata keys.

**Import** (`mtk import arkiv <input.jsonl>`):
Parse arkiv JSONL records and create Email objects. Map fields:
- `content` → `body_text`
- `timestamp` → `date`
- `metadata.subject` → `subject`
- `metadata.from_addr` → `from_addr`
- `metadata.message_id` → `message_id`
- `metadata.tags` → Tag associations
- etc.

New files:
- `src/mtk/export/arkiv_export.py` — ArkivExporter
- `src/mtk/importers/arkiv.py` — ArkivImporter

### 6. Remove Embeddings and Semantic Search

Delete:
- `embedding` column from Email model
- `embedding` column from TopicCluster model
- `TopicCluster` model entirely (LLM-derived, no longer relevant)
- `email_topics` association table
- `semantic` optional dependency group (sentence-transformers, faiss-cpu)
- Semantic search path in `SearchEngine` (the `_semantic_search` method)
- `summary` column from Email and Thread models (LLM-generated, remove)

Keep:
- FTS5 full-text search (keyword search works without embeddings)
- Gmail-like query operators in SearchEngine

### 7. Cleanup

- Remove `httpx` from any dependency lists (was implicit Ollama dep)
- Update tests: delete LLM tests, MCP tool tests, graph tests; add new
  run_sql and get_schema tests, html export tests, arkiv import/export tests
- Update CLAUDE.md to reflect simplified architecture

## Data Model Changes

Remove from schema:
- `Email.embedding` column (bytes, was for semantic search)
- `Email.summary` column (text, was LLM-generated)
- `Thread.summary` column (text, was LLM-generated)
- `TopicCluster` model + `email_topics` association table (LLM-derived)

Remaining tables served through `run_sql`:
emails, persons, person_emails, threads, tags, email_tags, attachments,
annotations, collections, collection_emails, privacy_rules, custom_fields,
imap_sync_state, imap_pending_push, emails_fts

## MCP Server Architecture

```
python -m mtk.mcp  (stdio)
  |
  +-- get_schema   -> reads sqlite_master + adds descriptions
  +-- run_sql      -> executes SQL, returns JSON rows
```

The server resolves the database path from:
1. `MTK_DATABASE_PATH` env var
2. Config file (`~/.config/mtk/config.yaml`)
3. Default: `~/.local/share/mtk/mtk.db`
