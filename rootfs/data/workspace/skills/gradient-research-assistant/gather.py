#!/usr/bin/env python3
"""
Data gathering for the Gradient Research Assistant.

Fetches public data for a given stock ticker from:
- Google News (RSS feeds)
- Reddit (public JSON API)
- SEC EDGAR (full-text search API)

All sources are free and rate-limited. Designed for demo frequency
(every 30 min for 5 tickers), not high-frequency data.

Usage:
    python3 gather.py --ticker CAKE --once
    python3 gather.py --ticker CAKE --output /path/to/output.md
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests

# ─── User-Agent for polite scraping ───────────────────────────────

USER_AGENT = "GradientResearchAssistant/1.0 (demo; +https://github.com/Rogue-Iteration/openclaw-do-gradient)"
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


def fetch_news(ticker: str) -> list[dict]:
    """Fetch news for a ticker from Google News RSS.

    Returns parsed items or empty list on failure.
    """
    url = "https://news.google.com/rss/search"
    params = {"q": f"{ticker} stock", "hl": "en-US", "gl": "US", "ceid": "US:en"}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return parse_news_rss(resp.text)
    except (requests.RequestException, Exception):
        return []


# ─── Reddit ───────────────────────────────────────────────────────


def parse_reddit_posts(data: dict) -> list[dict]:
    """Parse Reddit listing JSON into structured posts.

    Returns:
        List of dicts with keys: title, text, author, score, comments,
        subreddit, url
    """
    try:
        children = data.get("data", {}).get("children", [])
    except (AttributeError, TypeError):
        return []

    posts = []
    for child in children:
        post_data = child.get("data", {})
        if not post_data:
            continue
        posts.append({
            "title": post_data.get("title", ""),
            "text": post_data.get("selftext", ""),
            "author": post_data.get("author", "[deleted]"),
            "score": post_data.get("score", 0),
            "comments": post_data.get("num_comments", 0),
            "subreddit": post_data.get("subreddit", ""),
            "url": f"https://www.reddit.com{post_data.get('permalink', '')}",
        })

    return posts


def format_reddit_markdown(ticker: str, posts: list[dict]) -> str:
    """Format Reddit posts as a Markdown section."""
    lines = [f"# Reddit: {ticker}", ""]

    if not posts:
        lines.append("No recent Reddit discussions found.")
        return "\n".join(lines)

    for post in posts:
        lines.append(f"## {post['title']}")
        lines.append(f"*r/{post['subreddit']} | ⬆ {post['score']} | 💬 {post['comments']} | u/{post['author']}*")
        lines.append("")
        if post.get("text"):
            # Truncate long posts
            text = post["text"][:500]
            if len(post["text"]) > 500:
                text += "..."
            lines.append(text)
        lines.append(f"\n[View on Reddit]({post['url']})")
        lines.append("")

    return "\n".join(lines)


def fetch_reddit(ticker: str) -> list[dict]:
    """Fetch Reddit posts mentioning a ticker.

    Uses Reddit's public JSON search endpoint (no auth required).
    Returns parsed posts or empty list on failure.
    """
    url = "https://www.reddit.com/search.json"
    params = {
        "q": f"${ticker} OR {ticker} stock",
        "sort": "relevance",
        "t": "week",
        "limit": 10,
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return parse_reddit_posts(resp.json())
    except (requests.RequestException, json.JSONDecodeError, Exception):
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


# ─── Combined Gather ─────────────────────────────────────────────


def gather_all(ticker: str, company_name: str) -> dict:
    """Gather data from all sources and produce a combined research report.

    Returns:
        dict with keys:
        - ticker: the symbol
        - company: the company name
        - timestamp: ISO timestamp of the gather
        - markdown: the combined Markdown report
        - sources: dict with raw parsed data from each source
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Fetch from all sources (failures return empty lists)
    news = fetch_news(ticker)
    reddit_posts = fetch_reddit(ticker)
    sec = fetch_sec_filings(ticker)

    # Format each section
    news_md = format_news_markdown(ticker, news)
    reddit_md = format_reddit_markdown(ticker, reddit_posts)
    sec_md = format_sec_markdown(ticker, sec)

    # Combine into one document
    combined = f"""# Research Report: {ticker} — {company_name}
*Generated: {timestamp}*

---

{news_md}

---

{reddit_md}

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
            "reddit": reddit_posts,
            "sec": sec,
        },
    }


# ─── CLI Interface ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Gather research data for a ticker")
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--name", default="", help="Company name")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")

    args = parser.parse_args()
    ticker = args.ticker.upper().lstrip("$")
    name = args.name or ticker

    result = gather_all(ticker, name)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result["markdown"])
        print(f"Research saved to {args.output}")
    else:
        print(result["markdown"])

    # Summary stats
    news_count = len(result["sources"]["news"])
    reddit_count = len(result["sources"]["reddit"])
    sec_count = len(result["sources"]["sec"])
    print(f"\n📊 Gathered: {news_count} news articles, {reddit_count} Reddit posts, {sec_count} SEC filings",
          file=sys.stderr)


if __name__ == "__main__":
    main()
