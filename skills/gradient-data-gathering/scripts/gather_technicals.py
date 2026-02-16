#!/usr/bin/env python3
"""
Technical analysis data gathering for Ace (Technical Analyst).

Fetches price data via yfinance and calculates technical indicators:
- SMA (20, 50, 200)
- RSI (14)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- Volume analysis

Identifies key technical signals (crossovers, divergences, breakouts).

Usage:
    python3 gather_technicals.py --ticker CAKE --company "The Cheesecake Factory"
    python3 gather_technicals.py --ticker HOG --json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf


# ─── Price Data Fetching ─────────────────────────────────────────


def fetch_price_data(ticker: str, period: str = "5y") -> dict:
    """Fetch OHLCV price data from yfinance.

    Args:
        ticker: Stock ticker symbol
        period: Data period (e.g., '1mo', '3mo', '6mo', '1y', '5y')

    Returns:
        dict with 'success', 'data' (list of OHLCV dicts), 'info' (stock info)
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            return {"success": False, "data": [], "info": {}, "message": f"No data for {ticker}"}

        # Convert to list of dicts
        data = []
        for date, row in hist.iterrows():
            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        # Basic stock info
        info = {}
        try:
            raw_info = stock.info
            info = {
                "name": raw_info.get("shortName", ticker),
                "sector": raw_info.get("sector", ""),
                "market_cap": raw_info.get("marketCap", 0),
                "avg_volume": raw_info.get("averageVolume", 0),
            }
        except Exception:
            pass

        return {"success": True, "data": data, "info": info, "message": "OK"}
    except Exception as e:
        return {"success": False, "data": [], "info": {}, "message": str(e)}


# ─── Technical Indicator Calculations ─────────────────────────────


def _sma(prices: list[float], period: int) -> list[Optional[float]]:
    """Calculate Simple Moving Average."""
    result: list[Optional[float]] = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        result[i] = round(sum(window) / period, 2)
    return result


def _ema(prices: list[float], period: int) -> list[Optional[float]]:
    """Calculate Exponential Moving Average."""
    result: list[Optional[float]] = [None] * len(prices)
    if len(prices) < period:
        return result

    # Initialize with SMA
    sma = sum(prices[:period]) / period
    result[period - 1] = round(sma, 4)

    multiplier = 2 / (period + 1)
    for i in range(period, len(prices)):
        prev = result[i - 1] if result[i - 1] is not None else sma
        result[i] = round(prev + multiplier * (prices[i] - prev), 4)

    return result


def calculate_indicators(data: list[dict]) -> dict:
    """Calculate technical indicators from OHLCV data.

    Args:
        data: List of OHLCV dicts from fetch_price_data

    Returns:
        dict with indicator values for the most recent data point,
        plus recent history for trend analysis
    """
    if len(data) < 20:
        return {"success": False, "message": "Insufficient data for indicators"}

    closes = [d["close"] for d in data]
    volumes = [d["volume"] for d in data]
    highs = [d["high"] for d in data]
    lows = [d["low"] for d in data]

    # Moving Averages
    sma_20 = _sma(closes, 20)
    sma_50 = _sma(closes, 50)
    sma_200 = _sma(closes, 200)

    # RSI (14)
    rsi_values = _calculate_rsi(closes, 14)

    # MACD (12, 26, 9)
    macd_line, signal_line, histogram = _calculate_macd(closes)

    # Bollinger Bands (20, 2)
    bb_upper, bb_middle, bb_lower = _calculate_bollinger(closes, 20, 2)

    # Volume analysis
    vol_sma_20 = _sma([float(v) for v in volumes], 20)

    # Latest values
    latest = {
        "date": data[-1]["date"],
        "close": closes[-1],
        "volume": volumes[-1],
        "sma_20": sma_20[-1],
        "sma_50": sma_50[-1] if len(closes) >= 50 else None,
        "sma_200": sma_200[-1] if len(closes) >= 200 else None,
        "rsi": rsi_values[-1] if rsi_values[-1] is not None else None,
        "macd": macd_line[-1] if macd_line[-1] is not None else None,
        "macd_signal": signal_line[-1] if signal_line[-1] is not None else None,
        "macd_histogram": histogram[-1] if histogram[-1] is not None else None,
        "bb_upper": bb_upper[-1],
        "bb_middle": bb_middle[-1],
        "bb_lower": bb_lower[-1],
        "volume_sma_20": vol_sma_20[-1],
    }

    # Previous day for crossover detection
    prev = {
        "sma_50": sma_50[-2] if len(closes) >= 50 and sma_50[-2] is not None else None,
        "sma_200": sma_200[-2] if len(closes) >= 200 and sma_200[-2] is not None else None,
        "macd": macd_line[-2] if len(macd_line) >= 2 and macd_line[-2] is not None else None,
        "macd_signal": signal_line[-2] if len(signal_line) >= 2 and signal_line[-2] is not None else None,
        "rsi": rsi_values[-2] if len(rsi_values) >= 2 and rsi_values[-2] is not None else None,
    }

    # Price range (recent)
    recent_closes = closes[-20:]
    price_range = {
        "high_20d": round(max(highs[-20:]), 2),
        "low_20d": round(min(lows[-20:]), 2),
        "change_1d_pct": round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if len(closes) >= 2 else 0,
        "change_5d_pct": round((closes[-1] - closes[-5]) / closes[-5] * 100, 2) if len(closes) >= 5 else 0,
        "change_20d_pct": round((closes[-1] - closes[-20]) / closes[-20] * 100, 2) if len(closes) >= 20 else 0,
    }

    return {
        "success": True,
        "latest": latest,
        "previous": prev,
        "price_range": price_range,
    }


