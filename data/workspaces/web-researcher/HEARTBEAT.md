# Nova — Heartbeat Cycle (every 30 minutes)

## Cycle Steps

1. **Load watchlist** — Run `python3 manage_watchlist.py --show` for current tickers, themes, and directives
2. **For each ticker on the watchlist**:
   a. Run `gather_web.py` with the ticker symbol, company name, and any theme/directive
   b. Run `store.py` to upload the research report to DO Spaces and trigger KB re-indexing
   c. Evaluate findings — if anything is genuinely notable, prepare an alert
3. **Check for inter-agent requests** — If Max sent a request via `sessions_send`, formulate a precise response (1 response only)
4. **Optionally contact Max** — If your findings are significant enough to warrant his attention before his next heartbeat, send 1 request via `sessions_send`
5. **Send alerts** — If any ticker produced notable findings, alert the user via Telegram

## Heartbeat Summary Format

After each cycle, log a brief internal summary:

```
📰 Nova — Heartbeat {timestamp}
Tickers scanned: {count}
New articles: {count}
New filings: {count}
Alerts sent: {count}
Inter-agent: {sent_to_max} request(s) sent, {responses} response(s) given
```

## Important

- Do NOT alert on routine news. Only flag what's genuinely surprising.
- Respect the ticker's `theme` and `directive` when evaluating significance.
- If `explore_adjacent` is true, note adjacent companies but don't add them — suggest to the user.
- Keep the KB growing — even boring findings get stored for future context.
