# OpenClaw + Gradient AI — Investment Research Assistant

An AI-powered research assistant that monitors your stock watchlist, gathers intelligence from multiple sources, and delivers actionable alerts — all manageable through chat.

Built on [OpenClaw](https://openclaw.com) with [DigitalOcean Gradient AI](https://www.digitalocean.com/products/gradient-ai) for inference and knowledge retrieval.

## What It Does

| Feature | How It Works |
|---------|-------------|
| **Watchlist management** | Add/remove tickers, set custom alert rules — all via chat |
| **Multi-source intelligence** | Gathers news, Reddit sentiment, SEC filings per ticker |
| **AI-powered analysis** | Gradient AI scores significance and generates summaries |
| **Knowledge Base** | Research stored in DO Spaces, indexed for RAG queries |
| **Automated heartbeat** | Runs the gather→analyze→store→alert cycle periodically |
| **Chat-first** | Connect via Telegram, WhatsApp, Signal, or Discord |

## Architecture

```
You ↔ Telegram/WhatsApp ↔ OpenClaw Gateway ↔ Gradient AI (inference)
                                    ↓
                          Research Skill (Python)
                          ├── gather.py      → News, Reddit, SEC
                          ├── analyze.py     → AI scoring + summaries
                          ├── store.py       → Upload to Spaces → KB
                          ├── alert.py       → Format notifications
                          ├── query_kb.py    → RAG queries
                          └── manage_watchlist.py → Watchlist CRUD
```

## Quick Start

### Option A: Deploy to DigitalOcean App Platform

**Cost**: ~$24/mo for the 2GB worker (OpenClaw requires 2GB RAM minimum) + inference costs.

#### Prerequisites
- [DigitalOcean account](https://cloud.digitalocean.com)
- [doctl CLI](https://docs.digitalocean.com/reference/doctl/how-to/install/) installed and authenticated

#### Step 1: Create Your Resources

| # | What to Create | Where | What You'll Get |
|---|---------------|-------|-----------------|
| 1 | **API Token** | [API → Tokens](https://cloud.digitalocean.com/account/api/tokens) | `dop_v1_...` |
| 2 | **Gradient AI Key** | [Gradient AI → API Keys](https://cloud.digitalocean.com/gen-ai/api-keys) | API key for inference |
| 3 | **Spaces Bucket** | [Spaces → Create](https://cloud.digitalocean.com/spaces/new) | Bucket name |
| 4 | **Spaces Keys** | [API → Spaces Keys](https://cloud.digitalocean.com/account/api/spaces) | Access Key + Secret |
| 5 | **Knowledge Base** | [Gradient AI → Knowledge Bases](https://cloud.digitalocean.com/gen-ai/knowledge-bases) | UUID from the URL |

> [!TIP]
> Connect your Spaces bucket as a data source for the Knowledge Base — this is how the assistant stores and retrieves research.

#### Step 2: Deploy

```bash
# Clone and deploy
git clone https://github.com/Rogue-Iteration/openclaw-do-gradient.git
cd openclaw-do-gradient
doctl apps create --spec .do/app.yaml --wait
```

#### Step 3: Add Your Secrets

1. Go to [DigitalOcean Apps Dashboard](https://cloud.digitalocean.com/apps)
2. Click **openclaw-research** → **Settings** → **openclaw** component → **Environment Variables**
3. Add each secret:

| Variable | What to Enter |
|----------|---------------|
| `GRADIENT_API_KEY` | Your Gradient AI API key |
| `OPENCLAW_GATEWAY_TOKEN` | Any strong password (for gateway auth) |
| `RESTIC_SPACES_ACCESS_KEY_ID` | Spaces access key (for persistence) |
| `RESTIC_SPACES_SECRET_ACCESS_KEY` | Spaces secret key |
| `RESTIC_PASSWORD` | Any strong password (encrypts backups) |
| `DO_API_TOKEN` | Your API token (for KB re-indexing) |
| `DO_SPACES_ACCESS_KEY` | Spaces access key (for research uploads) |
| `DO_SPACES_SECRET_KEY` | Spaces secret key |
| `GRADIENT_KB_UUID` | Your Knowledge Base UUID |

4. Click **Save** — the app will redeploy with secrets.

### Option B: Run Locally

```bash
# Install OpenClaw
brew install node
npm install -g pnpm
pnpm add -g openclaw

# Clone and set up
git clone https://github.com/Rogue-Iteration/openclaw-do-gradient.git
cd openclaw-do-gradient
cp .env.example .env
# Edit .env with your credentials

# Install Python deps
pip install -r requirements.txt

# Start OpenClaw with Gradient AI
export GRADIENT_API_KEY="your-key"
openclaw gateway --allow-unconfigured
```

## Gradient AI Models

The assistant ships with these pre-configured models (switchable at runtime):

| Model | Best For | Switch Command |
|-------|----------|---------------|
| **Llama 3.3 70B** (default) | General analysis, summaries | `/model gradient/llama3.3-70b-instruct` |
| **DeepSeek R1 70B** | Complex financial reasoning | `/model gradient/deepseek-r1-distill-llama-70b` |
| **Qwen3 32B** | Quick tasks, lighter workloads | `/model gradient/qwen3-32b` |
| **GPT OSS 120B** | High-quality analysis | `/model gradient/openai-gpt-oss-120b` |

You can switch models anytime in chat — no redeploy needed.

## Chat Commands

Once connected via Telegram, WhatsApp, Signal, or Discord:

```
"Add AAPL to my watchlist"
"Remove TSLA"
"Set price movement threshold for AAPL to 3%"
"Show my watchlist"
"What's the latest research on AAPL?"
"Run a research cycle now"
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GRADIENT_API_KEY` | ✅ | Gradient AI inference key |
| `OPENCLAW_GATEWAY_TOKEN` | ✅ | Gateway authentication token |
| `DO_API_TOKEN` | ✅ | DigitalOcean API token (KB re-indexing) |
| `DO_SPACES_ACCESS_KEY` | ✅ | Spaces access key (research uploads) |
| `DO_SPACES_SECRET_KEY` | ✅ | Spaces secret key |
| `DO_SPACES_ENDPOINT` | | Spaces endpoint (default: `https://nyc3.digitaloceanspaces.com`) |
| `DO_SPACES_BUCKET` | | Spaces bucket name (default: `openclaw-research`) |
| `GRADIENT_KB_UUID` | ✅ | Knowledge Base UUID for RAG queries |
| `RESTIC_PASSWORD` | | Encryption password for backups (App Platform only) |

## Development

```bash
# Run tests
pip install -r requirements.txt
pytest tests/ -v

# Build Docker image locally
docker build -t openclaw-research .
docker run -it --env-file .env openclaw-research
```

## Based On

This project extends the [digitalocean-labs/openclaw-appplatform](https://github.com/digitalocean-labs/openclaw-appplatform) template with a custom research assistant skill.

## License

MIT
