#!/usr/bin/env python3
"""
Analysis engine for the Gradient Research Assistant.

Calls Gradient Serverless Inference to analyze gathered research data,
score significance, and determine whether to alert the user.

Uses a two-pass model routing strategy:
- Pass 1: Cheap model (e.g., qwen3-32b) for initial significance scoring
- Pass 2: Strong model (e.g., claude-sonnet-4-5-20250514) if score > threshold (deep analysis)

Usage:
    python3 analyze.py --ticker CAKE --data /path/to/research.md --verbose
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import requests

# Gradient AI inference endpoint
GRADIENT_INFERENCE_URL = "https://inference.do-ai.run/v1/chat/completions"

# Default models (can be overridden via watchlist global_settings)
DEFAULT_CHEAP_MODEL = "qwen3-32b"
DEFAULT_STRONG_MODEL = "claude-sonnet-4-5-20250514"

# Score threshold for triggering the second pass
DEEP_ANALYSIS_THRESHOLD = 5


def build_analysis_prompt(ticker: str, company_name: str, research_md: str, rules: dict) -> str:
    """Build the analysis prompt for the LLM.

    Args:
        ticker: Stock ticker symbol
        company_name: Full company name
        research_md: The Markdown research report to analyze
        rules: Effective alert rules for this ticker

    Returns:
        The formatted prompt string
    """
    rules_text = "\n".join(f"  - {k}: {v}" for k, v in sorted(rules.items()))

    return f"""You are a financial research analyst assistant. Analyze the following research data 
for {ticker} ({company_name}) and determine its significance.

## Alert Rules (what the user wants to be notified about):
{rules_text}

## Research Data:
{research_md}

## Your Task:
1. Analyze the research data above
2. Score its significance on a scale of 1–10 based on the alert rules
3. Provide a brief summary of key findings
4. Recommend whether to alert the user

## Response Format (JSON):
{{
  "significance_score": <1-10>,
  "summary": "<2-3 sentence summary of key findings>",
  "alert_reasons": ["<reason 1>", "<reason 2>"],
  "should_alert": <true/false>,
  "recommended_action": "<what the user should consider doing>"
}}

Respond ONLY with valid JSON, no markdown code fences or extra text."""


def build_deep_analysis_prompt(ticker: str, company_name: str, research_md: str, initial_analysis: dict) -> str:
    """Build the deep analysis prompt for the strong model (second pass).

    Args:
        ticker: Stock ticker symbol
        company_name: Full company name
        research_md: The Markdown research report
        initial_analysis: The result from the first pass

    Returns:
        The formatted prompt string
    """
    return f"""You are a senior financial research analyst. A junior analyst flagged {ticker} ({company_name})
as potentially significant (score: {initial_analysis.get('significance_score', 'N/A')}/10).

## Junior Analyst's Assessment:
{json.dumps(initial_analysis, indent=2)}

## Full Research Data:
{research_md}

## Your Task:
Provide a deeper analysis. Consider:
- Is the junior analyst's significance score justified?
- What broader market context should the user be aware of?
- Are there any risks or nuances the initial analysis missed?
- What specific action should the user consider?

## Response Format (JSON):
{{
  "significance_score": <1-10, your revised assessment>,
  "summary": "<3-5 sentence deep analysis>",
  "alert_reasons": ["<reason 1>", "<reason 2>"],
  "should_alert": <true/false>,
  "recommended_action": "<specific, actionable recommendation>",
  "market_context": "<broader context>",
  "risks": ["<risk 1>", "<risk 2>"]
}}

Respond ONLY with valid JSON, no markdown code fences or extra text."""


def parse_llm_response(response_text: str) -> Optional[dict]:
    """Parse the LLM's JSON response, handling common formatting issues.

    Returns:
        Parsed dict, or None if parsing fails.
    """
    text = response_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def call_gradient_inference(prompt: str, model: str, api_key: str) -> Optional[str]:
    """Call Gradient Serverless Inference API.

    Args:
        prompt: The prompt text
        model: Model identifier (e.g., 'qwen3-32b')
        api_key: Gradient API key

    Returns:
        The model's response text, or None on failure.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a financial research analyst. Always respond with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    try:
        resp = requests.post(
            GRADIENT_INFERENCE_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, Exception):
        return None


