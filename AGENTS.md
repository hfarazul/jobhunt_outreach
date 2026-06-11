# Job-Hunt Outreach Agent — warm LinkedIn outreach for a job search

This project runs LinkedIn outreach for a **job search**. **You — the coding agent (Claude Code, Codex, Cursor, Gemini, …) — are the operator.** The Python package `linkedin_agent` is the toolkit you drive. This file is the canonical guide; `CLAUDE.md` points here.

The candidate reaches out — warmly and one-to-one — to the people who can hire, refer, or influence hiring for the role they want: hiring managers, engineering leaders, founders at smaller companies, and recruiters. It is **not** mass-applying and **not** spraying generic "I'm looking for a job" notes. Every message references something specific and positions the candidate as a strong, selective professional.

This repo is a **reusable toolkit**: each job-seeker is configured as their own *campaign* (their background, target role, geography). One deployment runs one person's search under one LinkedIn account.

## Works with any agent — and Telegram is optional

There are two ways to run this, and **neither requires an LLM API key** — drafting is done by a coding agent CLI you already have authenticated:

1. **Interactive (recommended, any agent).** You — Claude Code / Codex / Cursor — drive the CLI directly: search, review, draft the message yourself from the campaign brief + context, and send via `linkedin connect/dm`. **You are the human-in-the-loop**, so **Telegram is not needed at all.** Nothing here is Claude-specific.
2. **Unattended (cron).** `linkedin daily` runs autonomously and drafts messages by shelling out to a coding-agent CLI (see *Drafting agent* below). In this mode, **Telegram is the optional approval channel** — approve/reject on your phone. If no Telegram credentials are set, `daily`/`poll` still run and simply skip notifications (drafts wait in the DB as `pending`).

**Telegram is therefore optional.** Set it up only if you want unattended runs with phone approvals. The whole interactive flow works without it.

### Drafting agent

The unattended drafter picks a coding-agent CLI in this order: `DRAFTER_AGENT_CMD` (a custom command prefix) → `DRAFTER_AGENT` (`claude` | `codex` | `cursor` | `gemini`) → auto-detect the first of `claude`, `codex`, `cursor-agent`, `gemini` on `PATH`. Override per machine in `.env`. (Implemented in `linkedin_agent/agent_cli.py`.) When *you* drive interactively, this isn't used — you write the drafts.

## The system in 30 seconds

```
campaign brief (markdown — one per candidate)
        │
        ▼
either: you (the agent) drive the CLI interactively   ──┐
   or:  hourly cron (`linkedin daily`) drafts via a      │
        coding-agent CLI                                 ▼
        │                                    human review (you, OR
        │  - syncs campaigns from markdown    Telegram Approve/Edit/Reject)
        │  - polls for inbound replies                   │
        │  - reacts to recipients' recent posts          ▼
        │  - drafts connect notes / DM1 / DM2 / DM3   Unipile API → LinkedIn
```

Drafts approved outside business hours stay queued until the next 9-5 Mon-Fri window (unless `LINKEDIN_DISABLE_SEND_WINDOW=1`).

## Campaign-first workflow

Every recipient belongs to a campaign, and **a campaign represents one candidate's search** (or one slice of it — e.g. a person running both "senior backend" and "platform lead" tracks). Campaigns are markdown files under `campaigns/`:

```
campaigns/
├── _example-candidate.md   # reference brief — copy this, archived so it never runs
├── jane-backend.md         # Jane's senior-backend search
```

Each file has YAML frontmatter (slug, name, status, target_icp, ICP overrides) plus a markdown body describing **the candidate**: their background, what they're looking for, proof points, anti-claims, tone. The drafter reads this file when generating messages, so editing the brief immediately changes the drafted output.

To create one: `linkedin campaign create <slug>` scaffolds the file; edit it; `linkedin campaign sync` (or any `daily` run) refreshes the DB.

## Pipeline stages

```
targeted → reacted → connection_sent → connected → dm_sent → replied
```

