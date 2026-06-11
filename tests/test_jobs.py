"""Tests for the job-driven sourcing pipeline: adapter jobs methods + the
`jobs` / `job-import` CLI commands, all against the offline fake backend."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str], env: dict[str, str], *, expect_fail: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(
        [sys.executable, "-m", "linkedin_agent", *args],
        cwd=ROOT, env={**os.environ, **env}, capture_output=True, text=True,
    )
    assert (r.returncode != 0) == expect_fail, (
        f"{args} rc={r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    )
    return r


def _db_query(db_path: str, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


# ===== adapter-level (fake) =================================================

@pytest.mark.unit
def test_fake_search_jobs_shape(db_env):
    from linkedin_agent.adapters import get_adapter
    from linkedin_agent.config import load as load_cfg
    ad = get_adapter(load_cfg())
    jobs = ad.search_jobs("AI engineer", region="123", date_posted=30, limit=4)
    assert len(jobs) == 4
    j = jobs[0]
    assert j.job_id and j.title and j.company_identifier
    assert j.url.startswith("https://www.linkedin.com/jobs/view/")


@pytest.mark.unit
def test_fake_get_job_has_hiring_team(db_env):
    from linkedin_agent.adapters import get_adapter
    from linkedin_agent.config import load as load_cfg
    ad = get_adapter(load_cfg())
    job = ad.get_job("1001")
    assert job.job_id == "1001"
    assert job.company_name
    # the hiring team should include people we can message
    assert len(job.hiring_team) >= 1
    assert all(p.linkedin_url for p in job.hiring_team)


@pytest.mark.unit
def test_fake_resolve_location(db_env):
    from linkedin_agent.adapters import get_adapter
    from linkedin_agent.config import load as load_cfg
    ad = get_adapter(load_cfg())
    cands = ad.resolve_location("London")
    assert cands and cands[0][0].isdigit()


# ===== CLI: jobs (read-only) ================================================

@pytest.mark.integration
def test_jobs_command_lists(env):
    r = _run(["jobs", "AI engineer", "--location", "London", "--limit", "3"], env)
    assert "job_id" in r.stdout
    assert "1001" in r.stdout  # fake job ids start at 1001


# ===== CLI: job-import ======================================================

@pytest.mark.integration
def test_job_import_imports_hiring_team_with_context(env):
    # job-import needs a campaign row; create one (and clean up the brief file).
    from linkedin_agent import campaigns as campaigns_mod
    slug = "jobtest-campaign"
    brief = campaigns_mod.brief_path_for(slug)
    try:
        _run(["campaign", "create", slug], env)
        r = _run(["job-import", "1001", "--campaign", slug], env)
        assert "imported" in r.stdout.lower()

        rows = _db_query(
            env["LINKEDIN_DB_PATH"],
            """SELECT p.full_name, p.pitch_context
               FROM prospects p JOIN campaigns c ON p.campaign_id = c.id
               WHERE c.slug = ?""",
            (slug,),
        )
        # at least the posting's hiring team (talent lead + eng manager)
        assert len(rows) >= 2
        for row in rows:
            assert row["pitch_context"], "every imported contact carries the role as context"
            assert "hiring" in row["pitch_context"].lower()
    finally:
        if brief.exists():
            brief.unlink()


@pytest.mark.integration
def test_job_import_dry_run_writes_nothing(env):
    from linkedin_agent import campaigns as campaigns_mod
    slug = "jobtest-dry"
    brief = campaigns_mod.brief_path_for(slug)
    try:
        _run(["campaign", "create", slug], env)
        r = _run(["job-import", "1001", "--campaign", slug, "--dry-run"], env)
        assert "dry-run" in r.stdout.lower()
        rows = _db_query(
            env["LINKEDIN_DB_PATH"],
            "SELECT COUNT(*) AS n FROM prospects WHERE pitch_context LIKE '%hiring%'",
        )
        assert rows[0]["n"] == 0
    finally:
        if brief.exists():
            brief.unlink()