def analyze_ticker(
    ticker: str,
    company_name: str,
    research_md: str,
    rules: dict,
    global_settings: dict,
    api_key: Optional[str] = None,
) -> dict:
    """Run the full analysis pipeline for a ticker.

    Two-pass strategy:
    1. Quick analysis with cheap model
    2. If significance > threshold, deep analysis with strong model

    Args:
        ticker: Stock ticker symbol
        company_name: Full company name
        research_md: The Markdown research report
        rules: Effective alert rules for this ticker
        global_settings: Global settings (models, thresholds)
        api_key: Gradient API key (defaults to env var)

    Returns:
        dict with analysis results including significance_score,
        summary, should_alert, and model_used.
    """
    api_key = api_key or os.environ.get("GRADIENT_API_KEY", "")
    if not api_key:
        return {
            "success": False,
            "error": "No GRADIENT_API_KEY found. Set the environment variable or pass api_key.",
            "significance_score": 0,
            "should_alert": False,
        }

    cheap_model = global_settings.get("cheap_model", DEFAULT_CHEAP_MODEL)
    strong_model = global_settings.get("strong_model", DEFAULT_STRONG_MODEL)
    threshold = global_settings.get("significance_threshold", 6)

    # Pass 1: Quick analysis with cheap model
    prompt = build_analysis_prompt(ticker, company_name, research_md, rules)
    response_text = call_gradient_inference(prompt, cheap_model, api_key)

    if response_text is None:
        return {
            "success": False,
            "error": f"Failed to get response from {cheap_model}",
            "significance_score": 0,
            "should_alert": False,
        }

    initial = parse_llm_response(response_text)
    if initial is None:
        return {
            "success": False,
            "error": "Failed to parse LLM response as JSON",
            "raw_response": response_text,
            "significance_score": 0,
            "should_alert": False,
        }

    initial["model_used"] = cheap_model
    initial["pass"] = "initial"
    initial["success"] = True

    score = initial.get("significance_score", 0)

    # Pass 2: If score warrants it, run deep analysis
    if score >= DEEP_ANALYSIS_THRESHOLD:
        deep_prompt = build_deep_analysis_prompt(ticker, company_name, research_md, initial)
        deep_response = call_gradient_inference(deep_prompt, strong_model, api_key)

        if deep_response:
            deep_result = parse_llm_response(deep_response)
            if deep_result:
                deep_result["model_used"] = strong_model
                deep_result["pass"] = "deep"
                deep_result["initial_analysis"] = initial
                deep_result["success"] = True
                # Final decision uses deep analysis score and threshold
                deep_result["should_alert"] = deep_result.get("significance_score", 0) >= threshold
                return deep_result

    # Use initial analysis result
    initial["should_alert"] = score >= threshold
    return initial


# ─── CLI Interface ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Analyze research data for a ticker")
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--name", default="", help="Company name")
    parser.add_argument("--data", required=True, help="Path to research Markdown file")
    parser.add_argument("--verbose", action="store_true", help="Show full analysis output")

    args = parser.parse_args()
    ticker = args.ticker.upper().lstrip("$")

    research_md = Path(args.data).read_text()

    # Load watchlist for rules and settings
    watchlist_path = Path(__file__).parent / "watchlist.json"
    if watchlist_path.exists():
        import manage_watchlist
        watchlist = manage_watchlist.load_watchlist(str(watchlist_path))
        rules = manage_watchlist.get_effective_rules(watchlist, ticker) or watchlist.get("default_rules", {})
        global_settings = watchlist.get("global_settings", {})
    else:
        rules = {}
        global_settings = {}

    result = analyze_ticker(ticker, args.name or ticker, research_md, rules, global_settings)

    if args.verbose:
        print(json.dumps(result, indent=2))
    else:
        score = result.get("significance_score", 0)
        alert = "🚨 ALERT" if result.get("should_alert") else "✅ OK"
        print(f"[{alert}] {ticker}: {score}/10 — {result.get('summary', 'No summary')}")


if __name__ == "__main__":
    main()