def _calculate_rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
    """Calculate Relative Strength Index."""
    result: list[Optional[float]] = [None] * len(closes)
    if len(closes) < period + 1:
        return result

    # Calculate price changes
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    # Initial average gain/loss
    gains = [max(d, 0) for d in deltas[:period]]
    losses = [max(-d, 0) for d in deltas[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = round(100 - (100 / (1 + rs)), 2)

    # Subsequent values using smoothing
    for i in range(period, len(deltas)):
        gain = max(deltas[i], 0)
        loss = max(-deltas[i], 0)

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = round(100 - (100 / (1 + rs)), 2)

    return result


def _calculate_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
    """Calculate MACD, signal line, and histogram."""
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    macd_line: list[Optional[float]] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = round(ema_fast[i] - ema_slow[i], 4)

    # Signal line = EMA of MACD line
    macd_values = [v for v in macd_line if v is not None]
    if len(macd_values) < signal:
        return macd_line, [None] * len(closes), [None] * len(closes)

    signal_ema = _ema(macd_values, signal)

    # Map signal back to full length
    signal_line: list[Optional[float]] = [None] * len(closes)
    macd_start = next(i for i, v in enumerate(macd_line) if v is not None)
    for i, val in enumerate(signal_ema):
        if val is not None:
            signal_line[macd_start + i] = val

    # Histogram
    histogram: list[Optional[float]] = [None] * len(closes)
    for i in range(len(closes)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = round(macd_line[i] - signal_line[i], 4)

    return macd_line, signal_line, histogram


def _calculate_bollinger(
    closes: list[float],
    period: int = 20,
    std_dev: int = 2,
) -> tuple[list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
    """Calculate Bollinger Bands."""
    middle = _sma(closes, period)
    upper: list[Optional[float]] = [None] * len(closes)
    lower: list[Optional[float]] = [None] * len(closes)

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5

        upper[i] = round(mean + std_dev * std, 2)
        lower[i] = round(mean - std_dev * std, 2)

    return upper, middle, lower


# ─── Signal Identification ────────────────────────────────────────


def identify_signals(indicators: dict) -> list[dict]:
    """Identify significant technical signals from calculated indicators.

    Returns:
        List of signal dicts, each with: signal, type ('bullish'/'bearish'), strength (1-3)
    """
    if not indicators.get("success"):
        return []

    signals = []
    latest = indicators["latest"]
    prev = indicators["previous"]
    price_range = indicators["price_range"]

    close = latest["close"]

    # ── Moving Average Crossovers ──
    if latest["sma_50"] and latest["sma_200"] and prev["sma_50"] and prev["sma_200"]:
        # Golden Cross
        if prev["sma_50"] <= prev["sma_200"] and latest["sma_50"] > latest["sma_200"]:
            signals.append({
                "signal": f"Golden Cross: SMA(50) ${latest['sma_50']} crossed above SMA(200) ${latest['sma_200']}",
                "type": "bullish",
                "strength": 3,
            })
        # Death Cross
        elif prev["sma_50"] >= prev["sma_200"] and latest["sma_50"] < latest["sma_200"]:
            signals.append({
                "signal": f"Death Cross: SMA(50) ${latest['sma_50']} crossed below SMA(200) ${latest['sma_200']}",
                "type": "bearish",
                "strength": 3,
            })

    # ── Price vs. Moving Averages ──
    if latest["sma_200"]:
        if close > latest["sma_200"] * 1.02:
            signals.append({
                "signal": f"Trading above SMA(200) ${latest['sma_200']} — long-term bullish",
                "type": "bullish",
                "strength": 1,
            })
        elif close < latest["sma_200"] * 0.98:
            signals.append({
                "signal": f"Trading below SMA(200) ${latest['sma_200']} — long-term bearish",
                "type": "bearish",
                "strength": 1,
            })

    # ── RSI ──
    rsi = latest.get("rsi")
    if rsi is not None:
        if rsi >= 70:
            signals.append({
                "signal": f"RSI overbought at {rsi}",
                "type": "bearish",
                "strength": 2,
            })
        elif rsi <= 30:
            signals.append({
                "signal": f"RSI oversold at {rsi}",
                "type": "bullish",
                "strength": 2,
            })

    # ── RSI Divergence (simplified) ──
    prev_rsi = prev.get("rsi")
    if rsi and prev_rsi:
        price_up = close > indicators["latest"].get("close", close)  # Simplified
        rsi_down = rsi < prev_rsi
        if price_up and rsi_down and rsi > 60:
            signals.append({
                "signal": f"Potential bearish RSI divergence: price rising but RSI declining ({rsi})",
                "type": "bearish",
                "strength": 2,
            })

    # ── MACD Crossover ──
    if latest["macd"] is not None and latest["macd_signal"] is not None:
        if prev["macd"] is not None and prev["macd_signal"] is not None:
            if prev["macd"] <= prev["macd_signal"] and latest["macd"] > latest["macd_signal"]:
                signals.append({
                    "signal": "MACD bullish crossover — momentum shifting up",
                    "type": "bullish",
                    "strength": 2,
                })
            elif prev["macd"] >= prev["macd_signal"] and latest["macd"] < latest["macd_signal"]:
                signals.append({
                    "signal": "MACD bearish crossover — momentum shifting down",
                    "type": "bearish",
                    "strength": 2,
                })

    # ── Bollinger Bands ──
    if latest["bb_upper"] and latest["bb_lower"]:
        bb_width = latest["bb_upper"] - latest["bb_lower"]
        bb_mid = latest["bb_middle"] or close

        if close >= latest["bb_upper"]:
            signals.append({
                "signal": f"Price at upper Bollinger Band ${latest['bb_upper']} — potential resistance",
                "type": "bearish",
                "strength": 1,
            })
        elif close <= latest["bb_lower"]:
            signals.append({
                "signal": f"Price at lower Bollinger Band ${latest['bb_lower']} — potential support",
                "type": "bullish",
                "strength": 1,
            })

        # Squeeze detection (bands narrowing)
        if bb_mid and bb_width / bb_mid < 0.04:
            signals.append({
                "signal": "Bollinger Band squeeze — volatility contraction, big move may be imminent",
                "type": "bullish",  # Direction neutral but noteworthy
                "strength": 2,
            })

    # ── Volume ──
    if latest["volume_sma_20"] and latest["volume_sma_20"] > 0:
        vol_ratio = latest["volume"] / latest["volume_sma_20"]
        if vol_ratio >= 2.0:
            signals.append({
                "signal": f"Volume spike: {vol_ratio:.1f}x the 20-day average",
                "type": "bullish" if price_range["change_1d_pct"] > 0 else "bearish",
                "strength": 2,
            })

    return signals


# ─── Markdown Formatting ─────────────────────────────────────────


def format_technicals_markdown(
    ticker: str,
    indicators: dict,
    signals: list[dict],
    info: dict,
) -> str:
    """Format technical analysis as a Markdown report."""
    lines = [f"# Technical Analysis: ${ticker}", ""]

    if not indicators.get("success"):
        lines.append(f"*{indicators.get('message', 'No data available')}*")
        return "\n".join(lines)

    latest = indicators["latest"]
    price_range = indicators["price_range"]

    # Price summary
    lines.append("## Price Summary")
    lines.append("")
    lines.append(f"- **Close**: ${latest['close']}")
    lines.append(f"- **20-Day Range**: ${price_range['low_20d']} — ${price_range['high_20d']}")
    lines.append(f"- **1D Change**: {price_range['change_1d_pct']:+.2f}%")
    lines.append(f"- **5D Change**: {price_range['change_5d_pct']:+.2f}%")
    lines.append(f"- **20D Change**: {price_range['change_20d_pct']:+.2f}%")
    lines.append("")

    # Moving Averages
    lines.append("## Moving Averages")
    lines.append("")
    lines.append(f"- **SMA(20)**: ${latest['sma_20']}" if latest["sma_20"] else "- SMA(20): N/A")
    if latest["sma_50"]:
        pos = "above" if latest["close"] > latest["sma_50"] else "below"
        lines.append(f"- **SMA(50)**: ${latest['sma_50']} (price {pos})")
    if latest["sma_200"]:
        pos = "above" if latest["close"] > latest["sma_200"] else "below"
        lines.append(f"- **SMA(200)**: ${latest['sma_200']} (price {pos})")
    lines.append("")

    # Momentum Indicators
    lines.append("## Momentum")
    lines.append("")
    if latest["rsi"] is not None:
        rsi_status = "overbought" if latest["rsi"] > 70 else "oversold" if latest["rsi"] < 30 else "neutral"
        lines.append(f"- **RSI(14)**: {latest['rsi']} ({rsi_status})")
    if latest["macd"] is not None:
        lines.append(f"- **MACD**: {latest['macd']:.4f} | Signal: {latest['macd_signal']:.4f} | Histogram: {latest['macd_histogram']:.4f}")
    lines.append("")

    # Bollinger Bands
    lines.append("## Bollinger Bands (20, 2)")
    lines.append("")
    if latest["bb_upper"]:
        lines.append(f"- **Upper**: ${latest['bb_upper']}")
        lines.append(f"- **Middle**: ${latest['bb_middle']}")
        lines.append(f"- **Lower**: ${latest['bb_lower']}")
        bb_width = latest["bb_upper"] - latest["bb_lower"]
        lines.append(f"- **Width**: ${bb_width:.2f}")
    lines.append("")

    # Volume
    lines.append("## Volume")
    lines.append("")
    lines.append(f"- **Today**: {latest['volume']:,}")
    if latest["volume_sma_20"]:
        vol_ratio = latest["volume"] / latest["volume_sma_20"]
        lines.append(f"- **20D Average**: {int(latest['volume_sma_20']):,}")
        lines.append(f"- **Ratio**: {vol_ratio:.2f}x average")
    lines.append("")

    # Signals
    if signals:
        lines.append("## 🚨 Signals Detected")
        lines.append("")
        for sig in sorted(signals, key=lambda s: s["strength"], reverse=True):
            emoji = "🟢" if sig["type"] == "bullish" else "🔴"
            strength = "⭐" * sig["strength"]
            lines.append(f"- {emoji} {sig['signal']} {strength}")
        lines.append("")
    else:
        lines.append("## Signals")
        lines.append("No significant technical signals detected.")
        lines.append("")

    return "\n".join(lines)


# ─── Combined Technical Gather ────────────────────────────────────


def gather_technicals(
    ticker: str,
    company_name: str,
    theme: Optional[str] = None,
    directive: Optional[str] = None,
) -> dict:
    """Gather technical analysis data for a ticker.

    This is Ace's primary entry point — price data + technical indicators.

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
        - indicators: calculated indicator values
        - signals: list of detected signals
        - info: stock info from yfinance
    """
    now = datetime.now(timezone.utc).isoformat()

    # Fetch price data
    price_result = fetch_price_data(ticker, period="6mo")

    if not price_result["success"]:
        return {
            "ticker": ticker,
            "company": company_name,
            "timestamp": now,
            "markdown": f"# Technical Analysis: ${ticker}\n\nFailed to fetch price data: {price_result['message']}",
            "indicators": {"success": False},
            "signals": [],
            "info": {},
        }

    # Calculate indicators
    indicators = calculate_indicators(price_result["data"])

    # Identify signals
    signals = identify_signals(indicators) if indicators.get("success") else []

    # Format markdown
    markdown = format_technicals_markdown(ticker, indicators, signals, price_result["info"])

    # Add header
    header = f"# Technical Research Report: ${ticker} ({company_name})\n"
    header += f"*Generated: {now}*\n"
    if theme:
        header += f"*Theme: {theme}*\n"
    if directive:
        header += f"*Directive: {directive}*\n"
    header += "\n---\n\n"

    return {
        "ticker": ticker,
        "company": company_name,
        "timestamp": now,
        "markdown": header + markdown,
        "indicators": indicators,
        "signals": signals,
        "info": price_result["info"],
    }


# ─── CLI Interface ────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Gather technical analysis data for a stock ticker"
    )
    parser.add_argument("--ticker", required=True, help="Stock ticker symbol")
    parser.add_argument("--company", default=None, help="Company name")
    parser.add_argument("--theme", default=None, help="Research theme")
    parser.add_argument("--directive", default=None, help="Research directive")
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of markdown"
    )

    args = parser.parse_args()
    company = args.company or args.ticker

    result = gather_technicals(
        args.ticker.upper(),
        company,
        theme=args.theme,
        directive=args.directive,
    )

    if args.json:
        output = {
            "ticker": result["ticker"],
            "company": result["company"],
            "timestamp": result["timestamp"],
            "indicators": result["indicators"],
            "signals": result["signals"],
            "info": result["info"],
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print(result["markdown"])

    # Summary to stderr
    signals = result["signals"]
    bullish = sum(1 for s in signals if s["type"] == "bullish")
    bearish = sum(1 for s in signals if s["type"] == "bearish")
    print(
        f"\n📈 {result['ticker']}: {len(signals)} signals "
        f"({bullish} bullish, {bearish} bearish)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
