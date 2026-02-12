#!/usr/bin/env python3
"""
Storage layer for the Gradient Research Assistant.

Handles:
1. Uploading research Markdown files to DigitalOcean Spaces
2. Triggering Gradient Knowledge Base re-indexing

Usage:
    python3 store.py --ticker CAKE --data /path/to/research.md
    python3 store.py --test --ticker CAKE
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import boto3
import requests
from botocore.config import Config

# DO API base
DO_API_BASE = "https://api.digitalocean.com"


def get_spaces_client(
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    endpoint: Optional[str] = None,
):
    """Create an S3-compatible client for DO Spaces.

    Falls back to environment variables if args aren't provided.
    """
    access_key = access_key or os.environ.get("DO_SPACES_ACCESS_KEY", "")
    secret_key = secret_key or os.environ.get("DO_SPACES_SECRET_KEY", "")
    endpoint = endpoint or os.environ.get("DO_SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )


def build_spaces_key(ticker: str, source: str = "combined", timestamp: Optional[str] = None) -> str:
    """Build the S3 key (path) for a research file in Spaces.

    Format: research/{date}/{TICKER}_{source}.md
    """
    if timestamp:
        date_str = timestamp[:10]  # YYYY-MM-DD from ISO format
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"research/{date_str}/{ticker}_{source}.md"


def upload_to_spaces(
    markdown_content: str,
    ticker: str,
    source: str = "combined",
    bucket: Optional[str] = None,
    timestamp: Optional[str] = None,
    client=None,
) -> dict:
    """Upload a Markdown research file to DO Spaces.

    Args:
        markdown_content: The Markdown text to upload
        ticker: Stock ticker symbol
        source: Source identifier (e.g., 'combined', 'news', 'reddit')
        bucket: Spaces bucket name
        timestamp: ISO timestamp for path construction
        client: Pre-configured S3 client (optional)

    Returns:
        dict with 'success', 'key', 'bucket', and 'message'
    """
    bucket = bucket or os.environ.get("DO_SPACES_BUCKET", "openclaw-research")

    try:
        if client is None:
            client = get_spaces_client()

        key = build_spaces_key(ticker, source, timestamp)

        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=markdown_content.encode("utf-8"),
            ContentType="text/markdown",
            ACL="private",
        )

        return {
            "success": True,
            "key": key,
            "bucket": bucket,
            "message": f"Uploaded {key} to {bucket}",
        }
    except Exception as e:
        return {
            "success": False,
            "key": "",
            "bucket": bucket,
            "message": f"Upload failed: {str(e)}",
        }


def trigger_kb_reindex(
    kb_uuid: Optional[str] = None,
    api_token: Optional[str] = None,
) -> dict:
    """Trigger a re-indexing job for the Gradient Knowledge Base.

    This tells the KB to re-scan its data sources (including our Spaces
    bucket) and index any new documents.

    Args:
        kb_uuid: Knowledge Base UUID
        api_token: DO personal access token

    Returns:
        dict with 'success' and 'message'
    """
    kb_uuid = kb_uuid or os.environ.get("GRADIENT_KB_UUID", "")
    api_token = api_token or os.environ.get("DO_API_TOKEN", "")

    if not kb_uuid:
        return {"success": False, "message": "No GRADIENT_KB_UUID configured."}
    if not api_token:
        return {"success": False, "message": "No DO_API_TOKEN configured."}

    # Get data sources for this KB
    try:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        # List data sources
        list_url = f"{DO_API_BASE}/v2/gen-ai/knowledge_bases/{kb_uuid}/data_sources"
        resp = requests.get(list_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data_sources = resp.json().get("data_sources", [])

        if not data_sources:
            return {"success": False, "message": "No data sources configured for this Knowledge Base."}

        # Trigger indexing for the first (Spaces) data source
        ds_id = data_sources[0].get("uuid", "")
        if not ds_id:
            return {"success": False, "message": "Data source has no UUID."}

        index_url = f"{DO_API_BASE}/v2/gen-ai/knowledge_bases/{kb_uuid}/indexing_jobs"
        index_payload = {
            "data_source_id": ds_id,
        }
        resp = requests.post(index_url, headers=headers, json=index_payload, timeout=15)
        resp.raise_for_status()

        return {
            "success": True,
            "message": f"Re-indexing triggered for KB {kb_uuid}, data source {ds_id}.",
        }
    except requests.RequestException as e:
        return {"success": False, "message": f"KB re-index failed: {str(e)}"}


def store_research(
    markdown_content: str,
    ticker: str,
    timestamp: Optional[str] = None,
) -> dict:
    """Store research data: upload to Spaces and trigger KB re-index.

    This is the main entry point — called after gather.py produces research.

    Returns:
        dict with upload and indexing results.
    """
    # Step 1: Upload to Spaces
    upload_result = upload_to_spaces(markdown_content, ticker, timestamp=timestamp)

    # Step 2: Trigger KB re-indexing (only if upload succeeded)
    if upload_result["success"]:
        index_result = trigger_kb_reindex()
    else:
        index_result = {"success": False, "message": "Skipped: upload failed."}

    return {
        "upload": upload_result,
        "indexing": index_result,
        "success": upload_result["success"],  # Overall success depends on upload
    }


# ─── CLI Interface ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Store research data to Spaces and KB")
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--data", help="Path to research Markdown file")
    parser.add_argument("--test", action="store_true", help="Upload a test document")

    args = parser.parse_args()
    ticker = args.ticker.upper().lstrip("$")

    if args.test:
        content = f"# Test Document: {ticker}\n\nThis is a test upload at {datetime.now(timezone.utc).isoformat()}."
    elif args.data:
        content = Path(args.data).read_text()
    else:
        print("Error: --data or --test required.", file=sys.stderr)
        sys.exit(1)

    result = store_research(content, ticker)
    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
