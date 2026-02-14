```
                           ___
                        .-'   `'.
                       /         \
                      |    $$     ;    "The chart sees it first."
                      |    {}     |
                 _.-- '. \_____/ .'
               .'     / `'---'` \
              /      /  /)    (\  \
             |      | .'/      \'. |      📈 📉 📊
             |      |/ /  ____  \ \|
              \     / /  |    |  \ \     ┌──────────────────┐
               `'-.|/    | $$ |   \|     │ BUY  HOLD  SELL  │
                   /     |____|    \     │ ███░ ████░ ██░░░ │
            _.---'`  /              `    └──────────────────┘
          .'       .' '.          .' '.
         /  _    .'     '-.  _.-'     '.
        |  ( `.'            `           |
       /    `. \     STONKS    / .'    \
      | .  .  ` `.     ↗↗    .' `  .   |
      |  \  \    | `'------'` |   /  / |
       \  `. `.  |            |  .' .'
        \    `-. \   🦞🦞🦞   / .-`
         `-._   `'-.____.--'`  _.-'
              `'--._________.--'`
```

# OpenClaw + Gradient AI Research Assistant

A proactive investment research assistant powered by [Gradient AI](https://www.digitalocean.com/products/ai-ml) models via [OpenClaw](https://openclaw.ai). Deploy it to a DigitalOcean Droplet in minutes.

---

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                             ║
║   ░██╗░░░░░░░██╗░█████╗░██████╗░███╗░░██╗██╗███╗░░██╗░██████╗░            ║
║   ░██║░░██╗░░██║██╔══██╗██╔══██╗████╗░██║██║████╗░██║██╔════╝░            ║
║   ░╚██╗████╗██╔╝███████║██████╔╝██╔██╗██║██║██╔██╗██║██║░░██╗░            ║
║   ░░████╔═████║░██╔══██║██╔══██╗██║╚████║██║██║╚████║██║░░╚██╗            ║
║   ░░╚██╔╝░╚██╔╝░██║░░██║██║░░██║██║░╚███║██║██║░╚███║╚██████╔╝            ║
║   ░░░╚═╝░░░╚═╝░░╚═╝░░╚═╝╚═╝░░╚═╝╚═╝░░╚══╝╚═╝╚═╝░░╚══╝░╚═════╝░            ║
║                                                                             ║
║   🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴🌴   ║
║                                                                             ║
║   THIS SOFTWARE IS A DEMO.  A PROTOTYPE.  A VIBE.                          ║
║                                                                             ║
║   OpenClaw is early-stage software with KNOWN SECURITY VULNERABILITIES.     ║
║   This project lets LLM agents execute arbitrary Python on your machine.    ║
║   There is NO sandboxing, NO rate limiting, and NO safety net.              ║
║                                                                             ║
║   🚨  YOU RUN THIS AT YOUR OWN RISK.  🚨                                   ║
║                                                                             ║
║   And while we're here — WATCH YOUR TOKEN USAGE.                            ║
║   These four agents will burn through API credits like it's Miami in '85.   ║
║   Every research cycle, every cron trigger, every follow-up question —      ║
║   that's tokens. Set billing alerts. Check your dashboard. Be vigilant.     ║
║                                                                             ║
║   Don't say we didn't warn you. 🕶️                                         ║
║                                                                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

---

## What This Is (And Isn't)

This is a **fun showcase** of what's possible when you combine [OpenClaw's](https://openclaw.ai) multi-agent framework with [Gradient AI](https://www.digitalocean.com/products/ai-ml) models. You get a team of four AI analysts working together to research stocks and report back via Telegram. It's cool. It's kinda wild. It actually works.

**What it is NOT:**
- ❌ Production-grade financial software
- ❌ A secure, hardened application
- ❌ Financial advice of any kind
- ❌ A reason to YOLO your 401k based on what a lobster-themed chatbot tells you

OpenClaw has **major security limitations** in its current state. This project is meant to show the *potential* of the platform — not to be deployed in any environment where security matters. See [Known Limitations](#known-limitations--security-caveats) below.

---

## Meet the Team

| Agent | Role | Vibe | Specialty |
|-------|------|------|-----------|
| 🧠 **Max** | Fundamental Analyst & Team Lead | The senior quant who's seen every cycle. Dry, nerdy humor. Drops obscure financial history references. | Synthesizes news + filings + sentiment into investment theses. Delivers the morning briefing. |
| 📰 **Nova** | Web Researcher | The pedantic librarian. "It's a Form 8-K, not 'some SEC filing'." | SEC filings, press releases, official sources. Citation-obsessed. Primary source purist. |
| 📱 **Luna** | Social Researcher | Trend whisperer with Instagram-pro polish. Reads Reddit like a first language. | Social sentiment, retail crowd behavior, FOMO detection. Spots hype vs. momentum. |
| 📈 **Ace** | Technical Analyst | YouTuber chartist energy. "Alright, let's break this chart down." No BS. | Price action, support/resistance, indicators (RSI, MACD, Bollinger). The chart sees it first. |

---

## What It Does

- 📊 Monitors a watchlist of stock tickers
- 🔍 Gathers research from news, Reddit, SEC filings, and social media
- 🧠 Stores findings in a Gradient Knowledge Base for RAG queries
- 🚨 Proactively alerts you via Telegram when something significant happens
- 💬 Answers questions about your watchlist using accumulated knowledge
- 🤖 Four specialized agents working as a coordinated research team

## Architecture

```
Telegram → OpenClaw Gateway → Gradient AI (GPT OSS 120B)
                ↓
         exec tool → Python skills
                ↓
         DO Spaces + Gradient KB
```

## Known Limitations & Security Caveats

> **This section exists because we believe in being upfront.** OpenClaw is exciting tech, but it's not ready for anything resembling production use in sensitive environments.

| Risk | Details |
|------|---------|
| 🔓 **Arbitrary Code Execution** | Agents execute Python via `exec`. There is no sandbox. A sufficiently creative (or confused) agent could do anything your host OS allows. |
| 🚫 **No Rate Limiting** | Nothing prevents agents from making unlimited API calls. A runaway loop = a runaway bill. |
| 🔑 **Minimal Authentication** | The only access control is Telegram pairing. Anyone with bot access can trigger agent actions. |
| 💸 **Token Burn** | Each research cycle across all 4 agents consumes a significant number of tokens. Cron-triggered cycles compound this. **Set billing alerts on your Gradient AI account.** |
| 🌐 **Network Exposure** | Agents make outbound HTTP requests to third-party APIs (Reddit, news sources, SEC EDGAR). No request filtering is applied. |

---

## Quick Start

### 1. Prepare Your Environment

```bash
git clone https://github.com/Rogue-Iteration/openclaw-do-gradient.git
cd openclaw-do-gradient
cp .env.example .env
```

Open `.env` in your editor — you'll fill in each key as you create it below.

### 2. Prerequisites

<details>
<summary><strong>Gradient AI Model Access Key</strong></summary>

1. Log into the [DigitalOcean Console](https://cloud.digitalocean.com)
2. Go to **Agent Platform**
3. Click **Create model access key**
4. Copy the key → paste into `.env` as `GRADIENT_API_KEY`
</details>

<details>
<summary><strong>Telegram Bot</strong></summary>

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **HTTP API token** → paste into `.env` as `TELEGRAM_BOT_TOKEN`
</details>

<details>
<summary><strong>DigitalOcean API Token</strong></summary>

Only needed if deploying via `install.sh`. Skip if running Docker locally.

1. [DigitalOcean Console](https://cloud.digitalocean.com) → **API**
2. Click **Generate New Token**
3. Scope: **Full Access** (or minimum: Droplet, GenAI, Spaces)
4. Copy the token → paste into `.env` as `DO_API_TOKEN`
</details>

<details>
<summary><strong>DigitalOcean Spaces (Object Storage)</strong></summary>

1. [DigitalOcean Console](https://cloud.digitalocean.com) → **Spaces Object Storage**
2. Click **Create Bucket**, pick a region (e.g., `nyc3`) and name (e.g., `openclawresearch`)
3. Select the **Access Keys** tab
4. Create a key with **full access** to your bucket
5. Copy the access key and secret → paste into `.env` as `DO_SPACES_ACCESS_KEY` and `DO_SPACES_SECRET_KEY`
6. Set `DO_SPACES_ENDPOINT` to match your region (e.g., `https://nyc3.digitaloceanspaces.com`)
7. Set `DO_SPACES_BUCKET` to your bucket name
</details>

<details>
<summary><strong>Gradient Knowledge Base</strong></summary>

1. [DigitalOcean Console](https://cloud.digitalocean.com) → **Agent Platform** → **Knowledge Bases** tab
2. Click **Create Knowledge Base**
3. Select your Spaces bucket (created above) as the data source
4. Copy the **UUID** from the Knowledge Base detail page → paste into `.env` as `GRADIENT_KB_UUID`
</details>

### 3. Deploy

```bash
# Validate your config
bash install.sh --dry-run

# Deploy to DigitalOcean
bash install.sh
```

The script will create a Droplet, deploy the bot, and print connection details.

### Pair Your Telegram

After deploying, pair your Telegram account:

1. Send any message to your bot on Telegram
2. It will reply with a **pairing code**
3. Approve it:
   ```bash
   # Local Docker:
   docker exec openclaw-research openclaw pairing approve telegram <CODE>

   # On a Droplet:
   ssh root@<droplet-ip> docker exec openclaw-research openclaw pairing approve telegram <CODE>
   ```

Your bot is now live! 🎉

## Updating

### From your local machine

```bash
bash install.sh --update
```

### On the Droplet

```bash
cd /opt/openclaw && bash deploy.sh
```

## Manual / Local Setup

If you don't want to use DigitalOcean, you can run the bot anywhere with Docker:

```bash
git clone https://github.com/Rogue-Iteration/openclaw-do-gradient.git
cd openclaw-do-gradient
cp .env.example .env
# Fill in .env
docker compose up -d
```

## Management

```bash
# SSH into Droplet
ssh root@<droplet-ip>

# View logs
docker logs -f openclaw-research

# Restart
docker compose restart

# Stop
docker compose down
```

## Development

### Running Tests

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

### Project Structure

```
├── skills/gradient-research-assistant/   # Shared skill tools (Python)
├── skills/{agent-name}/                  # Agent-specific skills
├── data/workspace/                       # Shared persona files
├── data/workspaces/{agent-name}/         # Per-agent persona files
├── tests/                                # Unit tests
├── Dockerfile                            # Container build
├── docker-compose.yml                    # Container orchestration
├── docker-entrypoint.sh                  # First-run setup
├── install.sh                            # DigitalOcean deploy script
├── deploy.sh                             # On-server update script
└── .env.example                          # Environment variable template
```

## License

MIT
