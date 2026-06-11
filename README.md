# Job-Hunt Outreach Agent

Warm, one-to-one LinkedIn outreach for a job search — driven by your coding agent (Claude Code, Codex, Cursor, Gemini, …).

The candidate reaches out to the people who can hire, refer, or influence hiring for the role they want (hiring managers, engineering leaders, founders, recruiters). Every message references something specific and positions the candidate as a strong, selective professional. It is **not** mass-applying and **not** generic "I'm looking for a job" spam.

Each job-seeker is configured as a **campaign** (their background, target role, geography). One deployment runs one person's search under one LinkedIn account, with daily safety caps and a human-in-the-loop approval step.

## Two ways to run (no LLM API key — drafting uses a coding-agent CLI)

1. **Interactive (any agent).** You drive the CLI directly — search, review, draft the message yourself from the brief, send via `linkedin connect/dm`. You are the human-in-the-loop, so **Telegram is not needed**. Works with any agent; nothing is Claude-specific.
2. **Unattended (cron).** `linkedin daily` runs autonomously and drafts by shelling out to a coding-agent CLI (`claude` / `codex` / `cursor-agent` / `gemini`, configurable via `DRAFTER_AGENT`). Here **Telegram is the optional approval channel** — Approve/Edit/Reject on your phone. Without Telegram creds it still runs and just skips notifications.

```
campaign brief (markdown)
        │
        ▼
you drive the CLI  ── or ──  hourly cron (`linkedin daily`) drafts via a coding-agent CLI
        │                                   │
        ▼                                   ▼
   you review + send          human review (you, or Telegram Approve/Edit/Reject)
                                            │
                                            ▼
                                   Unipile API → LinkedIn
```

Pipeline: `targeted → reacted → connection_sent → connected → dm_sent → replied`, gated by daily caps (default 30 reactions / 20 connections / 10 DMs) and a 9-5 Mon-Fri send window.

See `AGENTS.md` (the canonical agent guide; `CLAUDE.md` points to it) for the full playbook.

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

## Two ways to source who you reach out to

1. **People search** — find hiring-side people directly by keyword:
   `linkedin validate-query "engineering manager fintech" --campaign <slug>` then `linkedin search ...`.
2. **Job-driven** — start from live job postings, then reach the people who own the role:
   `linkedin jobs "AI engineer" --location London --date-posted 7` → pick a role → `linkedin job-import <job_id> --campaign <slug>` (pulls the posting's recruiter/hiring team **and** the company's managers, with the role attached as context). See the `job-driven-outreach` skill in `.claude/skills/`.

Both feed the same pipeline: review → connect note → DM after they accept.

## Setting up for a new person

This toolkit is reusable: **each job-seeker is a separate deployment** — their own LinkedIn account, their own `.env`, their own database, their own Telegram chat, and their own campaign brief. Nothing is shared between two people except the code. To onboard someone new:

### 1. Get the code onto their machine
```bash
git clone <this-repo-url> ~/jobhunt_outreach
cd ~/jobhunt_outreach
./setup.sh          # creates the venv, installs deps + Playwright, inits an empty DB, copies .env.example → .env
```
`setup.sh` prefers the newest Python it can find (3.11+ required).

### 2. Connect *their* LinkedIn account
Each person outreaches from **their own** LinkedIn profile — never a shared one (mixing identities and sharing the daily action budget gets accounts flagged). In your [Unipile](https://www.unipile.com) dashboard, connect that person's LinkedIn account, then copy into their `.env`:
- `UNIPILE_API_KEY`, `UNIPILE_ACCOUNT_ID` (the account id for *their* profile), `UNIPILE_DSN`

### 3. Give them their own Telegram approval bot
Approvals land on the candidate's phone, so they need their own bot + chat:
1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Start a chat with the new bot, then run `linkedin telegram-test` — it tells you the `TELEGRAM_CHAT_ID` to set (or use a chat-id lookup bot).

> Don't reuse one Telegram bot token across two running deployments — LinkedIn-style long-polling allows only one consumer per token, so the second daemon collides with the first.

### 4. Write their candidate campaign
This is what positions them — spend time here. Either run the 8-question protocol in `CLAUDE.md` interactively with Claude Code, or by hand:
```bash
linkedin campaign create <their-slug>
$EDITOR campaigns/<their-slug>.md     # About me · What I'm looking for · Proof points · Anti-claims · Tone
```
Set the ICP overrides in the frontmatter (`icp_role_required` / `icp_role_excluded` / `icp_geo_required`) to match the roles they target and their geography. Copy `campaigns/_example-candidate.md` as the shape.

> Personal campaign briefs contain real history — keep them **local to that deployment**; don't commit them back to the shared repo.

### 5. Validate, then start small
```bash
linkedin validate-query "<a query for the people they'd message>" --campaign <their-slug>   # want ≥6/10 keepers
linkedin search "<that query>" --campaign <their-slug> --limit 8       # OR job-driven: jobs → job-import
linkedin pipeline --status targeted                                    # eyeball the imports
linkedin daily                                                         # drafts → approve on Telegram
```
Import 5–10 first and watch a couple move through to `connected` before scaling up.

### 6. (Optional) Run it 24/7
On a dedicated always-on Mac: install the bot daemon with `scripts/install_launchd.sh` (LaunchAgent `com.jobhunt.linkedin-bot`) and add the daily cron from `scripts/daily_outreach.sh`. The only state to back up / migrate is `data/outreach.db`, `.env`, and `campaigns/*.md`. See `CLAUDE.md → Deployment`.

## Configuration

Copy `.env.example` to `.env` and fill in your Unipile credentials. Key vars:

- `UNIPILE_API_KEY` / `UNIPILE_ACCOUNT_ID` / `UNIPILE_DSN` — LinkedIn access via Unipile (**required**)
- `DAILY_MAX_*` — rate caps
- `LINKEDIN_DB_PATH` — override the SQLite location (default `data/outreach.db`)
- `DRAFTER_AGENT` / `DRAFTER_AGENT_CMD` — *optional*; which coding-agent CLI the **unattended** drafter uses (auto-detects `claude` / `codex` / `cursor-agent` / `gemini` if unset)
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — *optional*; only for unattended phone-approval. The interactive flow needs neither.

## Tests

```bash
pytest            # unit + integration (live/slow excluded by default)
pytest -m live    # hits the real Unipile API (needs credentials)
```
