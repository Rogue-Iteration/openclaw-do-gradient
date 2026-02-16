# Max — Heartbeat Cycle (every 2 hours)

## Cycle Steps

0. **Check scheduled updates** — Run `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --check` to see if any scheduled reports are due. If any are due:
   a. Execute the prompt for each due schedule (e.g., deliver the morning briefing or evening wrap)
   b. After completing each, mark it as run: `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --mark-run {id}`
1. **Load watchlist** — Run `python3 /app/skills/gradient-research-assistant/scripts/manage_watchlist.py --show` for current tickers, themes, and directives
2. **Query the Knowledge Base** — For each ticker, query the KB for recent research accumulated by Nova
3. **Run analysis** — Use `analyze.py` for each ticker:
   a. Quick pass (significance scoring 1-10)
   b. If score ≥ 5, trigger deep analysis with the premium model
   c. Build/update your thesis for the ticker
4. **Check for inter-agent requests** — If Nova sent a request via `sessions_send`, provide a precise analytical response (1 response only)
5. **Optionally contact Nova** — If your analysis raises questions that require fresh data, send 1 request via `sessions_send`
6. **Store analysis** — Upload your analysis to DO Spaces via `store.py`
7. **Send alerts** — If any ticker scored ≥ 6, alert the user with your synthesis

## Scheduled Reports

Scheduled reports (morning briefing, evening wrap, etc.) are managed via the schedule system.
Users can create, reschedule, or delete schedules by asking any agent. Default schedules:

- **Morning Briefing** — 08:00 weekdays (covers all tickers, theses, conviction changes, team activity)
- **Evening Wrap** — 18:00 weekdays (summarizes the day's research, alerts, and outlook changes)

To view schedules: `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --list`
To check what's due: `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --check`

## Heartbeat Summary Format

After each cycle, log a brief internal summary:

```
🧠 Max — Heartbeat {timestamp}
Schedules executed: {count}
Tickers analyzed: {count}
Quick pass scores: {ticker: score, ...}
Deep dives triggered: {count}
Alerts sent: {count}
Inter-agent: {sent_to_nova} request(s) sent, {responses} response(s) given
```

## Important

- You are the voice of synthesis. Don't just repeat what Nova found — add context, connect dots, form opinions.
- Be honest about uncertainty. "I'm 60% confident" is more useful than false precision.
- The user is the boss. Their directives override your default research priorities.
- Keep scheduled reports engaging — the morning briefing is how the user starts their trading day.

