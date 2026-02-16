#!/usr/bin/env python3
"""
Fundamental data gathering for Max (Fundamental Analyst).

Fetches structured financial data for a given stock ticker from:
- SEC EDGAR XBRL API (companyfacts) — audited financials from 10-K/10-Q filings
- yfinance — supplementary company info, analyst recommendations, earnings history

Provides:
- Income statement metrics (revenue, net income, EPS, gross/operating profit)
- Balance sheet metrics (assets, liabilities, equity, cash, debt)
- Cash flow metrics (operating cash flow, capex, free cash flow)
- Company overview (sector, industry, market cap, description)
- Analyst recommendations and earnings beat/miss history

Usage:
    python3 gather_fundamentals.py --ticker CAKE --company "The Cheesecake Factory"
    python3 gather_fundamentals.py --ticker BNTX --json
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests
import yfinance as yf

# ─── Constants ────────────────────────────────────────────────────

# SEC EDGAR requires a User-Agent with contact info
SEC_HEADERS = {
    "User-Agent": "GradientResearchAssistant demo@example.com",
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 15

# Cache the ticker→CIK mapping to avoid re-fetching
_CIK_CACHE: dict[str, str] = {}

# US-GAAP concepts to extract, organized by category.
# For each metric, we try multiple concept names since companies vary.
INCOME_CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "cost_of_revenue": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
    "eps_basic": [
        "EarningsPerShareBasic",
    ],
    "eps_diluted": [
        "EarningsPerShareDiluted",
    ],
}

BALANCE_SHEET_CONCEPTS = {
    "total_assets": [
        "Assets",
    ],
    "total_liabilities": [
        "Liabilities",
    ],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
    ],
    "long_term_debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
    ],
    "short_term_debt": [
        "ShortTermBorrowings",
        "DebtCurrent",
    ],
    "current_assets": [
        "AssetsCurrent",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
    ],
    "shares_outstanding": [
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
    ],
}

CASH_FLOW_CONCEPTS = {
    "operating_cash_flow": [
        "NetCashProvidedByOperatingActivities",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "dividends_paid": [
        "PaymentsOfDividends",
        "PaymentsOfDividendsCommonStock",
    ],
}


# ─── SEC EDGAR: CIK Resolution ──────────────────────────────────


def resolve_cik(ticker: str) -> Optional[str]:
    """Look up a company's CIK number by ticker symbol.

    Uses the SEC's public company_tickers.json file.
    Returns CIK as a zero-padded 10-digit string, or None if not found.
    """
    global _CIK_CACHE

    ticker_upper = ticker.upper()
    if ticker_upper in _CIK_CACHE:
        return _CIK_CACHE[ticker_upper]

    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=SEC_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        # Build full cache while we have the data
        for entry in data.values():
            t = entry.get("ticker", "").upper()
            cik = str(entry.get("cik_str", "")).zfill(10)
            _CIK_CACHE[t] = cik

        return _CIK_CACHE.get(ticker_upper)

    except (requests.RequestException, json.JSONDecodeError, Exception) as e:
        print(f"Warning: CIK lookup failed: {e}", file=sys.stderr)
        return None


# ─── SEC EDGAR: XBRL Company Facts ──────────────────────────────


def fetch_company_facts(cik: str) -> Optional[dict]:
    """Fetch all XBRL company facts from SEC EDGAR.

    This is the motherlode — every financial fact the company has ever
    reported to the SEC, organized by taxonomy and concept name.

    Args:
        cik: Zero-padded 10-digit CIK number

    Returns:
        Full companyfacts JSON dict, or None on failure
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, json.JSONDecodeError, Exception) as e:
        print(f"Warning: EDGAR companyfacts failed for CIK {cik}: {e}", file=sys.stderr)
        return None


