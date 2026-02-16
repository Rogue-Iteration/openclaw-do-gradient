"""
Tests for gather_fundamentals.py — Max's fundamental data gathering.

Tests cover:
- CIK resolution from ticker
- XBRL financial data extraction
- Supplementary yfinance data fetching
- Markdown formatting (populated and empty)
- Combined gather_fundamentals() function
"""

from pathlib import Path

import pytest

import sys

SKILL_DIR = Path(__file__).parent.parent / "skills" / "gradient-data-gathering" / "scripts"
sys.path.insert(0, str(SKILL_DIR))

from gather_fundamentals import (
    resolve_cik,
    extract_financials,
    fetch_yfinance_supplementary,
    format_fundamentals_markdown,
    gather_fundamentals as run_gather_fundamentals,
    _format_number,
    _extract_concept_data,
)


# ─── Fixtures ─────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def xbrl_facts():
    import json
    return json.loads((FIXTURES_DIR / "sec_edgar_xbrl_CAKE.json").read_text())


@pytest.fixture
def empty_facts():
    return {"facts": {"us-gaap": {}}}


@pytest.fixture
def mock_cik_response():
    """Simplified company_tickers.json response."""
    return {
        "0": {"cik_str": 887596, "ticker": "CAKE", "title": "CHEESECAKE FACTORY INC"},
        "1": {"cik_str": 1776661, "ticker": "BNTX", "title": "BIONTECH SE"},
    }


# ─── CIK Resolution ──────────────────────────────────────────────


class TestResolveCik:
    def test_resolves_known_ticker(self, monkeypatch, mock_cik_response):
        # Clear the cache
        import gather_fundamentals
        gather_fundamentals._CIK_CACHE = {}

        class FakeResp:
            def raise_for_status(self): pass
            def json(self): return mock_cik_response

        monkeypatch.setattr("gather_fundamentals.requests.get", lambda *a, **kw: FakeResp())

        cik = resolve_cik("CAKE")
        assert cik == "0000887596"

    def test_returns_none_for_unknown_ticker(self, monkeypatch, mock_cik_response):
        import gather_fundamentals
        gather_fundamentals._CIK_CACHE = {}

        class FakeResp:
            def raise_for_status(self): pass
            def json(self): return mock_cik_response

        monkeypatch.setattr("gather_fundamentals.requests.get", lambda *a, **kw: FakeResp())

        cik = resolve_cik("XXXXXX")
        assert cik is None

    def test_case_insensitive(self, monkeypatch, mock_cik_response):
        import gather_fundamentals
        gather_fundamentals._CIK_CACHE = {}

        class FakeResp:
            def raise_for_status(self): pass
            def json(self): return mock_cik_response

        monkeypatch.setattr("gather_fundamentals.requests.get", lambda *a, **kw: FakeResp())

        cik = resolve_cik("cake")
        assert cik == "0000887596"

    def test_returns_none_on_request_failure(self, monkeypatch):
        import gather_fundamentals
        gather_fundamentals._CIK_CACHE = {}

        def fail(*a, **kw):
            raise Exception("network error")

        monkeypatch.setattr("gather_fundamentals.requests.get", fail)
        cik = resolve_cik("CAKE")
        assert cik is None


# ─── Financial Data Extraction ────────────────────────────────────


