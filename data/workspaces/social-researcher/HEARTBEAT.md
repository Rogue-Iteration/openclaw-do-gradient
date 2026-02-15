# Luna — Heartbeat Cycle (every 45 minutes)

## Cycle Steps

1. **Load watchlist** — Run `python3 manage_watchlist.py --show` for current tickers, themes, and directives
2. **For each ticker on the watchlist**:
   a. Run `gather_social.py` with the ticker symbol, company name, and any theme/directive
   b. Run `store.py` to upload the social research report to DO Spaces and trigger KB re-indexing
   c. Evaluate sentiment signals — if any spike or shift is significant, prepare an alert
3. **Check for inter-agent requests** — If Max sent a request via `sessions_send`, formulate a precise response (1 response only)
4. **Optionally contact Max** — If your signals are significant enough to warrant his attention, send 1 request via `sessions_send`
5. **Send alerts** — If any ticker produced notable social signals, alert the user via Telegram

## Heartbeat Summary Format

After each cycle, log a brief internal summary:

```
📱 Luna — Heartbeat {timestamp}
Tickers scanned: {count}
Reddit posts found: {count}
Sentiment shifts detected: {count}
Volume spikes: {count}
Alerts sent: {count}
Inter-agent: {sent_to_max} request(s) sent, {responses} response(s) given
```

## Important

- Do NOT alert on normal Reddit chatter. Only flag genuine sentiment shifts or volume spikes.
- Respect the ticker's `theme` and `directive` when evaluating significance.
- If `explore_adjacent` is true, note adjacent tickers from the same threads — suggest to the user.
- Keep the KB growing — even quiet social data has value for establishing baselines.
