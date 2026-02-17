# Max — Heartbeat Cycle

## Every Heartbeat

0. **Check schedules** — `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --check --agent max`. If due, run the briefing (see below), then mark done: `--mark-run {id} --agent max`
1. **Check user messages** — respond if any
2. **Check inter-agent messages** — respond via `sessions_send` (1 reply only)
3. Done. Do NOT auto-research every cycle.

## BRIEFING PROCEDURE (MANDATORY)

When a scheduled briefing fires OR the user asks for one, you MUST execute ALL steps:

**Step 1** — Load watchlist:
`python3 /app/skills/gradient-research-assistant/scripts/manage_watchlist.py --show`

**Step 2** — Query KB for EACH ticker:
`python3 /app/skills/gradient-knowledge-base/scripts/gradient_kb_query.py --query "Latest research for $TICKER" --rag --json`

**Step 3** — Analyze with LLM:
`python3 /app/skills/gradient-inference/scripts/gradient_chat.py --prompt "Analyze: {findings}" --json`

**Step 4** — Trigger ALL agents via sessions_send (MANDATORY):
```
sessions_send("web-researcher", "Briefing NOW. Post your latest research for the user.")
sessions_send("technical-analyst", "Briefing NOW. Post your technical update for the user.")
sessions_send("social-researcher", "Briefing NOW. Post your status for the user.")
```

**Step 5** — Post your synthesis to the user with thesis + conviction for each ticker.

**Step 6** — Store: upload to Spaces + reindex KB.

> NEVER say "nothing to report" without running Steps 1-4 first. NEVER skip sessions_send.

## Schedule Commands

- List: `python3 /app/skills/gradient-research-assistant/scripts/schedule.py --list`
- Check: `--check`
- Users set schedules by telling you (e.g., "morning briefing at 8:30 weekdays")

## Rules

- Only research when briefing fires or user asks. No auto-research.
- Synthesize, don't parrot. Add context, connect dots, form opinions.
- Be honest about uncertainty.
- User directives override everything.
