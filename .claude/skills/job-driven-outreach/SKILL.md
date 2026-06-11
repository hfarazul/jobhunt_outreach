---
name: job-driven-outreach
description: Source warm job-search outreach from live LinkedIn job postings. Use when the user wants to "find jobs and reach out", "apply via the hiring manager not the form", target a specific role/company from its posting, or run the jobs → hiring-team → DM pipeline. Searches LinkedIn jobs, picks the most relevant role, pulls that posting's hiring team + the company's managers, and drafts candidate outreach that references the specific role. All sends are approval-gated and respect daily caps.
---

# Job-driven outreach

Turn a live LinkedIn **job posting** into warm outreach: instead of dropping a CV into an ATS, reach the people who own the role — the posting's recruiter/talent lead and an engineering manager or founder — with a message that references that exact role and the candidate's real, relevant work.

```
jobs search → pick the most relevant role → job-import (hiring team + managers)
            → review → connect note referencing the role → (after accept) DM1
```

This is sourcing, not auto-blasting. You apply judgment at two points: **which role** and **which message**. Every LinkedIn-visible send is gated by Telegram approval (or an explicit in-chat go) and the daily caps.

## Prerequisites

- A candidate campaign exists for whoever is searching (`linkedin campaign list`). If not, create one first (see the campaign-creation protocol in `CLAUDE.md`) — the brief is what the drafter uses to position the candidate. Copy `campaigns/_example-candidate.md`.
- `LINKEDIN_BACKEND=unipile` with working credentials in `.env`.

## Steps

### 1. Search jobs (read-only)

```
linkedin jobs "<role keywords>" --location "<city/region>" --date-posted <N> --limit 15
```

- **`--location` is required for geography.** Free-text city names in the keywords do NOT geo-filter — LinkedIn needs a resolved geo id, which `--location` handles for you.
- `--date-posted 7` (or `1`) surfaces fresh postings; fresh + low-applicant roles are where outreach lands best.
- This prints a table of `job_id · title · company · location · posted`. Nothing is imported.

### 2. Pick the most relevant role (judgment)

Prefer:
- An **actual employer**, not a staffing/recruitment agency (names like "… Recruitment", "… Talent", "… Solutions" are usually agencies reposting — skip them; you want the company that will employ the candidate).
- A real fit for the candidate's brief (seniority, domain, stack).
- Freshly posted, ideally few applicants (check the detail in the next step).
- Small/mid companies where the hiring manager or founder is reachable.

### 3. Import the job's hiring contacts

```
linkedin job-import <job_id> --campaign <slug>          # add --dry-run to preview first
```

This:
- fetches the posting's own **hiring team** (recruiter / talent lead),
- (unless `--no-managers`) people-searches the **company** for an engineering lead / founder,
- imports them as `targeted` prospects with the **role stashed as `pitch_context`** — so the drafter references this specific job.

Use `--dry-run` first to see who would be imported.

### 4. Review

```
linkedin pipeline --status targeted
```

Confirm the contacts are the right people (a talent lead + a manager/founder is the ideal pair). Drop anyone off-target with judgment before reaching out.

### 5. Reach out (approval-gated)

The downstream flow is unchanged — the connect note will reference the role from `pitch_context`:

- **Automated:** `linkedin daily` reacts to recent posts, drafts connect notes via the candidate drafter, and pushes them to Telegram for Approve/Edit/Reject.
- **Manual / controlled:** draft and review a connect note for one prospect, then `linkedin connect <pid> --note "<body>"`.

**On "DMs":** you cannot DM a LinkedIn non-connection without InMail. The correct first touch is a **connection request with a note** (≤300 chars, referencing the role). The actual DM (DM1) fires automatically once they accept.

### 6. After they accept

`linkedin daily` (or the followup flow) drafts DM1 → Telegram approval → send. Keep referencing the specific role and the candidate's relevant proof points.

## Guardrails

- **Verify factual hooks before sending.** If a draft cites a specific company/tech detail, confirm it's real (read the job description / the person's posts) — never send a hallucinated claim to a real person.
- **Truthful positioning only.** The candidate's proof points come from their campaign brief; never invent experience.
- **Don't sound like a cold applicant.** Peer-to-peer, specific, selective — the candidate drafter enforces this, but review the output.
- **Caps + approval.** Check `linkedin status` before bulk action. Never push an unapproved message to LinkedIn.

## Under the hood

- Adapter: `search_jobs()`, `get_job()` (returns `hiring_team`), `resolve_location()` in `linkedin_agent/adapters/base.py` / `unipile_adapter.py` (Unipile `POST /linkedin/search` with `category: "jobs"`, `GET /linkedin/jobs/{id}`, `GET /linkedin/search/parameters`).
- CLI: `jobs` (search) and `job-import` (source contacts) in `linkedin_agent/cli.py`.
- Tests: `tests/test_jobs.py` (offline, fake backend).
