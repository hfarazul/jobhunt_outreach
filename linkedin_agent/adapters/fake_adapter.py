from __future__ import annotations

# Offline adapter for tests and dry-run smoke checks. Never touches the network.
# Wire by setting LINKEDIN_BACKEND=fake in .env.

import os
import re

from ..config import Config
from .base import JobDetail, JobHit, LinkedInAdapter, Post, PostHit, ProspectHit


# Some company-scoped lookups fire very specific sub-queries:
# '"<company>" CTO', '"<company>" engineer', '"<company>" "founding"'.
# We match that shape exactly so we don't suppress legitimate user searches
# like 'ai engineer' or 'startup CTO'.
_TEAM_CHECK_QUERY_RE = re.compile(
    r'^"[^"]+"\s+(cto|engineer|"founding")\s*$', re.IGNORECASE,
)


class FakeAdapter(LinkedInAdapter):
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name: str, *args, **kwargs) -> None:
        self.calls.append((name, args, kwargs))

    def search(self, query: str, limit: int = 20) -> list[ProspectHit]:
        self._record("search", query, limit=limit)
        # Test hooks — let integration tests drive scenarios that the default
        # query-echo headline can't naturally produce (e.g. a no-match path
        # needs headlines that lack the keyword a lookup is searching for).
        if os.environ.get("LINKEDIN_FAKE_EMPTY_SEARCH") == "1":
            return []
        # Some lookups fire secondary sub-queries like '"X" CTO', '"X" engineer'.
        # FakeAdapter's default query-echo headlines contain those words too,
        # which would skew such scenarios. This hook returns empty for queries
        # matching that shape; default-enabled in tests so happy-path imports
        # work, opt-out by unsetting it when a test exercises that flow itself.
        if os.environ.get("LINKEDIN_FAKE_EMPTY_TEAM_CHECK") == "1":
            if _TEAM_CHECK_QUERY_RE.match(query):
                return []
        headline_override = os.environ.get("LINKEDIN_FAKE_HEADLINE")
        return [
            ProspectHit(
                linkedin_url=f"https://www.linkedin.com/in/fake-{i}-{query.replace(' ', '-').lower()}",
                full_name=f"Fake Person {i}",
                headline=headline_override or f"Headline {i} matching {query}",
                company=f"Company {i}",
                title="Founder",
                location="Remote",
            )
            for i in range(1, limit + 1)
        ]

    def search_posts(self, keywords: str, *, limit: int = 20,
                     date_posted: str = "past_month",
                     author_keywords: str | None = None) -> list[PostHit]:
        self._record("search_posts", keywords, limit=limit,
                     date_posted=date_posted, author_keywords=author_keywords)
        out: list[PostHit] = []
        for i in range(1, limit + 1):
            slug = f"fake-post-author-{i}-{keywords.replace(' ', '-')[:30]}".lower()
            author = ProspectHit(
                linkedin_url=f"https://www.linkedin.com/in/{slug}",
                full_name=f"Fake Author {i}",
                headline=f"Founder building {keywords[:40]}",
                location="San Francisco, CA",
                provider_id=f"ACo{slug.replace('-', '_')}",
            )
            out.append(PostHit(
                author=author,
                post_text=f"Hey LinkedIn — sharing some thoughts on {keywords}. {i}",
                post_url=f"https://www.linkedin.com/feed/update/urn:li:activity:fake-{i}",
                posted_at="2026-05-17T12:00:00Z",
            ))
        return out

    def resolve_location(self, keywords: str, *, limit: int = 5) -> list[tuple[str, str]]:
        self._record("resolve_location", keywords, limit=limit)
        # Deterministic fake id derived from the keyword so tests can assert.
        return [(str(90000000 + len(keywords)), f"{keywords} Area (fake)")]

    def search_jobs(self, keywords: str, *, region: str | None = None,
                    date_posted: int | None = None, sort_by: str = "relevance",
                    limit: int = 20) -> list[JobHit]:
        self._record("search_jobs", keywords, region=region,
                     date_posted=date_posted, sort_by=sort_by, limit=limit)
        if os.environ.get("LINKEDIN_FAKE_EMPTY_SEARCH") == "1":
            return []
        out: list[JobHit] = []
        for i in range(1, limit + 1):
            out.append(JobHit(
                job_id=f"{1000 + i}",
                title=f"{keywords.title()} {i}",
                company_name=f"Fake Co {i}",
                company_identifier=f"fake-co-{i}",
                location="London Area, United Kingdom",
                url=f"https://www.linkedin.com/jobs/view/{1000 + i}",
                posted_at="2026-06-11T09:00:00.000Z",
            ))
        return out

    def get_job(self, job_id: str) -> JobDetail:
        self._record("get_job", job_id)
        # Fake hiring team: one talent lead + one engineering manager.
        team = [
            ProspectHit(
                linkedin_url=f"https://www.linkedin.com/in/fake-talent-lead-{job_id}",
                full_name=f"Talent Lead {job_id}", company=f"Fake Co {job_id}",
                headline="Talent Lead", provider_id=f"ACoFakeTalent{job_id}",
            ),
            ProspectHit(
                linkedin_url=f"https://www.linkedin.com/in/fake-eng-manager-{job_id}",
                full_name=f"Eng Manager {job_id}", company=f"Fake Co {job_id}",
                headline="Engineering Manager", provider_id=f"ACoFakeMgr{job_id}",
            ),
        ]
        return JobDetail(
            job_id=str(job_id),
            title=f"AI Engineer (job {job_id})",
            company_name=f"Fake Co {job_id}",
            company_identifier=f"fake-co-{job_id}",
            location="London Area, United Kingdom",
            description="We're hiring an AI engineer to build production agent systems.",
            apply_url="https://example.com/apply",
            applicants=0,
            posted_at="2026-06-11T09:00:00.000Z",
            hiring_team=team,
        )

    def get_recent_posts(self, linkedin_url: str, limit: int = 5) -> list[Post]:
        self._record("get_recent_posts", linkedin_url, limit=limit)
        slug = linkedin_url.rstrip("/").rsplit("/", 1)[-1]
        return [
            Post(
                post_id=f"urn:li:activity:{slug}-{i}",
                url=f"https://www.linkedin.com/feed/update/urn:li:activity:{slug}-{i}/",
                author_url=linkedin_url,
                text=f"Sample post {i} from {slug}",
                posted_at="2026-05-14T12:00:00Z",
            )
            for i in range(1, limit + 1)
        ]

    def react(self, post: Post, reaction: str = "LIKE") -> str:
        self._record("react", post.post_urn, reaction=reaction)
        return post.post_urn

    def send_connection(self, linkedin_url: str, note: str | None = None) -> str:
        self._record("send_connection", linkedin_url, note=note)
        return "fake-invitation-id"

    def send_dm(self, linkedin_url: str, body: str) -> str:
        self._record("send_dm", linkedin_url, body=body)
        return "fake-message-id"
