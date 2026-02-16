"""
Tests for gather.py — the per-agent research data orchestrator.

Tests cover:
- Source routing per agent
- Error isolation (one source fails, others continue)
- Store integration (mocked)
- Dry-run mode
- Summary generation
"""

from pathlib import Path

import pytest
import sys

_SCRIPTS_DIR = Path(__file__).parent.parent / "skills" / "gradient-research-assistant" / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

# Also add the gather scripts dir so gather.py can find them
_GATHER_DIR = Path(__file__).parent.parent / "skills" / "gradient-data-gathering" / "scripts"
sys.path.insert(0, str(_GATHER_DIR))

from gather import (
    run_source,
    gather,
    AGENT_SOURCES,
    SOURCE_REGISTRY,
    _source_label,
)


# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def patch_sleep(monkeypatch):
    """Don't actually sleep in tests."""
    import gather as gather_mod
    monkeypatch.setattr(gather_mod.time, "sleep", lambda *a: None)


def _mock_gather_func(ticker, company_name, theme=None, directive=None):
    """A mock gather function that returns a basic result."""
    return {
        "ticker": ticker,
        "company": company_name,
        "markdown": f"# Report for {ticker}\n\nTest data.",
        "metric_count": 5,
        "article_count": 3,
        "filing_count": 2,
        "post_count": 10,
        "signal_count": 4,
    }


def _failing_gather_func(ticker, company_name, theme=None, directive=None):
    """A mock gather function that raises an error."""
    raise ConnectionError("API unavailable")


# ─── Source Registry ─────────────────────────────────────────────


class TestSourceRegistry:
    def test_all_sources_registered(self):
        assert "web" in SOURCE_REGISTRY
        assert "fundamentals" in SOURCE_REGISTRY
        assert "social" in SOURCE_REGISTRY
        assert "technicals" in SOURCE_REGISTRY

    def test_agent_defaults(self):
        assert AGENT_SOURCES["nova"] == ["web", "fundamentals"]
        assert AGENT_SOURCES["ace"] == ["technicals"]
        assert AGENT_SOURCES["luna"] == ["social"]
        assert AGENT_SOURCES["max"] == []


# ─── Run Source ──────────────────────────────────────────────────


class TestRunSource:
    def test_unknown_source(self):
        result = run_source("nonexistent", "CAKE", "Cheesecake Factory")
        assert result["success"] is False
        assert "Unknown source" in result["error"]

    def test_successful_source(self, monkeypatch):
        import gather as gather_mod

        # Mock the import mechanism
        class FakeModule:
            gather_web = staticmethod(_mock_gather_func)

        monkeypatch.setattr(gather_mod, "__import__", lambda name, *a, **kw: FakeModule() if name == "gather_web" else __import__(name, *a, **kw), raising=False)

        # Simpler approach: just monkeypatch the __import__
        # Actually, let's mock it differently
        import types
        fake_mod = types.ModuleType("gather_web")
        fake_mod.gather_web = _mock_gather_func
        monkeypatch.setitem(sys.modules, "gather_web", fake_mod)

        result = run_source("web", "CAKE", "Cheesecake Factory")
        assert result["success"] is True
        assert result["metric_count"] == 5  # article_count + filing_count

    def test_failed_source(self, monkeypatch):
        import types
        fake_mod = types.ModuleType("gather_web")
        fake_mod.gather_web = _failing_gather_func
        monkeypatch.setitem(sys.modules, "gather_web", fake_mod)

        result = run_source("web", "CAKE", "Cheesecake Factory")
        assert result["success"] is False
        assert "API unavailable" in result["error"]


# ─── Gather Orchestrator ────────────────────────────────────────


class TestGather:
    def _mock_all_sources(self, monkeypatch):
        """Mock all source modules to return test data."""
        import types
        for source_name, (module_name, func_name) in SOURCE_REGISTRY.items():
            fake_mod = types.ModuleType(module_name)
            setattr(fake_mod, func_name, _mock_gather_func)
            monkeypatch.setitem(sys.modules, module_name, fake_mod)

    def test_gather_with_default_sources(self, monkeypatch):
        self._mock_all_sources(monkeypatch)

        result = gather(
            ticker="CAKE",
            company_name="The Cheesecake Factory",
            agent="nova",
            dry_run=True,
        )

        assert result["success"] is True
        assert result["agent"] == "nova"
        assert result["ticker"] == "CAKE"
        assert len(result["sources"]) == 2  # web + fundamentals
        assert "web" in result["sources"]
        assert "fundamentals" in result["sources"]

    def test_gather_with_explicit_sources(self, monkeypatch):
        self._mock_all_sources(monkeypatch)

        result = gather(
            ticker="CAKE",
            company_name="The Cheesecake Factory",
            agent="ace",
            sources=["web", "technicals"],
            dry_run=True,
        )

        assert result["success"] is True
        assert result["sources"] == ["web", "technicals"]
        assert len(result["gather_results"]) == 2

    def test_gather_empty_agent(self):
        result = gather(
            ticker="CAKE",
            company_name="The Cheesecake Factory",
            agent="max",
            dry_run=True,
        )

        assert result["success"] is False
        assert "No sources" in result["summary"]

    def test_error_isolation(self, monkeypatch):
        """One source failing shouldn't crash the others."""
        import types

        # web fails
        fake_web = types.ModuleType("gather_web")
        fake_web.gather_web = _failing_gather_func
        monkeypatch.setitem(sys.modules, "gather_web", fake_web)

        # fundamentals succeeds
        fake_fund = types.ModuleType("gather_fundamentals")
        fake_fund.gather_fundamentals = _mock_gather_func
        monkeypatch.setitem(sys.modules, "gather_fundamentals", fake_fund)

        result = gather(
            ticker="CAKE",
            company_name="The Cheesecake Factory",
            agent="nova",
            dry_run=True,
        )

        # Should still succeed because fundamentals worked
        assert result["success"] is True
        assert any(gr["success"] for gr in result["gather_results"])
        assert any(not gr["success"] for gr in result["gather_results"])
        assert "failed: web" in result["summary"]

    def test_dry_run_skips_store(self, monkeypatch):
        self._mock_all_sources(monkeypatch)

        result = gather(
            ticker="CAKE",
            company_name="The Cheesecake Factory",
            agent="ace",
            dry_run=True,
        )

        assert result["dry_run"] is True
        for sr in result["store_results"]:
            if sr["success"]:
                assert "DRY RUN" in sr["message"]

    def test_summary_includes_counts(self, monkeypatch):
        self._mock_all_sources(monkeypatch)

        result = gather(
            ticker="CAKE",
            company_name="The Cheesecake Factory",
            agent="nova",
            dry_run=True,
        )

        assert "$CAKE" in result["summary"]
        assert "articles/filings" in result["summary"] or "financial metrics" in result["summary"]

    def test_timestamp_present(self, monkeypatch):
        self._mock_all_sources(monkeypatch)

        result = gather(
            ticker="CAKE",
            company_name="The Cheesecake Factory",
            agent="ace",
            dry_run=True,
        )

        assert "timestamp" in result
        assert "2026" in result["timestamp"] or "20" in result["timestamp"]  # Year check


# ─── Source Labels ───────────────────────────────────────────────


class TestSourceLabel:
    def test_web_label(self):
        assert _source_label("web", 5) == "5 articles/filings"

    def test_fundamentals_label(self):
        assert _source_label("fundamentals", 16) == "16 financial metrics"

    def test_technicals_label(self):
        assert _source_label("technicals", 3) == "3 technical signals"

    def test_unknown_label(self):
        assert _source_label("custom", 7) == "7 items from custom"
