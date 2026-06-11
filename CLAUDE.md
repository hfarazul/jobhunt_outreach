# Job-Hunt Outreach Agent — warm LinkedIn outreach for a job search

This project runs LinkedIn outreach for a **job search**. **You (Claude Code) are the agent.** The Python package `linkedin_agent` is the toolkit you drive.

The candidate reaches out — warmly and one-to-one — to the people who can hire, refer, or influence hiring for the role they want: hiring managers, engineering leaders, founders at smaller companies, and recruiters. It is **not** mass-applying and **not** spraying generic "I'm looking for a job" notes. Every message references something specific and positions the candidate as a strong, selective professional.

Day-to-day, most operations are automated by cron. You're invoked when there's *judgment* to apply: setting up a candidate's campaign, drafting a custom message, replying to an interested recruiter or hiring manager.

This repo is a **reusable toolkit**: each job-seeker is configured as their own *campaign* (their background, target role, geography). One deployment runs one person's search under one LinkedIn account.

## The system in 30 seconds

```
campaign brief (markdown — one per candidate)
        │
        ▼
hourly cron (`linkedin daily`)
        │  - syncs campaigns from markdown files
        │  - polls for inbound replies
        │  - reacts to target recipients' recent posts
        │  - drafts connect notes / DM1 / DM2 / DM3 via the message-drafter subagent
        ▼
Telegram bot (drafts post with Approve/Edit/Reject buttons)
        │
        ▼  candidate taps on phone
Unipile API → LinkedIn
```

Drafts approved outside business hours stay queued until the next 9-5 Mon-Fri window.

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

`ghosted` auto-applies; the rest are manual flags the candidate sets after talking.

## Daily ops — what the cron does

| Step | What | Approval needed |
|---|---|---|
| `campaigns sync` | Refresh DB from markdown files | — |
| `poll` | Fetch inbound replies, halt sequences, **auto-draft a reply** | **Yes (Telegram)** |
| `react` | Like a recent post of each `targeted` recipient → `reacted` | No (low stakes) |
| `connect` | Draft a connect note for each `reacted` recipient | **Yes (Telegram)** |
| `dm1` | Draft first DM for each `connected` recipient | **Yes (Telegram)** |
| `followup` | Draft DM2 (after 4d) / DM3 (after 11d) for `dm_sent` | **Yes (Telegram)** |
| `send-approved` | Flush drafts approved outside the business-hours window | — |
| `auto-ghost` | Mark stale `dm_count=3` recipients as `ghosted` | — |

The candidate only sees Telegram approval cards on their phone. Tap to approve, swipe to reject, tap Edit + reply to rewrite.

## When Claude Code is needed (interactive)

The cron handles everything *mechanical*. Claude Code is for the parts that benefit from judgment:

1. **Setting up a new candidate's campaign** — follow the protocol in the next section. Don't just `campaign create` and leave the brief blank.
2. **Recrafting a reply the auto-drafter got wrong.** Most phone drafts are good enough to Approve or Edit. But for nuanced replies — "you look overqualified", "we have no openings right now but…", scheduling, a tricky question about the candidate's background — the candidate will reject the phone draft and ask Claude Code for a better one. Read the full thread (`messages` table) and the campaign brief, draft, send via `linkedin dm <pid> "..."`.
3. **Tuning the drafter prompt.** If drafts feel off, iterate on `.claude/agents/message-drafter.md`, then rerun `linkedin daily` to see the new style.
4. **One-off recipient work.** "Draft a custom DM2 for recipient 5 — they asked what I've shipped." Use the message-drafter subagent directly.

## Campaign-creation protocol — follow this every time

When the user says "set up my search" / "I want to target X roles" / similar:

### Phase 1 — Clarifying questions (ask all 8)

Push for specificity on each — vague answers produce templated messages:

1. **Who is the candidate?** Role, years, the kind of work they do best, what they want next.
2. **Which roles, specifically?** Title + seniority + company stage/size. ("Engineer" is too broad; "senior/staff backend at post-PMF, 20-300-person product companies" is workable.)
3. **Where?** Country/region/cities, or remote-first.
4. **Who do we message?** Hiring managers? Eng leads? Founders (small cos)? Recruiters? Future teammates for a referral? Usually a mix — name the priority.
5. **Proof points?** 2-3 concrete, true accomplishments (shipped projects, metrics, scale, notable employers) the candidate can lead with.
6. **Anti-claims?** What to never say — no fabricated experience, no sounding desperate, no copying the job post.
7. **Tone?** Peer-to-peer / direct / warm / technical. The candidate is selective, not begging.
8. **Search queries?** 2-3 LinkedIn classic-search keyword strings that surface the right *recipients* (e.g. `"engineering manager" fintech`, `head of engineering Series B`). Classic search is keyword-only.