Plus a `disposition` column (set after a conversation begins). The stored values are generic; for a job search read them as:

| value | job-hunt meaning |
|---|---|
| `interested` | in a live conversation — they engaged |
| `won` | landed it — offer / accepted / strong referral made |
| `lost` | rejected, passed, or role filled |
| `not_fit` | not a match for what the candidate wants |
| `deferred` | good contact, wrong timing — revisit later |
| `ghosted` | auto-applied 14 days after DM3 with no reply |

`ghosted` auto-applies; the rest are manual flags set after talking.

## Daily ops — what the cron does

| Step | What | Human approval |
|---|---|---|
| `campaigns sync` | Refresh DB from markdown files | — |
| `poll` | Fetch inbound replies, halt sequences, **auto-draft a reply** | **Yes** |
| `react` | Like a recent post of each `targeted` recipient → `reacted` | No (low stakes) |
| `connect` | Draft a connect note for each `reacted` recipient | **Yes** |
| `dm1` | Draft first DM for each `connected` recipient | **Yes** |
| `followup` | Draft DM2 (after 4d) / DM3 (after 11d) for `dm_sent` | **Yes** |
| `send-approved` | Flush drafts approved outside the business-hours window | — |
| `auto-ghost` | Mark stale `dm_count=3` recipients as `ghosted` | — |

In unattended mode, "approval" is a Telegram card (tap to approve, swipe to reject, Edit to rewrite). In interactive mode, *you* are the approval — show the draft, get an OK, then send.

## When the agent is needed (interactive)

The cron handles everything *mechanical*. You (the agent) are for the parts that benefit from judgment:

