# Job-Hunt Outreach Agent

Warm, one-to-one LinkedIn outreach for a job search — driven by Claude Code.

The candidate reaches out to the people who can hire, refer, or influence hiring for the role they want (hiring managers, engineering leaders, founders, recruiters). Every message references something specific and positions the candidate as a strong, selective professional. It is **not** mass-applying and **not** generic "I'm looking for a job" spam.

Each job-seeker is configured as a **campaign** (their background, target role, geography). One deployment runs one person's search under one LinkedIn account, with daily safety caps and a human-in-the-loop Telegram approval step.

## How it works

```
campaign brief (markdown)
        │
        ▼
hourly cron (`linkedin daily`)  →  drafts via the message-drafter subagent
        │
        ▼
Telegram bot (Approve / Edit / Reject on your phone)
        │
        ▼
Unipile API → LinkedIn
```

Pipeline: `targeted → reacted → connection_sent → connected → dm_sent → replied`, gated by daily caps (default 30 reactions / 20 connections / 10 DMs) and a 9-5 Mon-Fri send window.

## Quick start

```bash
./setup.sh                                   # venv, deps, Playwright, DB init, .env
linkedin campaign create my-search           # scaffold a candidate brief
$EDITOR campaigns/my-search.md               # fill in background, target role, proof points
linkedin validate-query "engineering manager fintech" --campaign my-search
linkedin search "engineering manager fintech" --campaign my-search --limit 8
linkedin daily                               # run a cycle; approve drafts in Telegram
```

See `CLAUDE.md` for the full campaign-creation protocol and CLI reference. Start by copying `campaigns/_example-candidate.md`.

## Configuration

Copy `.env.example` to `.env` and fill in your Unipile and Telegram credentials. Key vars:

- `UNIPILE_API_KEY` / `UNIPILE_ACCOUNT_ID` / `UNIPILE_DSN` — LinkedIn access via Unipile
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — approval bot
- `DAILY_MAX_*` — rate caps
- `LINKEDIN_DB_PATH` — override the SQLite location (default `data/outreach.db`)

## Tests

```bash
pytest            # unit + integration (live/slow excluded by default)
pytest -m live    # hits the real Unipile API (needs credentials)
```
