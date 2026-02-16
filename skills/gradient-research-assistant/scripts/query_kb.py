#!/usr/bin/env python3
"""
Knowledge Base query layer for the Gradient Research Assistant.

Queries the Gradient Knowledge Base via RAG for ticker research
accumulated over time.

Usage:
    python3 query_kb.py --query "What do you know about CAKE?"
    python3 query_kb.py --ticker CAKE

Delegates to the generic gradient-knowledge-base and gradient-inference
skills for low-level API calls; this module adds the financial research
domain-specific RAG prompt.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

import requests

# ─── Skill imports ────────────────────────────────────────────────
# Add the generic skill script directories to sys.path so we can
# import from them without installing as packages.
# __file__ is .../skills/gradient-research-assistant/scripts/query_kb.py
# parent = scripts/, parent.parent = gradient-research-assistant/, parent.parent.parent = skills/
_SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_SKILLS_ROOT / "gradient-knowledge-base" / "scripts"))
sys.path.insert(0, str(_SKILLS_ROOT / "gradient-inference" / "scripts"))

import gradient_kb_query
import gradient_chat

# ─── Constants (frozen — tests import these) ─────────────────────
GRADIENT_INFERENCE_URL = "https://inference.do-ai.run/v1/chat/completions"
KB_RETRIEVE_URL = "https://kbaas.do-ai.run/v1"
DO_API_BASE = "https://api.digitalocean.com"


def query_knowledge_base(
    query: str,
    kb_uuid: Optional[str] = None,
    api_token: Optional[str] = None,
) -> dict:
    """Query the Gradient Knowledge Base for research documents.

    Delegates to gradient_kb_query.query_kb() from the generic KB skill.

    Args:
        query: The search query
        kb_uuid: Knowledge Base UUID
        api_token: DO personal access token

    Returns:
        dict with 'success', 'results', and 'message'
    """
    return gradient_kb_query.query_kb(query, kb_uuid=kb_uuid, api_token=api_token)


def build_rag_prompt(query: str, kb_results: list[dict]) -> str:
    """Build a RAG-enhanced prompt combining the user's question with KB context.

    This is the financial-research-specific version — emphasizes ticker
    analysis, dates, and watchlist awareness.

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
    model: str = "openai-gpt-oss-120b",
    kb_uuid: Optional[str] = None,
    api_key: Optional[str] = None,
    api_token: Optional[str] = None,
) -> dict:
    """Run a RAG-enhanced query: KB search → LLM synthesis.

    Delegates KB retrieval to gradient_kb_query and LLM call to
    gradient_chat, while using this module's financial-research-specific
    build_rag_prompt().

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

    # Step 1: Query the Knowledge Base (via generic skill)
    kb_result = gradient_kb_query.query_kb(query, kb_uuid=kb_uuid, api_token=api_token)
    kb_results = kb_result.get("results", [])

    # Step 2: Build domain-specific RAG prompt
    prompt = build_rag_prompt(query, kb_results)

    # Step 3: Call LLM for synthesis (via generic skill)
    llm_result = gradient_chat.chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful financial research assistant."},
            {"role": "user", "content": prompt},
        ],
        model=model,
        api_key=api_key,
        temperature=0.4,
        max_tokens=1500,
    )

    if not llm_result["success"]:
        return {
            "success": False,
            "answer": "",
            "sources_count": len(kb_results),
            "message": f"LLM synthesis failed: {llm_result['message']}",
        }

    return {
        "success": True,
        "answer": llm_result["content"],
        "sources_count": len(kb_results),
        "kb_success": kb_result["success"],
        "message": f"Answered using {len(kb_results)} sources from the Knowledge Base.",
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
