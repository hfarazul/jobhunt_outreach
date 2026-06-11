from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAMPAIGNS_DIR = ROOT / "campaigns"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_KV_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.+)$")


@dataclass
class CampaignBrief:
    slug: str
    name: str
    target_icp: str | None
    status: str
    brief: str   # markdown body without frontmatter
    path: Path


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Minimal YAML frontmatter parser — only handles flat string key/value pairs.
    Avoids pulling in pyyaml for the simple case."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw_meta, body = m.group(1), m.group(2)
    meta: dict[str, str] = {}
    for line in raw_meta.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kv = _KV_RE.match(line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip('"').strip("'")
    return meta, body


def brief_path_for(slug: str) -> Path:
    return CAMPAIGNS_DIR / f"{slug}.md"


def load_brief(slug: str) -> CampaignBrief:
    path = brief_path_for(slug)
    if not path.exists():
        raise FileNotFoundError(f"no campaign brief at {path}")
    raw = path.read_text()
    meta, body = _parse_frontmatter(raw)
    return CampaignBrief(
        slug=meta.get("slug", slug),
        name=meta.get("name", slug),
        target_icp=meta.get("target_icp") or None,
        status=meta.get("status", "active"),
        brief=body.strip(),
        path=path,
    )


def list_brief_files() -> list[Path]:
    if not CAMPAIGNS_DIR.exists():
        return []
    return sorted(p for p in CAMPAIGNS_DIR.glob("*.md") if p.is_file())


CAMPAIGN_TEMPLATE = """\
---
slug: {slug}
name: {name}
status: active
target_icp: <who you're reaching out to — e.g. "Engineering managers and heads of eng at 20-200 person product companies hiring senior backend engineers, US/remote">
# ICP overrides for validate-query — narrow to who can hire/refer you:
icp_role_required: "engineering manager|head of eng|vp eng|director.*eng|tech lead|cto|founder|recruiter|talent"
icp_role_excluded: "open to work|seeking|aspiring|student"
icp_geo_required: "United States|, CA\\\\b|, NY\\\\b|United Kingdom|Remote"
---

# About me

<2-4 lines on who you are as a candidate: your role, years of experience, the kind of work you do best, and what you're looking for next. This is what the drafter uses to position you.>

# What I'm looking for

<The target role(s), seniority, company stage/size, and any must-haves (remote, domain, stack). Be specific — vague targets produce templated messages.>

# Proof points (use whichever fits the recipient)

- <a shipped project + its impact / metric>
- <a notable employer, scale, or domain>
- <a skill or result that maps to the role you want>

# Anti-claims — DO NOT say

- Never sound desperate or lead with "I'm looking for a job"
- Never copy text from the job posting — that reads as surveilled
- Never invent experience, employers, or metrics
- <add your own>

# Tone

<peer-to-peer | direct | warm | technical — how you want to come across. You're reaching out as a strong candidate who's selective, not an applicant begging for a callback.>
"""


def scaffold_brief(slug: str, name: str | None = None) -> Path:
    path = brief_path_for(slug)
    if path.exists():
        raise FileExistsError(f"campaign brief already exists at {path}")
    CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(CAMPAIGN_TEMPLATE.format(slug=slug, name=name or slug))
    return path