def _extract_concept_data(
    facts: dict,
    concept_names: list[str],
    years: int = 5,
) -> list[dict]:
    """Extract time-series data for a financial concept.

    Tries each concept name in order until one returns data.
    Filters to the most recent `years` worth of 10-K/10-Q filings.

    Returns:
        List of dicts with: value, end_date, form, filed, fiscal_year, fiscal_period
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    for concept_name in concept_names:
        concept = us_gaap.get(concept_name, {})
        units = concept.get("units", {})

        # Financial data can be in USD, USD/shares, or pure (shares)
        for unit_type in ["USD", "USD/shares", "shares", "pure"]:
            entries = units.get(unit_type, [])
            if not entries:
                continue

            # Calculate cutoff date
            cutoff_year = datetime.now().year - years

            # Filter to 10-K and 10-Q filings within the time range
            results = []
            for entry in entries:
                form = entry.get("form", "")
                if form not in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
                    continue

                end_date = entry.get("end", "")
                if not end_date:
                    continue

                try:
                    end_year = int(end_date[:4])
                except (ValueError, IndexError):
                    continue

                if end_year < cutoff_year:
                    continue

                results.append({
                    "value": entry.get("val"),
                    "end_date": end_date,
                    "form": form,
                    "filed": entry.get("filed", ""),
                    "fiscal_year": entry.get("fy"),
                    "fiscal_period": entry.get("fp", ""),
                })

            if results:
                # Sort by end_date and deduplicate (keep latest filing per period)
                results.sort(key=lambda x: x["end_date"])
                seen = set()
                deduped = []
                for r in results:
                    key = (r["end_date"], r["form"].replace("/A", ""))
                    if key not in seen:
                        seen.add(key)
                        deduped.append(r)
                return deduped

    return []


def extract_financials(facts: dict, years: int = 5) -> dict:
    """Extract key financial metrics from XBRL company facts.

    Args:
        facts: Full companyfacts JSON from SEC EDGAR
        years: Number of years of history to extract

    Returns:
        dict organized by category (income, balance_sheet, cash_flow),
        each containing metric names mapped to time-series data
    """
    if not facts:
        return {"income": {}, "balance_sheet": {}, "cash_flow": {}}

    result = {
        "income": {},
        "balance_sheet": {},
        "cash_flow": {},
    }

    # Extract income statement metrics
    for metric_name, concept_names in INCOME_CONCEPTS.items():
        data = _extract_concept_data(facts, concept_names, years)
        if data:
            result["income"][metric_name] = data

    # Extract balance sheet metrics
    for metric_name, concept_names in BALANCE_SHEET_CONCEPTS.items():
        data = _extract_concept_data(facts, concept_names, years)
        if data:
            result["balance_sheet"][metric_name] = data

    # Extract cash flow metrics
    for metric_name, concept_names in CASH_FLOW_CONCEPTS.items():
        data = _extract_concept_data(facts, concept_names, years)
        if data:
            result["cash_flow"][metric_name] = data

    return result


# ─── yfinance Supplementary Data ─────────────────────────────────


def fetch_yfinance_supplementary(ticker: str) -> dict:
    """Fetch supplementary data from yfinance.

    Provides company info, analyst recommendations, and earnings history
    that complement the raw SEC filings.

    Returns:
        dict with keys: info, recommendations, earnings_history
    """
    result = {
        "info": {},
        "recommendations": [],
        "earnings_history": [],
    }

    try:
        stock = yf.Ticker(ticker)

        # Company info
        try:
            raw_info = stock.info
            result["info"] = {
                "name": raw_info.get("shortName", ticker),
                "long_name": raw_info.get("longName", ""),
                "sector": raw_info.get("sector", ""),
                "industry": raw_info.get("industry", ""),
                "market_cap": raw_info.get("marketCap"),
                "enterprise_value": raw_info.get("enterpriseValue"),
                "trailing_pe": raw_info.get("trailingPE"),
                "forward_pe": raw_info.get("forwardPE"),
                "price_to_book": raw_info.get("priceToBook"),
                "dividend_yield": raw_info.get("dividendYield"),
                "beta": raw_info.get("beta"),
                "52_week_high": raw_info.get("fiftyTwoWeekHigh"),
                "52_week_low": raw_info.get("fiftyTwoWeekLow"),
                "description": raw_info.get("longBusinessSummary", ""),
            }
        except Exception:
            pass

        # Analyst recommendations
        try:
            recs = stock.recommendations
            if recs is not None and not recs.empty:
                # Take the most recent recommendations
                recent = recs.tail(10)
                for _, row in recent.iterrows():
                    rec = {}
                    for col in recent.columns:
                        val = row[col]
                        # Convert numpy types to native Python
                        if hasattr(val, "item"):
                            val = val.item()
                        rec[col] = val
                    result["recommendations"].append(rec)
        except Exception:
            pass

        # Earnings history (EPS beat/miss)
        try:
            earnings = stock.earnings_history
            if earnings is not None and not earnings.empty:
                for _, row in earnings.iterrows():
                    entry = {}
                    for col in earnings.columns:
                        val = row[col]
                        if hasattr(val, "item"):
                            val = val.item()
                        elif hasattr(val, "isoformat"):
                            val = val.isoformat()
                        entry[col] = val
                    result["earnings_history"].append(entry)
        except Exception:
            pass

    except Exception as e:
        print(f"Warning: yfinance supplementary data failed for {ticker}: {e}", file=sys.stderr)

    return result


# ─── Markdown Formatting ─────────────────────────────────────────


def _format_number(value, prefix: str = "$", suffix: str = "") -> str:
    """Format a number for display (e.g., $1.2B, $340.5M)."""
    if value is None:
        return "N/A"

    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)

    negative = v < 0
    v = abs(v)

    if v >= 1e12:
        formatted = f"{v / 1e12:.1f}T"
    elif v >= 1e9:
        formatted = f"{v / 1e9:.1f}B"
    elif v >= 1e6:
        formatted = f"{v / 1e6:.1f}M"
    elif v >= 1e3:
        formatted = f"{v / 1e3:.1f}K"
    else:
        formatted = f"{v:.2f}"

    sign = "-" if negative else ""
    return f"{sign}{prefix}{formatted}{suffix}"


def _get_latest_value(data_points: list[dict], form_filter: str = "10-K") -> Optional[dict]:
    """Get the most recent data point, optionally filtered by form type."""
    if not data_points:
        return None

    # Try the specific form first
    filtered = [d for d in data_points if d["form"].replace("/A", "") == form_filter]
    if filtered:
        return filtered[-1]

    # Fall back to any form
    return data_points[-1]


def _format_trend(data_points: list[dict], form_filter: str = "10-K") -> str:
    """Format a simple trend arrow based on annual values."""
    filtered = [d for d in data_points if d["form"].replace("/A", "") == form_filter]
    if len(filtered) < 2:
        return ""

    prev_val = filtered[-2].get("value")
    curr_val = filtered[-1].get("value")

    if prev_val is None or curr_val is None:
        return ""

    try:
        prev_val = float(prev_val)
        curr_val = float(curr_val)
    except (TypeError, ValueError):
        return ""

    if prev_val == 0:
        return ""

    pct_change = (curr_val - prev_val) / abs(prev_val) * 100
    arrow = "📈" if pct_change > 0 else "📉" if pct_change < 0 else "➡️"
    return f" {arrow} {pct_change:+.1f}% YoY"


def format_fundamentals_markdown(
    ticker: str,
    financials: dict,
    supplementary: dict,
) -> str:
    """Format fundamental data as a Markdown report."""
    lines = [f"# Fundamental Analysis: ${ticker}", ""]

    income = financials.get("income", {})
    balance = financials.get("balance_sheet", {})
    cash_flow = financials.get("cash_flow", {})
    info = supplementary.get("info", {})

    # ── Company Overview ──
    if info:
        lines.append("## Company Overview")
        lines.append("")
        if info.get("long_name"):
            lines.append(f"**{info['long_name']}**")
        if info.get("sector") or info.get("industry"):
            parts = []
            if info.get("sector"):
                parts.append(info["sector"])
            if info.get("industry"):
                parts.append(info["industry"])
            lines.append(f"*{' — '.join(parts)}*")
        lines.append("")

        if info.get("market_cap"):
            lines.append(f"- **Market Cap**: {_format_number(info['market_cap'])}")
        if info.get("enterprise_value"):
            lines.append(f"- **Enterprise Value**: {_format_number(info['enterprise_value'])}")
        if info.get("trailing_pe"):
            lines.append(f"- **P/E (Trailing)**: {info['trailing_pe']:.1f}")
        if info.get("forward_pe"):
            lines.append(f"- **P/E (Forward)**: {info['forward_pe']:.1f}")
        if info.get("price_to_book"):
            lines.append(f"- **P/B**: {info['price_to_book']:.2f}")
        if info.get("dividend_yield"):
            lines.append(f"- **Dividend Yield**: {info['dividend_yield']:.2%}")
        if info.get("beta"):
            lines.append(f"- **Beta**: {info['beta']:.2f}")
        if info.get("52_week_high") and info.get("52_week_low"):
            lines.append(f"- **52-Week Range**: ${info['52_week_low']:.2f} — ${info['52_week_high']:.2f}")
        lines.append("")

        if info.get("description"):
            # Truncate long descriptions
            desc = info["description"]
            if len(desc) > 500:
                desc = desc[:500] + "..."
            lines.append(f"> {desc}")
            lines.append("")

    # ── Income Statement ──
    if income:
        lines.append("## Income Statement (from SEC filings)")
        lines.append("")

        for metric, label, prefix in [
            ("revenue", "Revenue", "$"),
            ("gross_profit", "Gross Profit", "$"),
            ("operating_income", "Operating Income", "$"),
            ("net_income", "Net Income", "$"),
            ("eps_diluted", "EPS (Diluted)", "$"),
        ]:
            data = income.get(metric, [])
            if not data:
                continue

            latest = _get_latest_value(data)
            if latest:
                trend = _format_trend(data)
                val = _format_number(latest["value"], prefix=prefix)
                period = f"FY{latest.get('fiscal_year', '?')}"
                lines.append(f"- **{label}**: {val} ({period}){trend}")

        # Margins (if we have the data)
        rev_data = income.get("revenue", [])
        gp_data = income.get("gross_profit", [])
        ni_data = income.get("net_income", [])
        oi_data = income.get("operating_income", [])

        margins = []
        rev_latest = _get_latest_value(rev_data)
        if rev_latest and rev_latest["value"]:
            rev_val = float(rev_latest["value"])
            if rev_val > 0:
                gp_latest = _get_latest_value(gp_data)
                if gp_latest and gp_latest["value"]:
                    gm = float(gp_latest["value"]) / rev_val * 100
                    margins.append(f"Gross: {gm:.1f}%")

                oi_latest = _get_latest_value(oi_data)
                if oi_latest and oi_latest["value"]:
                    om = float(oi_latest["value"]) / rev_val * 100
                    margins.append(f"Operating: {om:.1f}%")

                ni_latest = _get_latest_value(ni_data)
                if ni_latest and ni_latest["value"]:
                    nm = float(ni_latest["value"]) / rev_val * 100
                    margins.append(f"Net: {nm:.1f}%")

        if margins:
            lines.append(f"- **Margins**: {' | '.join(margins)}")

        lines.append("")

        # Annual history table — deduplicate by fiscal year (keep FY entries only)
        annual_data = [d for d in rev_data if d["form"].replace("/A", "") == "10-K"]
        # Prefer FY entries; if multiple entries per fiscal year, keep the one with fp="FY"
        seen_years = {}
        for d in annual_data:
            fy = d.get("fiscal_year")
            if fy is None:
                continue
            # Prefer FY period, otherwise keep the latest entry per fiscal year
            if fy not in seen_years or d.get("fiscal_period") == "FY":
                seen_years[fy] = d
        annual_data = sorted(seen_years.values(), key=lambda x: x.get("fiscal_year", 0))

        if len(annual_data) >= 2:
            lines.append("### Annual Revenue History")
            lines.append("")
            lines.append("| Fiscal Year | Revenue | Net Income | EPS |")
            lines.append("|-------------|---------|------------|-----|")
            for rev_entry in annual_data[-5:]:
                fy = f"FY{rev_entry.get('fiscal_year', '?')}"
                rev_val = _format_number(rev_entry["value"])

                # Find matching net income and EPS
                ni_val = "—"
                eps_val = "—"
                end_date = rev_entry["end_date"]

                for ni in ni_data:
                    if ni["end_date"] == end_date and ni["form"].replace("/A", "") == "10-K":
                        ni_val = _format_number(ni["value"])
                        break

                eps_data = income.get("eps_diluted", [])
                for eps in eps_data:
                    if eps["end_date"] == end_date and eps["form"].replace("/A", "") == "10-K":
                        eps_val = _format_number(eps["value"])
                        break

                lines.append(f"| {fy} | {rev_val} | {ni_val} | {eps_val} |")
            lines.append("")

    # ── Balance Sheet ──
    if balance:
        lines.append("## Balance Sheet (from SEC filings)")
        lines.append("")

        for metric, label, prefix in [
            ("total_assets", "Total Assets", "$"),
            ("total_liabilities", "Total Liabilities", "$"),
            ("stockholders_equity", "Stockholders' Equity", "$"),
            ("cash", "Cash & Equivalents", "$"),
            ("long_term_debt", "Long-Term Debt", "$"),
            ("current_assets", "Current Assets", "$"),
            ("current_liabilities", "Current Liabilities", "$"),
            ("shares_outstanding", "Shares Outstanding", ""),
        ]:
            data = balance.get(metric, [])
            if not data:
                continue

            latest = _get_latest_value(data)
            if latest:
                trend = _format_trend(data)
                val = _format_number(latest["value"], prefix=prefix)
                period = f"FY{latest.get('fiscal_year', '?')}"
                lines.append(f"- **{label}**: {val} ({period}){trend}")

        # Key ratios
        ratios = []
        assets = _get_latest_value(balance.get("total_assets", []))
        liabilities = _get_latest_value(balance.get("total_liabilities", []))
        equity = _get_latest_value(balance.get("stockholders_equity", []))
        cash = _get_latest_value(balance.get("cash", []))
        lt_debt = _get_latest_value(balance.get("long_term_debt", []))
        curr_assets = _get_latest_value(balance.get("current_assets", []))
        curr_liab = _get_latest_value(balance.get("current_liabilities", []))

        if equity and liabilities and equity["value"] and float(equity["value"]) != 0:
            de_ratio = float(liabilities["value"]) / float(equity["value"])
            ratios.append(f"D/E: {de_ratio:.2f}")

        if curr_assets and curr_liab and curr_liab["value"] and float(curr_liab["value"]) != 0:
            current_ratio = float(curr_assets["value"]) / float(curr_liab["value"])
            ratios.append(f"Current: {current_ratio:.2f}")

        if cash and lt_debt and lt_debt["value"]:
            net_debt = float(lt_debt["value"]) - float(cash["value"])
            ratios.append(f"Net Debt: {_format_number(net_debt)}")

        if ratios:
            lines.append(f"- **Key Ratios**: {' | '.join(ratios)}")

        lines.append("")

    # ── Cash Flow ──
    if cash_flow:
        lines.append("## Cash Flow (from SEC filings)")
        lines.append("")

        for metric, label in [
            ("operating_cash_flow", "Operating Cash Flow"),
            ("capex", "Capital Expenditures"),
            ("dividends_paid", "Dividends Paid"),
        ]:
            data = cash_flow.get(metric, [])
            if not data:
                continue

            latest = _get_latest_value(data)
            if latest:
                trend = _format_trend(data)
                val = _format_number(latest["value"])
                period = f"FY{latest.get('fiscal_year', '?')}"
                lines.append(f"- **{label}**: {val} ({period}){trend}")

        # Free Cash Flow (operating CF - capex)
        ocf = _get_latest_value(cash_flow.get("operating_cash_flow", []))
        capex = _get_latest_value(cash_flow.get("capex", []))
        if ocf and capex and ocf["value"] is not None and capex["value"] is not None:
            fcf = float(ocf["value"]) - abs(float(capex["value"]))
            lines.append(f"- **Free Cash Flow**: {_format_number(fcf)}")

        lines.append("")

    # ── Analyst Recommendations ──
    recs = supplementary.get("recommendations", [])
    if recs:
        lines.append("## Analyst Recommendations")
        lines.append("")
        # Summarize the latest recommendations
        for rec in recs[-5:]:
            firm = rec.get("Firm", rec.get("firm", ""))
            grade = rec.get("To Grade", rec.get("toGrade", ""))
            action = rec.get("Action", rec.get("action", ""))
            if firm and grade:
                lines.append(f"- **{firm}**: {grade}" + (f" ({action})" if action else ""))
        lines.append("")

    # ── Earnings History ──
    earnings = supplementary.get("earnings_history", [])
    if earnings:
        lines.append("## Earnings History")
        lines.append("")
        lines.append("| Quarter | EPS Estimate | EPS Actual | Surprise |")
        lines.append("|---------|-------------|------------|----------|")
        for e in earnings[-8:]:
            quarter = e.get("Quarter End", e.get("quarter", ""))
            if hasattr(quarter, "strftime"):
                quarter = quarter.strftime("%Y-%m-%d")
            estimate = e.get("EPS Estimate", e.get("epsEstimate", ""))
            actual = e.get("EPS Actual", e.get("epsActual", ""))
            surprise = e.get("Surprise(%)", e.get("surprisePercent", ""))

            est_str = f"${estimate:.2f}" if isinstance(estimate, (int, float)) else str(estimate)
            act_str = f"${actual:.2f}" if isinstance(actual, (int, float)) else str(actual)
            sur_str = f"{surprise:.1f}%" if isinstance(surprise, (int, float)) else str(surprise)

            lines.append(f"| {quarter} | {est_str} | {act_str} | {sur_str} |")
        lines.append("")

    # ── Data empty fallback ──
    if not income and not balance and not cash_flow:
        lines.append("*No SEC EDGAR XBRL data found for this ticker.*")
        lines.append("*This may mean the company files under a different CIK or is not a US-listed company.*")
        lines.append("")

    return "\n".join(lines)


# ─── Combined Fundamentals Gather ────────────────────────────────


def gather_fundamentals(
    ticker: str,
    company_name: str,
    theme: Optional[str] = None,
    directive: Optional[str] = None,
) -> dict:
    """Gather fundamental data for a ticker.

    This is Max's primary data entry point — SEC EDGAR XBRL financials
    supplemented with yfinance company info and analyst data.

    Args:
        ticker: Stock ticker symbol
        company_name: Full company name
        theme: Optional research theme (informational only)
        directive: Optional research directive (informational only)

    Returns:
        dict with keys:
        - ticker: the symbol
        - company: the company name
        - timestamp: ISO timestamp
        - markdown: the formatted Markdown report
        - financials: extracted financial metrics from EDGAR
        - supplementary: yfinance data (info, recommendations, earnings)
        - cik: the SEC CIK number (or None)
        - theme: the research theme (if any)
        - directive: the research directive (if any)
    """
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: Resolve CIK from ticker
    cik = resolve_cik(ticker)

    # Step 2: Fetch XBRL company facts from SEC EDGAR
    facts = None
    financials = {"income": {}, "balance_sheet": {}, "cash_flow": {}}
    if cik:
        # Small delay to be polite to SEC servers
        time.sleep(0.1)
        facts = fetch_company_facts(cik)
        if facts:
            financials = extract_financials(facts)

    # Step 3: Fetch supplementary data from yfinance
    supplementary = fetch_yfinance_supplementary(ticker)

    # Step 4: Format markdown
    markdown = format_fundamentals_markdown(ticker, financials, supplementary)

    # Add header
    header = f"# Fundamental Research Report: ${ticker} ({company_name})\n"
    header += f"*Generated: {now}*\n"
    if cik:
        header += f"*SEC CIK: {cik}*\n"
    if theme:
        header += f"*Theme: {theme}*\n"
    if directive:
        header += f"*Directive: {directive}*\n"
    header += "\n---\n\n"

    # Count extracted metrics
    metric_count = (
        len(financials.get("income", {}))
        + len(financials.get("balance_sheet", {}))
        + len(financials.get("cash_flow", {}))
    )

    return {
        "ticker": ticker,
        "company": company_name,
        "timestamp": now,
        "markdown": header + markdown,
        "financials": financials,
        "supplementary": supplementary,
        "cik": cik,
        "metric_count": metric_count,
        "theme": theme,
        "directive": directive,
    }


# ─── CLI Interface ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Gather fundamental financial data for a stock ticker (Max)"
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--company", default=None, help="Company name")
    parser.add_argument("--theme", default=None, help="Research theme")
    parser.add_argument("--directive", default=None, help="Research directive")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of markdown"
    )

    args = parser.parse_args()
    ticker = args.ticker.upper().lstrip("$")
    company = args.company or ticker

    result = gather_fundamentals(
        ticker, company, theme=args.theme, directive=args.directive,
    )

    if args.json:
        output = {
            "ticker": result["ticker"],
            "company": result["company"],
            "timestamp": result["timestamp"],
            "cik": result["cik"],
            "metric_count": result["metric_count"],
            "financials": result["financials"],
            "supplementary": {
                "info": result["supplementary"].get("info", {}),
                "recommendations_count": len(result["supplementary"].get("recommendations", [])),
                "earnings_history_count": len(result["supplementary"].get("earnings_history", [])),
            },
        }
        print(json.dumps(output, indent=2, default=str))
    elif args.output:
        from pathlib import Path
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(result["markdown"])
        print(f"Research saved to {args.output}")
    else:
        print(result["markdown"])

    # Summary to stderr
    print(
        f"\n🧠 Max gathered: {result['metric_count']} financial metrics "
        f"(CIK: {result['cik'] or 'not found'})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
