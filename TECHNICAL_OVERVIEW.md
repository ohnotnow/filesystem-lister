# Technical Overview

Last updated: 2026-01-14

## What This Is

A distributed media file aggregator that indexes files across multiple hosts and enables semantic search.

## Stack

**Go Server (filesystem-lister)**
- Go 1.24.1
- Standard library only (no external dependencies)

**Python CLI (media-search)**
- Python 3.12+
- chromadb 1.4.1 (vector database for semantic search)
- httpx 0.28.1 (HTTP client)

## Directory Structure

```
.
├── main.go              # Go HTTP server - lists files from directories
├── main_test.go         # Server unit tests
├── media-search.py      # Python CLI for indexing and searching
├── media-hosts.json     # Host configuration (list of servers to query)
├── pyproject.toml       # Python dependencies (uv managed)
└── AGENTS.md            # Agent workflow instructions (uses beads/bd)
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Host A         │     │  Host B         │     │  Host C         │
│  (Go server)    │     │  (Go server)    │     │  (Go server)    │
│  :8080/list     │     │  :8080/list     │     │  :8080/list     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   media-search.py       │
                    │   (Python CLI)          │
                    ├─────────────────────────┤
                    │   ChromaDB              │
                    │   (.media-index/)       │
                    └─────────────────────────┘
```

## Go Server (main.go)

### Data Types

| Type | Purpose |
|------|---------|
| `Config` | Runtime config: port, dirs, friendly name |
| `FileEntry` | Single file: path, name, size |
| `ListResponse` | API response: host name + file list |

### HTTP Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check, returns `{"status":"ok","host":"..."}` |
| `/list` | GET | Returns all files from configured directories |
| `/filter?q=` | GET | Returns files matching pattern (DOS-style wildcards) |

### Pattern Matching (matchPattern)

Case-insensitive DOS-style wildcards:
- `*word*` - contains
- `word*` - prefix
- `*word` - suffix
- `word` - exact match

### CLI Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--port` | 8080 | HTTP port |
| `--dir` | (required) | Directory to scan (repeatable) |
| `--friendlyname` | hostname | Display name in responses |

## Python CLI (media-search.py)

### Commands

| Command | Purpose |
|---------|---------|
| `hosts` | List configured hosts from media-hosts.json |
| `index` | Fetch files from all hosts, store in ChromaDB |
| `search <query>` | Semantic search across indexed files |

### Configuration

`media-hosts.json` format:
```json
{"hosts": [{"name": "my-box", "url": "http://host:port"}]}
```

### Storage

ChromaDB persistent storage in `.media-index/` directory.

## Testing

- Framework: Go testing package
- Run: `go test ./...`
- Coverage: matchPattern, handleHealth, handleList, handleFilter

## Local Development

```bash
# Start Go server
go run main.go --dir /path/to/media --port 8080

# Or use compiled binary
./filesystem-lister --dir /path/to/media

# Python CLI (uses uv)
uv run media-search.py hosts
uv run media-search.py index
uv run media-search.py search "movie name"
```

## Issue Tracking

Uses beads (`bd`) for issue tracking. See `AGENTS.md` and `beads.blade.php` for workflow.
