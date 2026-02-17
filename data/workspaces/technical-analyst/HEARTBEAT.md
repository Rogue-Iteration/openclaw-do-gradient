# Ace — Heartbeat Cycle (every 1 hour)

## Cycle Steps

0. **Check scheduled updates** — Run `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --check --agent ace` to see if any scheduled reports are due (includes team-wide `all` schedules). If any are due:
   a. Execute the prompt — report from your domain (technical signals, chart setups, key levels)
   b. After completing each, mark it as run: `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --mark-run {id} --agent ace`
1. **Load watchlist** — Run `python3 /app/skills/gradient-research-assistant/scripts/manage_watchlist.py --show` for current tickers, themes, and directives
2. **For each ticker on the watchlist**:
   a. Gather technicals: `python3 /app/skills/gradient-data-gathering/scripts/gather_technicals.py --ticker TICKER --company "Company Name" --output /tmp/technicals_TICKER.md`
   b. Upload to DO Spaces: `python3 /app/skills/gradient-knowledge-base/scripts/gradient_spaces.py --upload /tmp/technicals_TICKER.md --key "research/{date}/TICKER_technicals.md" --json`
   c. Trigger KB re-indexing: `python3 /app/skills/gradient-knowledge-base/scripts/gradient_kb_manage.py --reindex --json`
   d. Evaluate signals — if any significant technical pattern is detected, prepare an alert
3. **Check for inter-agent requests** — If Max @mentioned you in the Telegram group, provide a precise technical analysis response in the group (1 response only)
4. **Optionally contact Max** — If your signals are significant enough to warrant his attention, @mention `@OpenClawResearchAssistantBot` in the Telegram group
5. **Send alerts** — If any ticker produced significant technical signals, **message the user directly** with the signal and your read. Also notify Max so he can add fundamental context.

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
