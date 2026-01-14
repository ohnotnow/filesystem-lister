#!/usr/bin/env python
"""
Media search CLI - queries filesystem-lister instances and searches semantically.

Usage:
    ./media-search.py index          # Fetch from all hosts and index
    ./media-search.py search "query" # Search the index
    ./media-search.py hosts          # List configured hosts
"""

import argparse
import json
import sys
from pathlib import Path

import chromadb
import httpx

CONFIG_FILE = Path(__file__).parent / "media-hosts.json"
DB_PATH = Path(__file__).parent / ".media-index"


def load_hosts():
    if not CONFIG_FILE.exists():
        print(f"No config file found at {CONFIG_FILE}")
        print("Create one with: {\"hosts\": [{\"name\": \"my-box\", \"url\": \"http://host:port\"}]}")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text())["hosts"]


def get_collection():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection("media")


def cmd_hosts(args):
    hosts = load_hosts()
    for h in hosts:
        print(f"{h['name']}: {h['url']}")


def cmd_index(args):
    hosts = load_hosts()
    collection = get_collection()

    # Clear existing
    collection.delete(where={})

    all_files = []
    for host in hosts:
        print(f"Fetching from {host['name']}...")
        try:
            resp = httpx.get(f"{host['url']}/list", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for f in data["files"]:
                all_files.append({
                    "id": f"{host['name']}:{f['path']}",
                    "name": f["name"],
                    "path": f["path"],
                    "host": host["name"],
                })
        except Exception as e:
            print(f"  Error: {e}")

    if not all_files:
        print("No files found")
        return

    print(f"Indexing {len(all_files)} files...")
    collection.add(
        ids=[f["id"] for f in all_files],
        documents=[f["name"] for f in all_files],
        metadatas=[{"path": f["path"], "host": f["host"]} for f in all_files],
    )
    print("Done")


def cmd_search(args):
    collection = get_collection()

    if collection.count() == 0:
        print("Index is empty. Run 'index' first.")
        return

    results = collection.query(
        query_texts=[args.query],
        n_results=args.limit,
    )

    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        score = 1 - (dist / 2)  # Convert distance to similarity
        print(f"[{meta['host']}] {doc}")
        print(f"  {meta['path']}")
        print(f"  similarity: {score:.2f}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Media search CLI")
    subs = parser.add_subparsers(dest="command", required=True)

    subs.add_parser("hosts", help="List configured hosts")
    subs.add_parser("index", help="Fetch and index from all hosts")

    search = subs.add_parser("search", help="Search the index")
    search.add_argument("query", help="Search query")
    search.add_argument("-n", "--limit", type=int, default=10, help="Max results")

    args = parser.parse_args()

    if args.command == "hosts":
        cmd_hosts(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "search":
        cmd_search(args)


if __name__ == "__main__":
    main()
