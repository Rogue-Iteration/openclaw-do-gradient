# CLAUDE.md — OpenClaw + Gradient AI Research Assistant

## Project Overview

A proactive investment research assistant running in **Docker** on a DigitalOcean Droplet, powered by Gradient AI models via OpenClaw. Four specialized agents (Max, Nova, Luna, Ace) monitor a stock watchlist, gather research from multiple sources, and alert the user via Telegram.

## Architecture

- **Runtime**: OpenClaw gateway running in a Docker container
- **AI Backend**: Gradient AI (GPT OSS 120B, Llama 3.3, DeepSeek R1, Qwen3) via DO Inference API
- **Agents**: Max (fundamental analyst, default), Nova (web researcher), Luna (social researcher), Ace (technical analyst)
- **Messaging**: Telegram bot integration
- **Storage**: DigitalOcean Spaces (S3-compatible) + Gradient Knowledge Base for RAG
- **Skills**: Python scripts in `skills/` — shared (`gradient-research-assistant/`) and agent-specific

## Tech Stack

| Layer         | Technology                                  |
|---------------|---------------------------------------------|
| Language      | Python 3, Bash                              |
| Testing       | pytest, responses (HTTP mocking), moto (S3) |
| Dependencies  | requests, beautifulsoup4, feedparser, boto3, yfinance |
| Infra         | Docker, DigitalOcean Droplet, Spaces, Gradient AI |
| Gateway       | OpenClaw (Node.js / pnpm)                   |
| CI/CD         | GitHub Actions → GHCR                       |

## Key Directories

```
skills/gradient-research-assistant/  → Shared skill tools (gather, analyze, alert, store, etc.)
skills/{agent-name}/                 → Agent-specific skill tools
data/workspace/                      → Shared persona files (IDENTITY, AGENTS, HEARTBEAT)
data/workspaces/{agent-name}/        → Per-agent persona files
tests/                               → pytest unit tests
```

## Deployment

### Production Deployment

**You are expected to handle production deployments yourself.** The workflow is:

1. Commit and push changes to `main`
2. Run locally: `bash install.sh --update`
3. Or SSH into the Droplet: `ssh root@<droplet-ip>` → `cd /opt/openclaw && bash deploy.sh`

`install.sh --update` SCPs the `.env`, pulls latest code, and runs `docker compose up -d --build`.
`deploy.sh` does `git pull` + `docker compose up -d --build` directly on the Droplet.

### First-Time Setup

For deploying a new Droplet from scratch:
1. Fill out `.env` (see `.env.example`)
2. Run `bash install.sh`

See `README.md` for full prerequisites guide.

### Container Management

```bash
docker logs -f openclaw-research    # Tail logs
docker compose restart              # Restart
docker compose down                 # Stop
docker compose up -d --build        # Rebuild and start
```

## Droplet Safety

> **⚠️ Always ask before performing destructive actions on the Droplet.**
>
> This includes but is not limited to:
> - Deleting or overwriting files on the Droplet
> - Stopping or removing Docker containers
> - Modifying `.env` or OpenClaw state files
> - Any `rm`, destructive SSH commands, or `docker system prune`
>
> Non-destructive reads (checking logs, status, listing files) are fine without asking.

## Testing

### Approach

- **Use TDD where it makes sense** — particularly for new skill scripts and data-processing logic where inputs/outputs are well-defined.
- **Otherwise, write test cases afterwards** — especially for integration-style work, persona file changes, or deployment scripts.
- Tests live in `tests/` and follow the naming convention `test_<skill_name>.py`.

### Running Tests

```bash
cd /Users/simoneichenauer/Development/thebigclaw
python3 -m pytest tests/ -v
```

### Test Fixtures

Mock data and fixtures live in `tests/fixtures/`. Tests use `responses` for HTTP mocking and `moto` for S3/Spaces mocking.

## Code Style & Documentation

- **Document files inline** — every Python skill script should have:
  - A module-level docstring explaining what the skill does
  - Docstrings on all public functions describing purpose, parameters, and return values
  - Inline comments for non-obvious logic
- Bash scripts should have header comments and section markers
- Persona files (IDENTITY.md, AGENTS.md, HEARTBEAT.md) use Markdown

## Environment Variables

All secrets live in `.env` (locally and on the Droplet). **Never commit real secrets.**

See `.env.example` for the full list with inline documentation.

## Common Workflows

### Adding a new skill script

1. Create `skills/gradient-research-assistant/<skill_name>.py` (or under an agent-specific dir)
2. Add inline documentation (module docstring + function docstrings)
3. Write tests in `tests/test_<skill_name>.py` (TDD preferred)
4. Run `python3 -m pytest tests/ -v` to verify
5. Push to `main` → CI runs tests → deploy with `bash install.sh --update`

### Updating agent personas

1. Edit the relevant files in `data/workspaces/<agent-name>/`
2. Deploy: `bash install.sh --update` (or `deploy.sh` on the Droplet)
3. The Docker entrypoint syncs persona files on every container start
