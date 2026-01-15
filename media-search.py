#!/usr/bin/env python
"""
Media search CLI - queries filesystem-lister instances and searches semantically.

Usage:
    ./media-search.py index           # Sync from hosts (only if changed)
    ./media-search.py index --force   # Force sync even if versions match
    ./media-search.py search "query"  # Search the index
    ./media-search.py hosts           # List configured hosts
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


def get_client():
    return chromadb.PersistentClient(path=str(DB_PATH))


def get_collection(client=None):
    if client is None:
        client = get_client()
    return client.get_or_create_collection("media")


def get_stored_versions(collection) -> dict[str, str]:
    """Get stored versions from collection metadata."""
    meta = collection.metadata or {}
    versions_json = meta.get("versions", "{}")
    return json.loads(versions_json)


def store_versions(collection, versions: dict[str, str]):
    """Store versions in collection metadata (serialized as JSON string)."""
    collection.modify(metadata={"versions": json.dumps(versions)})


def fetch_host_version(host: dict) -> str | None:
    """Fetch version from a host's health endpoint."""
    try:
        resp = httpx.get(f"{host['url']}/health", timeout=5)
        resp.raise_for_status()
        return resp.json().get("version")
    except Exception as e:
        print(f"  Warning: Could not fetch version from {host['name']}: {e}")
        return None


def sync_host(collection, host: dict, files: list[dict]) -> tuple[int, int]:
    """
    Sync files from a host using smart diffing.
    Returns (added_count, removed_count).
    """
    # Build set of IDs from server
    server_ids = {f"{host['name']}:{f['path']}" for f in files}

    # Get existing IDs for this host from ChromaDB
    existing = collection.get(
        where={"host": host["name"]},
        include=[]  # We only need IDs
    )
    existing_ids = set(existing["ids"])

    # Compute diff
    to_add_ids = server_ids - existing_ids
    to_remove_ids = existing_ids - server_ids

    # Remove deleted files
    if to_remove_ids:
        collection.delete(ids=list(to_remove_ids))

    # Add new files
    if to_add_ids:
        # Build file lookup for new files
        files_by_id = {f"{host['name']}:{f['path']}": f for f in files}
        new_files = [files_by_id[id] for id in to_add_ids]

        collection.add(
            ids=[f"{host['name']}:{f['path']}" for f in new_files],
            documents=[f["name"] for f in new_files],
            metadatas=[{"path": f["path"], "host": host["name"]} for f in new_files],
        )

    return len(to_add_ids), len(to_remove_ids)


def cmd_hosts(args):
    hosts = load_hosts()
    for h in hosts:
        print(f"{h['name']}: {h['url']}")


def cmd_index(args):
    hosts = load_hosts()
    client = get_client()
    collection = get_collection(client)

    if getattr(args, "force", False):
        print("Force mode: ignoring versions, syncing all hosts")
        stored_versions = {}
    else:
        stored_versions = get_stored_versions(collection)

    new_versions = {}
    total_added = 0
    total_removed = 0
    hosts_updated = 0
    hosts_skipped = 0

    for host in hosts:
        print(f"Checking {host['name']}...")

        # Fetch current version
        current_version = fetch_host_version(host)
        if current_version is None:
            print(f"  Skipping (could not connect)")
            # Keep old version if we had one
            if host["name"] in stored_versions:
                new_versions[host["name"]] = stored_versions[host["name"]]
            continue

        stored_version = stored_versions.get(host["name"])

        # Check if update needed
        if current_version == stored_version:
            print(f"  No changes (version: {current_version[:20]}...)")
            new_versions[host["name"]] = current_version
            hosts_skipped += 1
            continue

        # Fetch full file list
        print(f"  Changes detected, fetching files...")
        try:
            resp = httpx.get(f"{host['url']}/list", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            files = [{"name": f["name"], "path": f["path"]} for f in data["files"]]
        except Exception as e:
            print(f"  Error fetching files: {e}")
            continue

        # Sync using diff
        added, removed = sync_host(collection, host, files)
        print(f"  Synced: +{added} -{removed} files")

        new_versions[host["name"]] = current_version
        total_added += added
        total_removed += removed
        hosts_updated += 1

    # Store updated versions
    store_versions(collection, new_versions)

    # Summary
    print()
    print(f"Done: {hosts_updated} hosts updated, {hosts_skipped} skipped")
    print(f"Total: +{total_added} added, -{total_removed} removed")


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
    index_parser = subs.add_parser("index", help="Fetch and index from all hosts")
    index_parser.add_argument(
        "-f", "--force", action="store_true",
        help="Force re-sync even if versions match"
    )

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
