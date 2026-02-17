# Nova — Heartbeat Cycle (every 30 minutes)

## Cycle Steps

0. **Check scheduled updates** — Run `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --check --agent nova` to see if any scheduled reports are due (includes team-wide `all` schedules). If any are due:
   a. Execute the prompt — report from your domain (news, filings, financial data)
   b. After completing each, mark it as run: `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --mark-run {id} --agent nova`
1. **Load watchlist** — Run `python3 /app/skills/gradient-research-assistant/scripts/manage_watchlist.py --show` for current tickers, themes, and directives
2. **For each ticker on the watchlist**:
   a. Gather web research: `python3 /app/skills/gradient-data-gathering/scripts/gather_web.py --ticker TICKER --name "Company Name" --output /tmp/web_TICKER.md`
   b. Upload to DO Spaces: `python3 /app/skills/gradient-knowledge-base/scripts/gradient_spaces.py --upload /tmp/web_TICKER.md --key "research/{date}/TICKER_web.md" --json`
   c. Trigger KB re-indexing: `python3 /app/skills/gradient-knowledge-base/scripts/gradient_kb_manage.py --reindex --json`
   d. Evaluate findings — if anything is genuinely notable, prepare an alert
3. **Check for inter-agent requests** — If Max @mentioned you in the Telegram group, formulate a precise response in the group (1 response only)
4. **Optionally contact Max** — If your findings are significant enough to warrant his attention, @mention `@OpenClawResearchAssistantBot` in the Telegram group
5. **Send alerts** — If any ticker produced notable findings, **message the user directly** with your findings. Also notify Max so he can synthesize.

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
