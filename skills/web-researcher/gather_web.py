#!/usr/bin/env python3
"""
Web data gathering for Nova (Web Researcher).

Fetches public data for a given stock ticker from:
- Google News (RSS feeds)
- SEC EDGAR (full-text search API)

Extracted from the original gather.py for the multi-agent architecture.
News + SEC are Nova's domain; Reddit remains in gather.py for Phase 2 (Pixel).

Usage:
    python3 gather_web.py --ticker BNTX --once
    python3 gather_web.py --ticker BNTX --theme "mRNA cancer research"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import feedparser
import requests

# ─── User-Agent for polite scraping ───────────────────────────────

USER_AGENT = "GradientResearchAssistant/1.0 (demo; +https://github.com/Rogue-Iteration/TheBigClaw)"
HEADERS = {"User-Agent": USER_AGENT}

# SEC EDGAR requires a specific user agent with contact info
SEC_HEADERS = {
    "User-Agent": "GradientResearchAssistant demo@example.com",
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 15


# ─── News (Google News RSS) ──────────────────────────────────────


def parse_news_rss(rss_text: str) -> list[dict]:
    """Parse an RSS feed and extract news items.

    Returns:
        List of dicts with keys: title, link, published, summary, source
    """
    try:
        feed = feedparser.parse(rss_text)
    except Exception:
        return []

    items = []
    for entry in feed.get("entries", []):
        items.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "summary": entry.get("summary", entry.get("description", "")),
            "source": entry.get("source", {}).get("title", "") if isinstance(entry.get("source"), dict) else "",
        })

    return items


def format_news_markdown(ticker: str, items: list[dict]) -> str:
    """Format news items as a Markdown section."""
    lines = [f"# News: {ticker}", ""]

    if not items:
        lines.append("No recent news found.")
        return "\n".join(lines)

    for item in items:
        lines.append(f"## {item['title']}")
        if item.get("source"):
            lines.append(f"*Source: {item['source']}*")
        if item.get("published"):
            lines.append(f"*Published: {item['published']}*")
        lines.append("")
        if item.get("summary"):
            lines.append(item["summary"])
        if item.get("link"):
            lines.append(f"\n[Read more]({item['link']})")
        lines.append("")

    return "\n".join(lines)


def fetch_news(
    ticker: str,
    theme: Optional[str] = None,
    directive: Optional[str] = None,
) -> list[dict]:
    """Fetch news for a ticker from Google News RSS.

    When a theme is provided, it's appended to the search query
    to focus results on the ticker's research theme.

    Returns parsed items or empty list on failure.
    """
    url = "https://news.google.com/rss/search"

    # Build search query — include theme if available
    query = f"{ticker} stock"
    if theme:
        query = f"{ticker} {theme}"

    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return parse_news_rss(resp.text)
    except (requests.RequestException, Exception):
        return []


# ─── SEC EDGAR ────────────────────────────────────────────────────


def parse_sec_filings(data: dict) -> list[dict]:
    """Parse SEC EDGAR search results into structured filings.

    Returns:
        List of dicts with keys: form_type, file_date, description, url,
        company, period
    """
    try:
        hits = data.get("hits", {}).get("hits", [])
    except (AttributeError, TypeError):
        return []

    filings = []
    for hit in hits:
        source = hit.get("_source", {})
        if not source:
            continue

        companies = source.get("display_names", [])
        company = companies[0] if companies else ""

        filings.append({
            "form_type": source.get("form_type", ""),
            "file_date": source.get("file_date", ""),
            "description": source.get("file_description", ""),
            "url": source.get("file_url", ""),
            "company": company,
            "period": source.get("period_of_report", ""),
        })

    return filings


def format_sec_markdown(ticker: str, filings: list[dict]) -> str:
    """Format SEC filings as a Markdown section."""
    lines = [f"# SEC Filings: {ticker}", ""]

    if not filings:
        lines.append("No recent SEC filings found.")
        return "\n".join(lines)

    for filing in filings:
        form_type = filing["form_type"]
        desc = filing.get("description", "")
        lines.append(f"## {form_type}{f' — {desc}' if desc else ''}")
        lines.append(f"*Filed: {filing.get('file_date', 'N/A')} | Period: {filing.get('period', 'N/A')}*")
        if filing.get("company"):
            lines.append(f"*Company: {filing['company']}*")
        if filing.get("url"):
            lines.append(f"\n[View Filing]({filing['url']})")
        lines.append("")

    return "\n".join(lines)


def fetch_sec_filings(ticker: str) -> list[dict]:
    """Fetch recent SEC filings for a ticker from EDGAR.

    Uses the free full-text search API.
    Returns parsed filings or empty list on failure.
    """
    url = "https://efts.sec.gov/LATEST/search-index"
    params = {
        "q": ticker,
        "dateRange": "custom",
        "startdt": "2025-01-01",
        "enddt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "forms": "10-K,10-Q,8-K,4",
    }

    try:
        resp = requests.get(url, params=params, headers=SEC_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return parse_sec_filings(resp.json())
    except (requests.RequestException, json.JSONDecodeError, Exception):
        return []


# ─── Combined Web Gather ─────────────────────────────────────────


def gather_web(
    ticker: str,
    company_name: str,
    theme: Optional[str] = None,
    directive: Optional[str] = None,
) -> dict:
    """Gather web data (news + SEC) for a ticker.

    This is Nova's primary entry point — news and SEC filings only.
    Reddit/social data is handled by Pixel (Phase 2).

    Args:
        ticker: Stock ticker symbol
        company_name: Full company name
        theme: Optional research theme (e.g., "mRNA cancer research")
        directive: Optional research directive (e.g., "Focus on clinical trials")

    Returns:
        dict with keys:
        - ticker: the symbol
        - company: the company name
        - timestamp: ISO timestamp of the gather
        - markdown: the combined Markdown report
        - sources: dict with raw parsed data from each source
        - theme: the research theme (if any)
        - directive: the research directive (if any)
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Fetch from web sources (failures return empty lists)
    news = fetch_news(ticker, theme=theme, directive=directive)
    sec = fetch_sec_filings(ticker)

    # Format each section
    news_md = format_news_markdown(ticker, news)
    sec_md = format_sec_markdown(ticker, sec)

    # Build header with theme/directive context
    header = f"# Research Report: {ticker} — {company_name}\n*Generated: {timestamp}*"
    if theme:
        header += f"\n*Research Theme: {theme}*"
    if directive:
        header += f"\n*Directive: {directive}*"

    # Combine into one document
    combined = f"""{header}

---

{news_md}

---

{sec_md}
"""

    return {
        "ticker": ticker,
        "company": company_name,
        "timestamp": timestamp,
        "markdown": combined,
        "sources": {
            "news": news,
            "sec": sec,
        },
        "theme": theme,
        "directive": directive,
    }


# ─── CLI Interface ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Gather web research data for a ticker (Nova)")
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--name", default="", help="Company name")
    parser.add_argument("--theme", default=None, help="Research theme to focus on")
    parser.add_argument("--directive", default=None, help="Research directive")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")

    args = parser.parse_args()
    ticker = args.ticker.upper().lstrip("$")
    name = args.name or ticker

    result = gather_web(ticker, name, theme=args.theme, directive=args.directive)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result["markdown"])
        print(f"Research saved to {args.output}")
    else:
        print(result["markdown"])

    # Summary stats
    news_count = len(result["sources"]["news"])
    sec_count = len(result["sources"]["sec"])
    print(f"\n📰 Nova gathered: {news_count} news articles, {sec_count} SEC filings",
          file=sys.stderr)


if __name__ == "__main__":
    main()
