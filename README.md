# Filesystem Lister

> **Warning**
> This project is a work in progress and under active development. Do not use with sensitive files or content. Use at your own risk.

## What Is This?

If you have media files scattered across multiple machines (a NAS, a desktop, a Raspberry Pi, etc.) and you want to search across all of them from one place, this tool helps with that.

```
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  NAS             │   │  Desktop         │   │  Raspberry Pi    │
│  /movies         │   │  /downloads      │   │  /media          │
│                  │   │                  │   │                  │
│  [Go server]     │   │  [Go server]     │   │  [Go server]     │
│  :8080           │   │  :8080           │   │  :8080           │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │ HTTP
                    ┌───────────▼───────────┐
                    │   Your Laptop         │
                    │                       │
                    │   [Python CLI]        │
                    │   media-search.py     │
                    │   media-hosts.json    │
                    │   .media-index/       │
                    └───────────────────────┘
```

## The Two Parts

### 1. Go Server (runs on each machine with files)

A small HTTP server that lists files from directories you specify. You deploy this to each machine that has media files you want to search.

### 2. Python CLI (runs on your local machine)

A command-line tool that:
- Connects to all your Go servers
- Pulls down the file listings
- Indexes them locally using ChromaDB
- Lets you search semantically (e.g., "space adventure" finds "Interstellar")

## Quick Start

### On each machine with media files

1. Download the appropriate binary from [Releases](https://github.com/ohnotnow/filesystem-lister/releases) (or build with `go build`)

2. Run it, pointing at your media directories:
   ```bash
   ./filesystem-lister --dir /path/to/movies --dir /path/to/tv --port 8080
   ```

3. Verify it's working:
   ```bash
   curl http://localhost:8080/health
   # {"host":"my-nas","status":"ok"}
   ```

### On your local machine (where you want to search)

1. Clone this repo:
   ```bash
   git clone https://github.com/ohnotnow/filesystem-lister.git
   cd filesystem-lister
   ```

2. Install Python dependencies using [uv](https://docs.astral.sh/uv/):
   ```bash
   uv sync
   ```

3. Edit `media-hosts.json` to list your servers:
   ```json
   {
     "hosts": [
       {"name": "nas", "url": "http://192.168.1.100:8080"},
       {"name": "desktop", "url": "http://192.168.1.101:8080"},
       {"name": "pi", "url": "http://192.168.1.102:8080"}
     ]
   }
   ```

4. Index all your files:
   ```bash
   uv run ./media-search.py index
   ```

5. Search:
   ```bash
   uv run ./media-search.py search "heist movie"
   ```

## CLI Commands

```bash
uv run ./media-search.py hosts           # List configured servers
uv run ./media-search.py index           # Fetch and index from all servers
uv run ./media-search.py search "query"  # Semantic search
uv run ./media-search.py search "query" -n 20  # Return more results
```

## Server Options

```bash
./filesystem-lister --dir /media         # Required: directory to scan (repeatable)
                    --port 8080           # HTTP port (default: 8080)
                    --friendlyname "nas"  # Display name (default: hostname)
```

## Server API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /list` | List all files |
| `GET /filter?q=*pattern*` | Filter files (DOS-style wildcards: `*word*`, `word*`, `*.mkv`) |

## Building the Go Server Locally

If you're not using a pre-built release binary, you can build it yourself:

```bash
cd filesystem-lister
go build -o filesystem-lister .
```

Or to cross-compile for another platform (e.g., Raspberry Pi):

```bash
GOOS=linux GOARCH=arm64 go build -o filesystem-lister-linux-arm64 .
```

Don't forget to rebuild after making changes - a classic gotcha!

## How Indexing Works

The system uses a version-based approach to avoid unnecessary re-indexing:

1. **Server-side SHA**: The Go server computes a SHA256 hash of all file paths it's serving. This hash is returned in the `/health` endpoint as the `version` field.

2. **Client-side caching**: The Python CLI stores the last-seen version for each host in ChromaDB's collection metadata.

3. **Smart sync**: When you run `index`, the CLI checks each host's current version against the stored version. If they match, that host is skipped. If they differ (files added/removed), it fetches the full listing and syncs.

4. **Diff-based updates**: When syncing, the CLI compares the server's file list against what's already indexed, only adding new files and removing deleted ones.

This means after the initial index, subsequent runs are fast - only hosts with actual changes get re-indexed.

## Requirements

- **Go servers**: Go 1.24+ to build, or just download a binary
- **Python CLI**: Python 3.12+ with [uv](https://docs.astral.sh/uv/)

## License

MIT License - see [LICENSE](LICENSE) for details.
