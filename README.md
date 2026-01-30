# mtk — Mail Toolkit

A toolkit for managing personal email archives with semantic search, relationship mapping, and privacy controls. Built atop `notmuch` with extensions for the longecho ecosystem.

## Status

**Incubating.** Part of the [longecho](../longecho) personal archive ecosystem.

## The Problem

Your email archive — decades of correspondence, relationships, decisions, life — is:

- Trapped in proprietary formats or cloud services
- Searchable only by keywords, not meaning
- Missing relationship context (who matters? how often?)
- A privacy minefield if not handled carefully
- Likely to disappear when services shut down

Email is one of the most complete records of your relationships and correspondence. It deserves careful preservation.

## The Vision

mtk provides:

1. **Import from anywhere** — Maildir, mbox, Gmail Takeout, IMAP exports
2. **notmuch integration** — Leverage excellent existing indexing
3. **Enhanced search** — Semantic search, relationship queries
4. **Relationship mapping** — Who do you correspond with? How often? About what?
5. **Privacy controls** — Filter, redact, selectively export
6. **longecho export** — Unified archive format with appropriate privacy

```
┌─────────────────────────────────────────────────────────────────┐
│                         IMPORT SOURCES                           │
├─────────────────────────────────────────────────────────────────┤
│  Maildir  │  mbox  │  Gmail Takeout  │  IMAP export  │  EML    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     NOTMUCH (indexing core)                      │
│                                                                  │
│  • Fast full-text search                                        │
│  • Tag-based organization                                       │
│  • Thread reconstruction                                        │
│  • Xapian backend                                               │
│                                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MTK (enhancement layer)                      │
│                                                                  │
│  • SQLite shadow database (our metadata)                        │
│  • Embeddings for semantic search                               │
│  • Relationship extraction and mapping                          │
│  • Thread summarization                                         │
│  • Privacy filtering and redaction                              │
│                                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                          EXPORT                                  │
├─────────────────────────────────────────────────────────────────┤
│  Filtered archive  │  Relationship graph  │  longecho           │
└─────────────────────────────────────────────────────────────────┘
```

## Relation to longecho

mtk is a **domain toolkit** in the longecho ecosystem:

| Tool | Domain | What it captures |
|------|--------|------------------|
| ctk | Conversations | How you think, your voice |
| btk | Bookmarks | What you find worth preserving |
| ebk | Ebooks | Your intellectual foundations |
| stk | Static sites | Your public voice |
| ptk | Photos | Visual memories |
| **mtk** | **Mail** | **Relationships, correspondence** |
| longecho | Orchestration | Synthesis, durability, the ghost |

mtk exports to the **unified artifact format** that longecho ingests.

## Why Wrap notmuch?

