from __future__ import annotations

import hashlib
import html
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Protocol

import httpx

from .models import DestinationRecommendation, JobPosting, JobSearchQuery


class JobProviderError(RuntimeError):
    pass


class JobProvider(Protocol):
    async def search(self, query: JobSearchQuery) -> list[JobPosting]: ...


def _plain_text(value: str, limit: int = 500) -> str:
    decoded = html.unescape(value or "")
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    normalized = re.sub(r"\s+", " ", without_tags).strip()
    return normalized[:limit]


class ArbeitnowJobProvider:
    """Read-only adapter for Arbeitnow's documented, unauthenticated Jobs API."""

    def __init__(self, api_url: str, timeout_seconds: float = 20) -> None:
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds

    async def search(self, query: JobSearchQuery) -> list[JobPosting]:
        tokens = {
            token.casefold()
            for token in re.findall(r"[\w+#.-]+", query.direction)
            if len(token) > 1
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={"User-Agent": "resume-campaign-agent/0.1 (dry-run)"},
            ) as client:
                response = await client.get(self.api_url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise JobProviderError(f"job provider unavailable: {type(exc).__name__}") from exc

        raw_jobs = payload.get("data", []) if isinstance(payload, dict) else []
        scored: list[tuple[int, JobPosting]] = []
        for raw in raw_jobs:
            title = str(raw.get("title") or "").strip()
            company = str(raw.get("company_name") or "").strip()
            url = str(raw.get("url") or "").strip()
            if not (title and company and url):
                continue
            location = str(raw.get("location") or "Remote").strip() or "Remote"
            tags = [str(tag).strip() for tag in raw.get("tags") or [] if str(tag).strip()]
            description = _plain_text(str(raw.get("description") or ""))
            haystack = " ".join([title, company, location, " ".join(tags), description]).casefold()
            score = sum(4 if token in title.casefold() else 1 for token in tokens if token in haystack)
            if tokens and score == 0:
                continue
            remote = bool(raw.get("remote"))
            if query.remote_preference == "required" and not remote:
                continue
            if query.remote_preference == "onsite" and remote:
                continue
            if remote and query.remote_preference == "preferred":
                score += 2
            for preferred in query.preferred_locations:
                if preferred.casefold() in location.casefold():
                    score += 3
            posted_at = None
            raw_date = raw.get("created_at")
            if raw_date:
                try:
                    posted_at = datetime.fromtimestamp(int(raw_date))
                except (TypeError, ValueError, OSError):
                    posted_at = None
            job_id = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
            try:
                job = JobPosting(
                    id=job_id,
                    title=title,
                    company=company,
                    location="Remote" if remote and not location else location,
                    remote=remote,
                    url=url,
                    tags=tags[:15],
                    description_excerpt=description,
                    posted_at=posted_at,
                    source="arbeitnow",
                )
            except ValueError:
                continue
            scored.append((score, job))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [job for _, job in scored[: query.limit]]


def recommend_destinations(
    jobs: list[JobPosting], preferred_locations: list[str]
) -> list[DestinationRecommendation]:
    groups: dict[str, list[JobPosting]] = defaultdict(list)
    for job in jobs:
        destination = "Remote" if job.remote else (job.location or "Unspecified")
        groups[destination].append(job)
    if not groups:
        return []
    max_count = max(len(items) for items in groups.values())
    recommendations: list[DestinationRecommendation] = []
    for destination, items in groups.items():
        count_score = 70 * len(items) / max_count
        preference_bonus = 0.0
        if destination == "Remote":
            preference_bonus += 10
        if any(value.casefold() in destination.casefold() for value in preferred_locations):
            preference_bonus += 20
        companies = list(Counter(job.company for job in items).keys())[:4]
        recommendations.append(
            DestinationRecommendation(
                destination=destination,
                score=round(min(100, count_score + preference_bonus), 1),
                matched_jobs=len(items),
                rationale=f"在本轮真实检索结果中匹配 {len(items)} 个职位"
                + ("，且符合地点偏好" if preference_bonus >= 20 else ""),
                sample_companies=companies,
            )
        )
    return sorted(recommendations, key=lambda item: (-item.score, item.destination))[:8]
