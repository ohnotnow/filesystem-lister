# Filesystem Lister

A distributed media file aggregator that indexes files across multiple hosts and enables semantic search.

> **Warning**
> This project is a work in progress and under active development. Do not use with sensitive files or content. Use at your own risk.

## Overview

Filesystem Lister consists of two components:

1. **Go Server** - A lightweight HTTP service that runs on each host and exposes file listings via a REST API
2. **Python CLI** - A command-line tool that aggregates files from multiple servers and provides semantic search using ChromaDB

## Requirements

- Go 1.24+ (for the server)
- Python 3.12+ with [uv](https://docs.astral.sh/uv/) (for the CLI)

## Installation

### Go Server

```bash
# Build the binary
go build -o filesystem-lister

# Or run directly
go run main.go --dir /path/to/media --port 8080
```

### Python CLI

```bash
# Install dependencies with uv
uv sync
```

## Usage

### Starting the Server

Run the server on each host where you have media files:

```bash
./filesystem-lister --dir /path/to/media --port 8080

# Multiple directories
./filesystem-lister --dir /movies --dir /tv-shows --port 8080

# Custom friendly name
./filesystem-lister --dir /media --friendlyname "living-room-nas"
```

#### Server Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /list` | List all files |
| `GET /filter?q=*pattern*` | Filter files (DOS-style wildcards) |

### Configuring Hosts

Create or edit `media-hosts.json`:

```json
{
  "hosts": [
    {"name": "nas", "url": "http://192.168.1.100:8080"},
    {"name": "desktop", "url": "http://192.168.1.101:8080"}
  ]
}
```

### Using the CLI

```bash
# List configured hosts
uv run ./media-search.py hosts

# Index files from all hosts
uv run ./media-search.py index

# Semantic search
uv run ./media-search.py search "space adventure"
uv run ./media-search.py search "romantic comedy" -n 20
```

## How It Works

1. The Go server scans configured directories and serves file metadata via HTTP
2. The Python CLI fetches file listings from all configured hosts
3. File names are indexed in ChromaDB for semantic search
4. Search queries return results ranked by semantic similarity

## Development

```bash
# Run Go tests
go test ./...

# Run server locally
go run main.go --dir ./test-files --port 8080
```

## License

MIT License - see [LICENSE](LICENSE) for details.