class TestExtractFinancials:
    def test_extracts_income_metrics(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        income = financials["income"]

        assert "revenue" in income
        assert "net_income" in income
        assert "eps_diluted" in income

    def test_extracts_balance_sheet_metrics(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        balance = financials["balance_sheet"]

        assert "total_assets" in balance
        assert "total_liabilities" in balance
        assert "stockholders_equity" in balance
        assert "cash" in balance
        assert "long_term_debt" in balance

    def test_extracts_cash_flow_metrics(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        cf = financials["cash_flow"]

        assert "operating_cash_flow" in cf
        assert "capex" in cf

    def test_revenue_values_correct(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        revenue = financials["income"]["revenue"]

        # Should have multiple data points
        assert len(revenue) >= 2

        # Most recent annual should be FY2024
        annual = [r for r in revenue if r["form"] == "10-K"]
        latest = annual[-1]
        assert latest["fiscal_year"] == 2024
        assert latest["value"] == 3498272000

    def test_handles_empty_facts(self, empty_facts):
        financials = extract_financials(empty_facts)
        assert financials["income"] == {}
        assert financials["balance_sheet"] == {}
        assert financials["cash_flow"] == {}

    def test_handles_none_facts(self):
        financials = extract_financials(None)
        assert financials["income"] == {}

    def test_filters_by_years(self, xbrl_facts):
        # With 1 year, should exclude older data
        financials = extract_financials(xbrl_facts, years=1)
        revenue = financials["income"].get("revenue", [])
        for r in revenue:
            year = int(r["end_date"][:4])
            assert year >= 2025  # Current year minus 1


class TestExtractConceptData:
    def test_tries_multiple_concept_names(self, xbrl_facts):
        facts = xbrl_facts
        # "Revenues" exists in our fixture
        data = _extract_concept_data(facts, ["NonexistentConcept", "Revenues"])
        assert len(data) > 0

    def test_returns_empty_for_unknown_concepts(self, xbrl_facts):
        data = _extract_concept_data(xbrl_facts, ["FakeConcept1", "FakeConcept2"])
        assert data == []

    def test_filters_to_10k_10q_only(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        for category in financials.values():
            for metric_data in category.values():
                for entry in metric_data:
                    assert entry["form"] in ("10-K", "10-Q", "10-K/A", "10-Q/A")


# ─── Number Formatting ───────────────────────────────────────────


class TestFormatNumber:
    def test_billions(self):
        assert _format_number(3498272000) == "$3.5B"

    def test_millions(self):
        assert _format_number(192340000) == "$192.3M"

    def test_thousands(self):
        assert _format_number(5000) == "$5.0K"

    def test_small_number(self):
        assert _format_number(4.22) == "$4.22"

    def test_negative(self):
        assert _format_number(-62800000) == "-$62.8M"

    def test_none(self):
        assert _format_number(None) == "N/A"

    def test_no_prefix(self):
        assert _format_number(45200000, prefix="") == "45.2M"


# ─── Markdown Formatting ─────────────────────────────────────────


class TestFormatFundamentalsMarkdown:
    def test_formats_with_data(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        supplementary = {
            "info": {"long_name": "The Cheesecake Factory", "sector": "Consumer Cyclical"},
            "recommendations": [],
            "earnings_history": [],
        }

        md = format_fundamentals_markdown("CAKE", financials, supplementary)

        assert "Fundamental Analysis: $CAKE" in md
        assert "Income Statement" in md
        assert "Balance Sheet" in md
        assert "Cash Flow" in md
        assert "Cheesecake Factory" in md

    def test_formats_empty_data(self):
        financials = {"income": {}, "balance_sheet": {}, "cash_flow": {}}
        supplementary = {"info": {}, "recommendations": [], "earnings_history": []}

        md = format_fundamentals_markdown("UNKNOWN", financials, supplementary)

        assert "Fundamental Analysis: $UNKNOWN" in md
        assert "No SEC EDGAR XBRL data found" in md

    def test_includes_margins(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        supplementary = {"info": {}, "recommendations": [], "earnings_history": []}

        md = format_fundamentals_markdown("CAKE", financials, supplementary)

        # Should calculate margins from revenue/gross profit/net income
        assert "Margins" in md

    def test_includes_key_ratios(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        supplementary = {"info": {}, "recommendations": [], "earnings_history": []}

        md = format_fundamentals_markdown("CAKE", financials, supplementary)

        assert "Key Ratios" in md
        assert "D/E" in md  # Debt/Equity ratio

    def test_includes_free_cash_flow(self, xbrl_facts):
        financials = extract_financials(xbrl_facts)
        supplementary = {"info": {}, "recommendations": [], "earnings_history": []}

        md = format_fundamentals_markdown("CAKE", financials, supplementary)

        assert "Free Cash Flow" in md


# ─── Combined Gather ─────────────────────────────────────────────


class TestGatherFundamentals:
    def test_returns_required_keys(self, monkeypatch):
        import gather_fundamentals
        gather_fundamentals._CIK_CACHE = {}

        monkeypatch.setattr("gather_fundamentals.resolve_cik", lambda *a: None)
        monkeypatch.setattr("gather_fundamentals.fetch_company_facts", lambda *a: None)
        monkeypatch.setattr(
            "gather_fundamentals.fetch_yfinance_supplementary",
            lambda *a: {"info": {}, "recommendations": [], "earnings_history": []},
        )

        result = run_gather_fundamentals("CAKE", "The Cheesecake Factory")

        assert result["ticker"] == "CAKE"
        assert result["company"] == "The Cheesecake Factory"
        assert "timestamp" in result
        assert "markdown" in result
        assert "financials" in result
        assert "supplementary" in result
        assert "cik" in result

    def test_includes_theme(self, monkeypatch):
        import gather_fundamentals
        gather_fundamentals._CIK_CACHE = {}

        monkeypatch.setattr("gather_fundamentals.resolve_cik", lambda *a: None)
        monkeypatch.setattr("gather_fundamentals.fetch_company_facts", lambda *a: None)
        monkeypatch.setattr(
            "gather_fundamentals.fetch_yfinance_supplementary",
            lambda *a: {"info": {}, "recommendations": [], "earnings_history": []},
        )

        result = run_gather_fundamentals("BNTX", "BioNTech", theme="mRNA cancer research")

        assert result["theme"] == "mRNA cancer research"
        assert "mRNA cancer research" in result["markdown"]

    def test_with_fixture_data(self, monkeypatch, xbrl_facts):
        import gather_fundamentals
        gather_fundamentals._CIK_CACHE = {}

        monkeypatch.setattr("gather_fundamentals.resolve_cik", lambda *a: "0000887596")
        monkeypatch.setattr("gather_fundamentals.fetch_company_facts", lambda *a: xbrl_facts)
        monkeypatch.setattr("gather_fundamentals.time.sleep", lambda *a: None)
        monkeypatch.setattr(
            "gather_fundamentals.fetch_yfinance_supplementary",
            lambda *a: {"info": {"long_name": "Cheesecake Factory"}, "recommendations": [], "earnings_history": []},
        )

        result = run_gather_fundamentals("CAKE", "The Cheesecake Factory")

        assert result["cik"] == "0000887596"
        assert result["metric_count"] > 0
        assert "Revenue" in result["markdown"]
        assert "Net Income" in result["markdown"]
