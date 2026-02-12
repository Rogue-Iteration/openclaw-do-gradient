#!/usr/bin/env python3
"""
Knowledge Base query layer for the Gradient Research Assistant.

Queries the Gradient Knowledge Base via RAG for ticker research
accumulated over time.

Usage:
    python3 query_kb.py --query "What do you know about CAKE?"
    python3 query_kb.py --ticker CAKE
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests

# Gradient inference endpoint (used for RAG-enhanced queries)
GRADIENT_INFERENCE_URL = "https://inference.do-ai.run/v1/chat/completions"
DO_API_BASE = "https://api.digitalocean.com"


def query_knowledge_base(
    query: str,
    kb_uuid: Optional[str] = None,
    api_token: Optional[str] = None,
) -> dict:
    """Query the Gradient Knowledge Base directly.

    Args:
        query: The search query
        kb_uuid: Knowledge Base UUID
        api_token: DO personal access token

    Returns:
        dict with 'success', 'results', and 'message'
    """
    kb_uuid = kb_uuid or os.environ.get("GRADIENT_KB_UUID", "")
    api_token = api_token or os.environ.get("DO_API_TOKEN", "")

    if not kb_uuid:
        return {"success": False, "results": [], "message": "No GRADIENT_KB_UUID configured."}
    if not api_token:
        return {"success": False, "results": [], "message": "No DO_API_TOKEN configured."}

    try:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        url = f"{DO_API_BASE}/v2/gen-ai/knowledge_bases/{kb_uuid}/query"
        payload = {"query": query, "top_k": 10}

        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        results = data.get("results", [])

        return {
            "success": True,
            "results": results,
            "message": f"Found {len(results)} relevant documents.",
        }
    except requests.RequestException as e:
        return {"success": False, "results": [], "message": f"KB query failed: {str(e)}"}


def build_rag_prompt(query: str, kb_results: list[dict]) -> str:
    """Build a RAG-enhanced prompt combining the user's question with KB context.

    Args:
        query: The user's original question
        kb_results: Results from the Knowledge Base query

    Returns:
        The RAG-enhanced prompt
    """
    if not kb_results:
        context = "No prior research data available yet. The knowledge base is still building up."
    else:
        context_parts = []
        for i, result in enumerate(kb_results, 1):
            content = result.get("content", result.get("text", ""))
            source = result.get("metadata", {}).get("source", "unknown")
            score = result.get("score", 0)
            context_parts.append(f"### Source {i} (relevance: {score:.2f})\n{content}")
        context = "\n\n".join(context_parts)

    return f"""You are a financial research assistant with access to a growing knowledge base of research data.
Answer the user's question using the research context below. Be specific, cite dates and sources when available,
and note when information might be outdated.

## Research Context (from Knowledge Base):
{context}

## User's Question:
{query}

## Instructions:
- Answer based on the research context above
- If the KB doesn't have enough data, say so honestly
- Mention when findings were gathered (dates from the documents)
- If asked about a ticker not in the KB, explain that it needs to be added to the watchlist
- Be concise but thorough"""


def query_with_rag(
    query: str,
    model: str = "qwen3-32b",
    kb_uuid: Optional[str] = None,
    api_key: Optional[str] = None,
    api_token: Optional[str] = None,
) -> dict:
    """Run a RAG-enhanced query: KB search → LLM synthesis.

    Args:
        query: The user's question
        model: LLM model for synthesis
        kb_uuid: Knowledge Base UUID
        api_key: Gradient API key (for inference)
        api_token: DO API token (for KB query)

    Returns:
        dict with 'success', 'answer', 'sources_count', 'message'
    """
    api_key = api_key or os.environ.get("GRADIENT_API_KEY", "")

    if not api_key:
        return {
            "success": False,
            "answer": "",
            "sources_count": 0,
            "message": "No GRADIENT_API_KEY configured.",
        }

    # Step 1: Query the Knowledge Base
    kb_result = query_knowledge_base(query, kb_uuid=kb_uuid, api_token=api_token)
    kb_results = kb_result.get("results", [])

    # Step 2: Build RAG prompt
    prompt = build_rag_prompt(query, kb_results)

    # Step 3: Call LLM for synthesis
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful financial research assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 1500,
        }

        resp = requests.post(GRADIENT_INFERENCE_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        answer = data["choices"][0]["message"]["content"]

        return {
            "success": True,
            "answer": answer,
            "sources_count": len(kb_results),
            "kb_success": kb_result["success"],
            "message": f"Answered using {len(kb_results)} sources from the Knowledge Base.",
        }
    except (requests.RequestException, KeyError, IndexError) as e:
        return {
            "success": False,
            "answer": "",
            "sources_count": len(kb_results),
            "message": f"LLM synthesis failed: {str(e)}",
        }


# ─── CLI Interface ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Query the research knowledge base")
    parser.add_argument("--query", help="Freeform query")
    parser.add_argument("--ticker", help="Ticker to ask about")

    args = parser.parse_args()

    if args.ticker:
        query = f"What do you know about ${args.ticker.upper()}? Summarize all research findings."
    elif args.query:
        query = args.query
    else:
        print("Error: --query or --ticker required.", file=sys.stderr)
        sys.exit(1)

    result = query_with_rag(query)

    if result["success"]:
        print(result["answer"])
        print(f"\n📚 Used {result['sources_count']} sources from the Knowledge Base.", file=sys.stderr)
    else:
        print(f"Error: {result['message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
