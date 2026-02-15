# Ace — Heartbeat Cycle (every 1 hour)

## Cycle Steps

1. **Load watchlist** — Run `python3 manage_watchlist.py --show` for current tickers, themes, and directives
2. **For each ticker on the watchlist**:
   a. Run `gather_technicals.py` with the ticker symbol and company name
   b. Run `store.py` to upload the technical analysis report to DO Spaces and trigger KB re-indexing
   c. Evaluate signals — if any significant technical pattern is detected, prepare an alert
3. **Check for inter-agent requests** — If Max sent a request via `sessions_send`, provide a precise technical analysis response (1 response only)
4. **Optionally contact Max** — If your signals are significant enough to warrant his attention, send 1 request via `sessions_send`
5. **Send alerts** — If any ticker produced significant technical signals, alert the user via Telegram

## Heartbeat Summary Format

After each cycle, log a brief internal summary:

```
📈 Ace — Heartbeat {timestamp}
Tickers analyzed: {count}
Signals detected: {list of ticker: signal pairs}
High-conviction setups: {count}
Alerts sent: {count}
Inter-agent: {sent_to_max} request(s) sent, {responses} response(s) given
```

## Important

- Do NOT alert on routine price fluctuations. Only flag when the technical setup is genuinely noteworthy.
- Multiple confirming signals > single signal. A golden cross with volume confirmation is worth alerting; RSI touching 65 is not.
- Include specific price levels in all analysis — "$48.20 support" not "near support."
- Keep the KB growing — even boring trading days contribute to pattern recognition over time.