1. **Setting up a new candidate's campaign** — follow the protocol below. Don't just `campaign create` and leave the brief blank.
2. **Recrafting a reply the auto-drafter got wrong** — nuanced replies (overqualified pushback, "no openings right now but…", scheduling, a tricky question about the candidate's background). Read the full thread (`messages` table) + the campaign brief, draft, send via `linkedin dm <pid> "..."`.
3. **Tuning the drafter prompt** — iterate on `.claude/agents/message-drafter.md`, then rerun `linkedin daily` to see the new style. (The file lives under `.claude/agents/` for historical reasons but is plain text any agent can edit; it's what the autonomous drafter loads.)
4. **One-off recipient work** — "Draft a custom DM2 for recipient 5 — they asked what I've shipped."

## Campaign-creation protocol — follow this every time

When the user says "set up my search" / "I want to target X roles" / similar:

### Phase 1 — Clarifying questions (ask all 8)

Push for specificity on each — vague answers produce templated messages:

1. **Who is the candidate?** Role, years, the kind of work they do best, what they want next.
2. **Which roles, specifically?** Title + seniority + company stage/size.
3. **Where?** Country/region/cities, or remote-first.
4. **Who do we message?** Hiring managers? Eng leads? Founders (small cos)? Recruiters? Name the priority.
5. **Proof points?** 2-3 concrete, true accomplishments the candidate can lead with.
6. **Anti-claims?** What to never say — no fabricated experience, no sounding desperate, no copying the job post.
7. **Tone?** Peer-to-peer / direct / warm / technical. Selective, not begging.
8. **Search queries?** 2-3 LinkedIn classic-search keyword strings that surface the right *recipients*.

### Phase 2 — Search validation (mandatory gate)

```
linkedin validate-query "<query>" --limit 10 --campaign <slug-once-created>
```

Grades each result on geography + hiring-side role + noise exclusion (other job-seekers). Exits 0 if keepers ≥ 6/10. If a query fails, iterate. Use only queries that pass.

### Phase 3 — Generate the brief

Write `campaigns/<slug>.md` from the answers, using `campaigns/_example-candidate.md` as the canon. Set the ICP frontmatter overrides (`icp_role_required` / `icp_role_excluded` / `icp_geo_required`). Then `linkedin campaign sync` and show the rendered brief.

> Personal briefs contain real history — keep them **local to that deployment**; don't commit them to a shared repo.

### Phase 4 — First import is small

**Import 5-10 first**, eyeball them in `linkedin pipeline --status targeted`, and scale up only after a couple reach `connected`.

## Two ways to source who you reach out to

1. **People search** — find hiring-side people directly: `linkedin validate-query "..."` then `linkedin search "..." --campaign <slug>`.
2. **Job-driven** — start from live job postings, then reach the people who own the role: `linkedin jobs "AI engineer" --location London --date-posted 7` → pick a role → `linkedin job-import <job_id> --campaign <slug>` (pulls the posting's recruiter/hiring team **and** the company's managers, with the role attached as context). See the `job-driven-outreach` skill in `.claude/skills/`.

## CLI reference

All commands are `python -m linkedin_agent <subcommand>` (or `linkedin <subcommand>` in the venv).

### Day-to-day
| Command | Purpose |
|---|---|
| `status` | Dashboard: caps, window, pipeline by stage, replies, due follow-ups |
| `daily` | Run the full cron cycle once |
| `caps` / `poll` / `pipeline [--status STATUS]` | Caps · fetch replies · list recipients |

### Campaigns
| Command | Purpose |
|---|---|
| `campaign create <slug>` / `sync` / `list` / `show <slug>` / `archive <slug>` / `assign <pid> <slug>` | Manage campaigns |

### Discovery + manual outreach
| Command | Purpose |
|---|---|
| `search "<query>" --campaign <slug> --limit N` | People search + import |
| `search-posts "<keywords>" --campaign <slug>` | Import people posting about a topic |
| `jobs "<keywords>" --location <city> --date-posted N` | Search job postings (read-only) |
| `job-import <job_id> --campaign <slug>` | Import a job's hiring team + managers |
| `validate-query "<query>" --campaign <slug>` | Grade a query before importing |
| `posts <pid>` / `react <pid>` / `connect <pid> --note "..."` / `dm <pid> "..."` | Manual actions |

### Telegram (optional — unattended mode only)
| Command | Purpose |
|---|---|
| `bot-run` | Start the Telegram daemon (long-running) |
| `telegram-test` / `telegram-push-draft <id>` | Sanity / re-push |

## Safety rules

1. **Never bypass the CLI.** Adapter methods don't enforce rate limits. Always use `python -m linkedin_agent <subcommand>`.
2. **Always check `caps` or `status` before bulk actions.** Hard caps (default 30 reactions / 20 connections / 10 DMs / 50 searches per 24h) will raise.
3. **Get human approval before any LinkedIn-visible send.** In unattended mode that's the Telegram Approve button; in interactive mode, show the draft and get an explicit OK. Never auto-blast.
4. **Verify factual hooks.** If a draft cites a specific company/tech detail, confirm it's real before sending — never a hallucinated claim to a real person. Truthful positioning only.
5. **Stop if anything looks off.** Captcha screens, "unusual activity" warnings, or unexpected 4xx responses → tell the user, don't retry.

## State

- DB: `data/outreach.db` (SQLite). Inspect with `sqlite3 data/outreach.db`.
- Campaign briefs: `campaigns/*.md`. Source of truth — DB rows are derived.
- Config: `.env` (Unipile creds; optional Telegram; optional `DRAFTER_AGENT`).
- Action log: `actions` table — every API call, drafter result, status transition.

## Deployment

For unattended 24/7 operation use a dedicated always-on Mac. Run `setup.sh`, (optionally) install the bot daemon with `scripts/install_launchd.sh` (LaunchAgent `com.jobhunt.linkedin-bot`), and add the daily cron from `scripts/daily_outreach.sh`. Make sure the cron machine has a coding-agent CLI on `PATH` (or `DRAFTER_AGENT_CMD` set) for the autonomous drafter. Per-machine state to migrate: `data/outreach.db`, `.env`, `campaigns/*.md`.
