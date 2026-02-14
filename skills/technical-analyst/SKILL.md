---
name: technical-analyst
description: Gather technical analysis data (price action, indicators) for stock tickers
---

# Technical Analyst Skill

This skill provides Ace's technical analysis capabilities.

## Tools

### gather_technicals.py

Fetch price data via yfinance and calculate technical indicators.

```bash
# Basic usage
python3 gather_technicals.py --ticker CAKE --company "The Cheesecake Factory"

# JSON output (indicators + signals data)
python3 gather_technicals.py --ticker HOG --json
```

**Output**: Markdown report with price summary, moving averages (SMA 20/50/200), RSI(14), MACD, Bollinger Bands, volume analysis, and detected signals (crossovers, divergences, breakouts).

**Requires**: `yfinance` package (installed via `requirements.txt` in the Docker image).

### Shared Tools (from gradient-research-assistant)

- `store.py` — Upload research to DO Spaces and trigger KB indexing
- `query_kb.py` — Query the knowledge base for historical context
- `manage_watchlist.py` — Read the watchlist
- `alert.py` — Format and send alerts
