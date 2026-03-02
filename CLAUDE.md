# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

mtk (Mail Toolkit) is a personal email archive management tool with full-text search, relationship mapping, and privacy controls. It wraps notmuch for indexing and adds a SQLite shadow database for enhanced features. LLM interaction happens via a pure-SQL MCP server (run_sql + get_schema over stdio).

Part of the longecho personal archive ecosystem alongside ctk (conversations), btk (bookmarks), ebk (ebooks), stk (static sites), and ptk (photos).

## Development Commands

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run specific test file
pytest tests/test_search.py

# Run with coverage
pytest --cov=src/mtk --cov-report=term-missing

# Type checking
mypy src/mtk

# Linting
ruff check src/mtk tests
ruff format src/mtk tests
```

## Architecture

### Core Layer (`src/mtk/core/`)
- `models.py` - SQLAlchemy ORM models: Email, Person, PersonEmail, Thread, Tag, Attachment, Annotation, Collection, PrivacyRule, CustomField, ImapSyncState, ImapPendingPush
- `database.py` - Database session management, uses SQLite with WAL mode and foreign keys enabled
- `config.py` - MtkConfig and PrivacyConfig for YAML-based configuration
- `privacy.py` - PrivacyFilter for exclusion/redaction rules during export

### Importers (`src/mtk/importers/`)
- `base.py` - BaseImporter abstract class with `discover()`, `parse()`, `import_all()` methods
- `parser.py` - EmailParser for RFC 2822 parsing, returns ParsedEmail dataclass
- `maildir.py`, `mbox.py`, `eml.py` - Format-specific importers (MaildirImporter, MboxImporter, EmlImporter)

### People/Relationships (`src/mtk/people/`)
- `resolver.py` - PersonResolver for merging multiple email addresses into unified Person records
- `relationships.py` - RelationshipAnalyzer for correspondence statistics (top correspondents, timelines)

### Search (`src/mtk/search/`)
- `engine.py` - SearchEngine with FTS5 full-text search (BM25 scoring, porter stemmer) and Gmail-like query operators (from:, to:, subject:, after:, before:, tag:, has:attachment)
- `fts.py` - FTS5 virtual table setup, triggers for automatic sync, query preparation

### Export (`src/mtk/export/`)
- `base.py` - Exporter (ABC) and ExportResult
- `json_export.py`, `mbox_export.py`, `markdown_export.py` - Format-specific exporters with privacy filter support
- `html_export.py` - HtmlExporter: generates a self-contained HTML Single File Application with embedded SQLite database (sql.js from CDN)
- `arkiv_export.py` - ArkivExporter: exports to arkiv JSONL format with schema.yaml generation

### MCP Server (`src/mtk/mcp/`)
- `server.py` - Pure-SQL MCP server with 2 tools: `run_sql` (execute SQL, read-only by default) and `get_schema` (database schema with descriptions and query tips)
- `__init__.py` - stdio transport entry point
- `__main__.py` - `python -m mtk.mcp` entry point

### IMAP Sync (`src/mtk/imap/`)
- `auth.py` - AuthManager for password/OAuth2 credential storage
- `connection.py` - ImapConnection context manager
- `pull.py` - Incremental IMAP fetch with UID tracking
- `push.py` - Queue-based tag change push to IMAP server
- `gmail.py` - Gmail-specific label mapping
- `mapping.py` - IMAP flag ↔ mtk tag mapping

### notmuch Integration (`src/mtk/integrations/`)
- `notmuch.py` - NotmuchSync for bidirectional tag sync and email import from notmuch database

### CLI (`src/mtk/cli/`)
- `main.py` - Typer app with commands: inbox, show, thread, reply, search, stats, init, shell
- Sub-apps: `import` (maildir, mbox, eml, gmail), `people` (list, show), `export` (json, mbox, markdown, html, arkiv), `tag` (add, remove, batch), `notmuch` (status, pull, push, sync, import)
- `imap_cli.py` - IMAP sub-commands (accounts, sync, push, folders, test)
- `shell.py` - Interactive REPL mode

## Key Patterns

### Database Sessions
Use context manager for sessions (auto-commit on success, rollback on error):
```python
db = Database(path)
with db.session() as session:
    session.add(email)
    # commits automatically
```

### JSON Output
All CLI commands support `--json` flag for programmatic use - output valid JSON to stdout.

### Privacy Filtering
Apply privacy rules during export by passing `privacy_filter` to exporters. Privacy config is loaded from `~/.config/mtk/privacy.yaml`.

### MCP Server
The MCP server exposes the SQLite database directly via `run_sql` + `get_schema`. Configure in `.mcp.json`:
```json
{"mcpServers": {"mtk": {"command": "python", "args": ["-m", "mtk.mcp"]}}}
```
Set `MTK_DATABASE_PATH` env var to override the database location.

## Testing

Tests use pytest with fixtures defined in `tests/conftest.py`:
- `db` - In-memory database
- `session` - Database session from in-memory db
- `populated_db` - Database with sample data (5 emails, 3 persons, 2 threads, 4 tags)
- `sample_maildir`, `sample_mbox`, `sample_eml_dir` - File system fixtures for import testing
- `email_factory`, `person_factory` - Factory fixtures for creating test data

## Optional Dependencies

- `notmuch` extra: notmuch2 bindings for mail indexing integration
- `mcp` extra: MCP Python SDK for the stdio MCP server
- `imap` extra: imapclient + keyring for IMAP sync
- `imap-oauth` extra: google-auth-oauthlib for Gmail OAuth2