### Phase 2 — Search validation (mandatory gate)

For each candidate query:

```
linkedin validate-query "<query>" --limit 10 --campaign <slug-once-created>
```

It grades each result on geography + hiring-side role + noise exclusion (other job-seekers). Exits 0 if keepers ≥ 6/10. If a query fails, iterate: add a city, add a stage qualifier, or drop a term that's pulling in other job-seekers. Use only the queries that pass.

### Phase 3 — Generate the brief

Write `campaigns/<slug>.md` from the Phase-1 answers, using `campaigns/_example-candidate.md` as the canon. Set the ICP frontmatter overrides (`icp_role_required` / `icp_role_excluded` / `icp_geo_required`) to match the target recipients and geography. Then `linkedin campaign sync` and show the rendered brief.

### Phase 4 — First import is small

Don't import 50 at once. **Import 5-10 first**, eyeball them in `linkedin pipeline --status targeted`, and scale up only after a couple move through to `connected`. This catches mismatches early.

## CLI reference

All commands are `python -m linkedin_agent <subcommand>` (or `linkedin <subcommand>` if the venv is activated).

### Day-to-day
| Command | Purpose |
|---|---|
| `status` | Dashboard: caps, window, pipeline by stage, replies, due follow-ups |
| `daily` | Run the full cron cycle once |
| `caps` | Usage vs. daily caps |
| `poll` | Fetch inbound replies only |
| `pipeline [--status STATUS]` | List recipients |

### Campaigns
| Command | Purpose |
|---|---|
| `campaign create <slug>` | Scaffold a new candidate campaign file + DB row |
| `campaign sync` | Re-read all `campaigns/*.md` into the DB |
| `campaign list` / `show <slug>` / `archive <slug>` | Manage campaigns |
| `campaign assign <prospect_id> <slug>` | Attach a recipient to a campaign |

### Discovery + manual outreach
| Command | Purpose |
|---|---|
| `search "<query>" --campaign <slug> --limit N` | Search LinkedIn, import N recipients |
| `search-posts "<keywords>" --campaign <slug>` | Import people posting about a topic |
| `validate-query "<query>" --campaign <slug>` | Grade a query before importing |
| `posts <pid>` / `react <pid>` / `connect <pid> --note "..."` / `dm <pid> "..."` | Manual actions |

### Telegram + bot daemon
| Command | Purpose |
|---|---|
| `bot-run` | Start the Telegram daemon (long-running) |
| `telegram-test` / `telegram-push-draft <id>` | Sanity / re-push |

> Note: this toolkit sources recipients via `search` / `search-posts`. There is no
> company-signal importer here — that's intentional. Add role-specific sourcing as a
> future enhancement if needed.

## Safety rules

1. **Never bypass the CLI.** Adapter methods don't enforce rate limits. Always use `python -m linkedin_agent <subcommand>`.
2. **Always check `caps` or `status` before bulk actions.** Hard caps (default 30 reactions / 20 connections / 10 DMs / 50 searches per 24h) will raise.
3. **Don't push drafts to LinkedIn that haven't been approved in Telegram.** The approval flow is the human-in-the-loop quality check.
4. **Stop if anything looks off.** Captcha screens, "unusual activity" warnings, or unexpected 4xx responses → tell the user, don't retry.

## State

- DB: `data/outreach.db` (SQLite). Inspect with `sqlite3 data/outreach.db`.
- Campaign briefs: `campaigns/*.md`. Source of truth — DB rows are derived.
- Telegram + Unipile sessions: configured via `.env`.
- Action log: `actions` table — every API call, drafter result, status transition.

## Deployment

For 24/7 operation use a dedicated always-on Mac. Run `setup.sh` (venv, deps, Playwright, DB init, `.env`), install the bot daemon with `scripts/install_launchd.sh` (LaunchAgent `com.jobhunt.linkedin-bot`), and add the daily cron from `scripts/daily_outreach.sh`. Per-machine state to copy when migrating: `data/outreach.db`, `.env`, and `campaigns/*.md` (already in git).