[notmuch](https://notmuchmail.org/) is an excellent mail indexer that aligns with our philosophy:

- **Fast** — Xapian-based full-text search
- **Tag-based** — Flexible organization
- **Unix philosophy** — Does one thing well
- **Maildir native** — Standard format
- **Active development** — Well-maintained

Rather than reinvent mail indexing, mtk wraps notmuch and adds:
- Semantic search (embeddings)
- Relationship mapping
- Privacy controls
- longecho integration

## Design Philosophy

- **notmuch-native** — Use notmuch for core indexing, don't replace it
- **SQLite shadow** — Our metadata alongside notmuch's Xapian
- **Privacy-first** — Explicit controls on what gets exported
- **Relationship-aware** — Who matters, not just what was said
- **Local-only** — No cloud, no sync, your mail stays yours

## Planned Usage

```bash
# Initial setup (uses existing notmuch or creates new)
mtk init ~/mail              # Point to Maildir
mtk init --import-mbox ~/archive.mbox
mtk init --import-gmail ~/takeout/mail

# Sync with notmuch
mtk sync                     # Pull notmuch tags and index

# Search (enhanced)
mtk search "project proposal"           # Full-text
mtk search --semantic "discussions about moving" # Semantic
mtk search --from "mom"                 # From specific person
mtk search --thread thread:abc123       # Show thread

# Relationships
mtk people                   # List correspondents
mtk people --top 20          # Most frequent
mtk person "John Smith"      # Correspondence with person
mtk graph                    # Relationship graph

# Summarization
mtk summarize thread:abc123  # Summarize a thread
mtk summarize --from "boss"  # Summarize correspondence

# Privacy
mtk privacy show             # Show current privacy rules
mtk privacy add-exclude "work@company.com"
mtk privacy add-redact "secret-project"
mtk privacy preview          # Preview what would be exported

# Export
mtk export archive ~/mail-archive       # Filtered archive
mtk export graph ~/relationships.json   # Relationship graph
mtk export longecho                      # Unified format
```

## Data Model

SQLAlchemy ORM models stored in SQLite:

```python
class Email(Base):
    message_id: str            # Message-ID (unique)
    thread_id: str | None      # FK to Thread
    from_addr: str
    from_name: str | None
    subject: str | None
    date: datetime
    in_reply_to: str | None
    references: str | None     # Space-separated message IDs
    body_text: str | None
    body_html: str | None
    body_preview: str | None
    embedding: bytes | None    # For semantic search
    summary: str | None        # AI-generated summary
    export_allowed: bool       # Privacy control
    # Relationships: thread, sender, attachments, tags

class Person(Base):
    name: str
    primary_email: str | None
    relationship_type: str | None  # "family", "friend", "colleague", etc.
    email_count: int
    first_contact: datetime | None
    last_contact: datetime | None
    # Relationships: email_addresses (PersonEmail), sent_emails

class Thread(Base):
    thread_id: str             # Unique thread identifier
    subject: str | None
    email_count: int
    first_date: datetime | None
    last_date: datetime | None
    summary: str | None
    # Relationships: emails
```

Additional models: `Tag`, `Attachment`, `Annotation`, `Collection`, `PrivacyRule`, `TopicCluster`, `PersonEmail`, `CustomField`.

## Privacy Controls

Email is sensitive. mtk provides explicit privacy controls:

### Exclusion Rules
```yaml
# ~/.config/mtk/privacy.yaml
exclude:
  # Exclude by address
  addresses:
    - "*@work.com"
    - "boss@company.com"

  # Exclude by tag
  tags:
    - "work"
    - "confidential"

  # Exclude by content pattern
  patterns:
    - "CONFIDENTIAL"
    - "attorney-client"
```

### Redaction Rules
```yaml
redact:
  # Redact specific patterns in exported content
  patterns:
    - pattern: '\b\d{3}-\d{2}-\d{4}\b'  # SSN
      replacement: "[REDACTED-SSN]"
    - pattern: 'secret-project-\w+'
      replacement: "[REDACTED-PROJECT]"
```

### Export Levels
```bash
mtk export --level personal   # Only personal (non-work)
mtk export --level family     # Only family
mtk export --level all        # Everything (careful!)
```

## Import Sources (Planned)

| Source | Format | Priority |
|--------|--------|----------|
| Maildir | standard | HIGH |
| mbox | standard | HIGH |
| Gmail Takeout | MBOX in zip | HIGH |
| EML files | individual emails | MEDIUM |
| IMAP | direct download | MEDIUM |
| Outlook PST | proprietary | LOW |

## Integration with notmuch

mtk does not replace notmuch — it enhances it:

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOUR MAIL                                │
│                    (Maildir structure)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│        NOTMUCH          │    │          MTK            │
│                         │    │                         │
│  • Xapian index         │◄───│  • Shadow SQLite        │
│  • Full-text search     │    │  • Embeddings           │
│  • Tags                 │    │  • Relationships        │
│  • Threads              │    │  • Privacy rules        │
│                         │    │  • Summaries            │
└─────────────────────────┘    └─────────────────────────┘
```

## Technical Notes

### notmuch Integration (Optional)

notmuch is optional. mtk can import emails directly from Maildir, mbox, and EML files without notmuch. Install notmuch for bidirectional tag sync and notmuch-based import:

```bash
# Debian/Ubuntu
sudo apt install notmuch

# Arch
sudo pacman -S notmuch

# macOS
brew install notmuch
```

### Shadow Database

mtk maintains a SQLite database alongside notmuch's Xapian index:

- Embeddings (notmuch doesn't have these)
- Relationship data
- Summaries
- Privacy rules
- Export metadata

### Embedding Generation

For semantic search, mtk generates embeddings for email content:

```python
# Using sentence-transformers
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embedding = model.encode(email.body_text)
```

## Development

```bash
cd ~/github/beta/mtk
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Dependencies

- **SQLAlchemy** — ORM and database layer (required)
- **typer + rich** — CLI framework (required)
- **notmuch + notmuch2** — Mail indexing integration (optional, `pip install mtk[notmuch]`)
- **sentence-transformers** — Embeddings for semantic search (optional, `pip install mtk[semantic]`)
- **ollama** — Local LLM for classification/summarization (optional)

## License

MIT
