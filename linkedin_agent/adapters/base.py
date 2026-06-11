from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ProspectHit:
    linkedin_url: str
    full_name: str | None = None
    headline: str | None = None
    company: str | None = None
    title: str | None = None
    location: str | None = None
    # LinkedIn-internal provider id (e.g. 'ACoAAA...'). Populated by adapters
    # that know it from search; used internally to skip a profile-resolve hop.
    provider_id: str | None = None


@dataclass
class Post:
    # post_id is the numeric activity id (string-form). For reaction/comment
    # calls Unipile expects this id directly.
    post_id: str
    url: str
    author_url: str
    text: str
    posted_at: str | None = None
    # Legacy alias used by older callers — same value as post_id.

    @property
    def post_urn(self) -> str:
        return self.post_id


@dataclass
class PostHit:
    """Result from a post-content search (vs profile search). Pairs the author
    profile with the post that matched the query. Use the post text as
    pitch_context when importing — the drafter can reference what the
    prospect actually wrote."""
    author: ProspectHit
    post_text: str
    post_url: str | None = None
    posted_at: str | None = None


@dataclass
class JobHit:
    """A single job posting from a jobs search."""
    job_id: str
    title: str
    company_name: str | None = None
    # LinkedIn company public_identifier (e.g. 'oxford-dynamics-limited') — used
    # to find that company's hiring managers via people search.
    company_identifier: str | None = None
    location: str | None = None
    url: str | None = None
    posted_at: str | None = None


@dataclass
class JobDetail:
    """Full detail for one job, including its LinkedIn-attached hiring team —
    the people to actually reach out to for this role."""
    job_id: str
    title: str
    company_name: str | None = None
    company_identifier: str | None = None
    location: str | None = None
    description: str = ""
    apply_url: str | None = None
    applicants: int | None = None
    posted_at: str | None = None
    # The "Meet the hiring team" people LinkedIn attaches to the posting —
    # usually a recruiter / talent lead and sometimes the hiring manager.
    hiring_team: list[ProspectHit] = field(default_factory=list)


class LinkedInAdapter(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 20) -> list[ProspectHit]:
        """Free-text people search. Returns ProspectHits, newest match first."""

    def resolve_location(self, keywords: str, *, limit: int = 5) -> list[tuple[str, str]]:
        """Resolve a location name (e.g. 'London') to candidate (id, title)
        pairs usable as the `region` filter in search_jobs. The id is a numeric
        LinkedIn geo id; pick the title that matches the intended place.

        Default impl raises NotImplementedError — only adapters that support
        the jobs API (UnipileAdapter) override."""
        raise NotImplementedError("location resolution not supported by this adapter")

    def search_jobs(
        self, keywords: str, *, region: str | None = None,
        date_posted: int | None = None, sort_by: str = "relevance",
        limit: int = 20,
    ) -> list["JobHit"]:
        """Search LinkedIn job postings.

        `region`: a numeric LOCATION id (from resolve_location) — LinkedIn's
        primary location filter. Free-text city names in `keywords` do NOT
        geo-filter; you must pass a region id.
        `date_posted`: timespan in days since today (e.g. 7, 30).
        `sort_by`: "relevance" (default) or "date".

        Default impl raises NotImplementedError — override per adapter."""
        raise NotImplementedError("jobs search not supported by this adapter")

    def get_job(self, job_id: str) -> "JobDetail":
        """Fetch full detail for one job, including its hiring_team. Default
        impl raises NotImplementedError — override per adapter."""
        raise NotImplementedError("job detail not supported by this adapter")

    def search_posts(
        self, keywords: str, *, limit: int = 20,
        date_posted: str = "past_month",
        author_keywords: str | None = None,
    ) -> list[PostHit]:
        """Keyword search across LinkedIn POST content (not profile headlines).
        Returns posts with their authors so we can import the right person and
        stash the post text as pitch_context.

        `date_posted`: one of "past_24h", "past_week", "past_month".
        `author_keywords`: optional headline filter to bias toward role
        (e.g. "founder" excludes service providers).

        Default impl raises NotImplementedError — adapters that support it
        (e.g. UnipileAdapter) override. Playwright backend can stay on
        profile-search until/unless we wire post-search on that side too."""
        raise NotImplementedError("post-search not supported by this adapter")

    @abstractmethod
    def get_recent_posts(self, linkedin_url: str, limit: int = 5) -> list[Post]:
        """Recent activity for a profile."""

    @abstractmethod
    def react(self, post: Post, reaction: str = "LIKE") -> str:
        """React to a post. Returns a result identifier (URN, etc.)."""

    @abstractmethod
    def send_connection(self, linkedin_url: str, note: str | None = None) -> str:
        """Send a connection request, optionally with a personalized note (≤300 chars)."""

    @abstractmethod
    def send_dm(self, linkedin_url: str, body: str) -> str:
        """Send a direct message. Assumes already connected (or InMail credit available)."""

    def close(self) -> None:
        """Optional cleanup."""
