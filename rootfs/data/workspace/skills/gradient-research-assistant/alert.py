#!/usr/bin/env python3
"""
Alert formatting for the Gradient Research Assistant.

Formats analysis results into user-friendly Telegram messages
that OpenClaw delivers proactively.

Usage:
    Called programmatically from the heartbeat cycle, not directly.
"""

import json
from typing import Optional


def format_alert_message(
    ticker: str,
    company_name: str,
    analysis: dict,
) -> str:
    """Format an analysis result as a proactive alert message.

    Args:
        ticker: Stock ticker symbol
        company_name: Full company name
        analysis: The result dict from analyze_ticker()

    Returns:
        Human-readable alert message string
    """
    score = analysis.get("significance_score", 0)
    summary = analysis.get("summary", "No summary available.")
    reasons = analysis.get("alert_reasons", [])
    action = analysis.get("recommended_action", "")
    model = analysis.get("model_used", "unknown")
    pass_type = analysis.get("pass", "initial")

    # Severity emoji
    if score >= 8:
        severity = "🔴"
    elif score >= 6:
        severity = "🟡"
    else:
        severity = "🟢"

    lines = []
    lines.append(f"{severity} **Alert: ${ticker}** ({company_name})")
    lines.append(f"Significance: **{score}/10**")
    lines.append("")
    lines.append(f"📋 **Summary:** {summary}")
    lines.append("")

    if reasons:
        lines.append("🎯 **Why I'm alerting you:**")
        for reason in reasons:
            lines.append(f"  • {reason}")
        lines.append("")

    if action:
        lines.append(f"💡 **Recommended action:** {action}")
        lines.append("")

    # Additional deep analysis info
    market_context = analysis.get("market_context")
    if market_context:
        lines.append(f"🌍 **Market context:** {market_context}")
        lines.append("")

    risks = analysis.get("risks", [])
    if risks:
        lines.append("⚠️ **Risks to consider:**")
        for risk in risks:
            lines.append(f"  • {risk}")
        lines.append("")

    # Footer with metadata
    analysis_type = "Deep analysis" if pass_type == "deep" else "Quick scan"
    lines.append(f"_({analysis_type} via {model})_")
    lines.append("")
    lines.append("👉 Ask me for a **deep dive** on this ticker for more details.")

    return "\n".join(lines)


def format_heartbeat_summary(results: list[dict]) -> str:
    """Format a summary of the entire heartbeat cycle.

    Args:
        results: List of analysis results for all tickers

    Returns:
        Summary message string
    """
    if not results:
        return "💤 Heartbeat complete. No tickers to check."

    alerts = [r for r in results if r.get("should_alert")]
    ok = [r for r in results if not r.get("should_alert")]

    lines = []
    lines.append(f"💓 **Heartbeat Complete** — checked {len(results)} tickers")
    lines.append("")

    if alerts:
        lines.append(f"🚨 **{len(alerts)} alert(s) triggered:**")
        for r in alerts:
            ticker = r.get("ticker", "?")
            score = r.get("significance_score", 0)
            lines.append(f"  • ${ticker}: {score}/10")
    else:
        lines.append("✅ All clear — no significant events detected.")

    if ok:
        lines.append("")
        lines.append(f"😴 {len(ok)} ticker(s) quiet: {', '.join('$' + r.get('ticker', '?') for r in ok)}")

    return "\n".join(lines)


def should_alert(analysis: dict, threshold: int = 6) -> bool:
    """Determine whether an analysis result should trigger an alert.

    Args:
        analysis: The analysis result dict
        threshold: Minimum significance score to alert

    Returns:
        True if the user should be alerted
    """
    if not analysis.get("success", False):
        return False

    score = analysis.get("significance_score", 0)
    return score >= threshold
