from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .china_catalog import (
    CHINA_ENTERPRISE_CATALOG,
    KNOWN_OFFICIAL_DOMAINS,
    CatalogEnterprise,
    application_channels_for,
)
from .config import Settings
from .models import (
    EnterpriseDiscoveryRequest,
    EnterpriseDiscoveryResponse,
    EnterpriseLead,
    ApplicationChannel,
    ResumeProfile,
    SessionState,
)


COMMON_BASES = (
    "北京", "上海", "深圳", "广州", "杭州", "成都", "武汉", "西安", "南京", "苏州",
    "合肥", "青岛", "长沙", "宁波", "厦门", "天津", "重庆", "佛山", "东莞", "珠海",
    "无锡", "郑州", "济南", "福州", "宁德", "长春", "株洲", "南通", "大连",
)


@dataclass(frozen=True)
class WebSearchHit:
    title: str
    url: str
    highlights: str
    query: str


class AIRankedItem(BaseModel):
    index: int = Field(ge=0)
    score: float = Field(ge=0, le=100)
    rationale: str = Field(min_length=2, max_length=300)
    recommended_roles: list[str] = Field(default_factory=list, max_length=6)


class AIRankingOutput(BaseModel):
    items: list[AIRankedItem] = Field(default_factory=list, max_length=40)


class AgentReachExaProvider:
    """Invoke the locally configured Agent Reach Exa backend without shell interpolation."""

    def __init__(self, timeout_seconds: float = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def _runtime(self) -> tuple[str, str] | None:
        node = shutil.which("node.exe") or shutil.which("node")
        mcporter = shutil.which("mcporter.cmd") or shutil.which("mcporter")
        if not (node and mcporter):
            return None
        cli = Path(mcporter).parent / "node_modules" / "mcporter" / "dist" / "cli.js"
        if not cli.exists():
            return None
        return node, str(cli)

    async def search(self, query: str, num_results: int = 8) -> list[WebSearchHit]:
        runtime = self._runtime()
        if runtime is None:
            raise RuntimeError("Agent Reach Exa runtime is unavailable")
        node, cli = runtime
        args_json = json.dumps(
            {"query": query, "numResults": min(max(num_results, 1), 10)},
            ensure_ascii=False,
        )
        process = await asyncio.create_subprocess_exec(
            node,
            cli,
            "call",
            "exa.web_search_exa",
            "--args",
            args_json,
            "--output",
            "json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise RuntimeError("Exa search timed out") from exc
        if process.returncode != 0:
            category = "configuration" if b"config" in stderr.lower() else "provider"
            raise RuntimeError(f"Exa search failed: {category}")
        try:
            payload = json.loads(stdout.decode("utf-8"))
            text = "\n".join(
                block.get("text", "")
                for block in payload.get("content", [])
                if block.get("type") == "text"
            )
        except (UnicodeDecodeError, ValueError, AttributeError) as exc:
            raise RuntimeError("Exa returned an unreadable response") from exc
        return self._parse(text, query)

    @staticmethod
    def _parse(text: str, query: str) -> list[WebSearchHit]:
        pattern = re.compile(
            r"Title:\s*(.*?)\nURL:\s*(https?://\S+).*?Highlights:\s*(.*?)(?=\n\n---|\Z)",
            re.DOTALL,
        )
        hits: list[WebSearchHit] = []
        for title, url, highlights in pattern.findall(text):
            clean_title = re.sub(r"\s+", " ", title).strip() or "招聘来源"
            clean_highlights = re.sub(r"\s+", " ", highlights).strip()[:1200]
            hits.append(
                WebSearchHit(
                    title=clean_title,
                    url=url.rstrip(".,)]"),
                    highlights=clean_highlights,
                    query=query,
                )
            )
        return hits


def build_query_plan(
    request: EnterpriseDiscoveryRequest, session: SessionState
) -> tuple[list[str], list[str], list[str], list[str]]:
    resume = session.resume
    bases = _unique(
        request.base_locations
        or resume.base_locations
        or session.preferred_locations
        or ([resume.city] if resume.city else [])
    )
    directions = _unique(
        request.professional_directions
        or resume.target_roles
        or ([resume.education[0].major] if resume.education else [])
    )
    industries = _unique(request.industries or resume.target_industries)
    employers = _unique(request.employer_types or resume.target_employer_types)
    focus = " ".join([*directions[:2], *industries[:2], *employers[:1]]).strip() or "不限专业"
    queries = [
        f"{base} {focus} 官方 招聘 校园招聘 社会招聘 2026"
        for base in bases[:3]
    ]
    if request.company_keywords:
        queries.append(
            f"{' '.join(request.company_keywords[:4])} {' '.join(bases[:2])} 官方 招聘 2026"
        )
    elif len(queries) < 2:
        base_scope = " ".join(bases[:2]) or "中国"
        queries.append(f"{base_scope} 中国企业 {focus} 官方 招聘网站 2026")
    return _unique(queries)[:4], bases, directions, industries


class EnterpriseDiscoveryService:
    def __init__(self, settings: Settings, web_provider: AgentReachExaProvider | None = None) -> None:
        self.settings = settings
        self.web_provider = web_provider or AgentReachExaProvider(
            timeout_seconds=max(20, settings.request_timeout_seconds)
        )

    async def discover(
        self, request: EnterpriseDiscoveryRequest, session: SessionState
    ) -> EnterpriseDiscoveryResponse:
        queries, bases, directions, industries = build_query_plan(request, session)
        warnings: list[str] = []
        hit_batches: list[list[WebSearchHit]] = []
        if queries:
            settled = await asyncio.gather(
                *(self.web_provider.search(query, 8) for query in queries),
                return_exceptions=True,
            )
            for result in settled:
                if isinstance(result, Exception):
                    warnings.append(str(result))
                else:
                    hit_batches.append(result)
        hits = [hit for batch in hit_batches for hit in batch]
        candidates = self._catalog_candidates(request, bases, directions, industries)
        candidates.extend(self._web_candidates(hits, bases, directions, industries))
        candidates = _deduplicate_leads(candidates)
        candidates.sort(key=lambda item: item.score, reverse=True)
        ai_used = False
        if request.ai_ranking and self.settings.llm_configured and candidates:
            try:
                candidates = await asyncio.wait_for(
                    self._rank_with_ai(
                        candidates[:40], session.resume, bases, directions, industries
                    ),
                    timeout=max(5, min(90, self.settings.ai_ranking_timeout_seconds)),
                )
                ai_used = True
            except Exception as exc:
                warnings.append(f"AI ranking unavailable: {type(exc).__name__}")
        # A high semantic match from a repost must never outrank a usable official
        # application channel. AI ranks within the same readiness tier.
        readiness_priority = {
            "direct_official": 2,
            "official_hub": 2,
            "needs_channel_verification": 0,
        }
        candidates.sort(
            key=lambda lead: (readiness_priority[lead.application_readiness], lead.score),
            reverse=True,
        )
        candidates = candidates[: request.limit]
        official_count = sum(
            lead.source_authority == "official_known" for lead in candidates
        )
        official_entry_count = sum(bool(lead.application_channels) for lead in candidates)
        live_or_hub_entry_count = sum(
            any(channel.availability in {"openings_live", "entry_hub", "check_required"} for channel in lead.application_channels)
            for lead in candidates
        )
        engine = "Agent Reach Exa AI + 中国企业官方入口目录"
        if ai_used:
            engine += " + Pydantic AI 排序"
        return EnterpriseDiscoveryResponse(
            session_id=session.id,
            search_engine=engine,
            ai_ranking_used=ai_used,
            query_plan=queries,
            source_count=len(hits) + len(CHINA_ENTERPRISE_CATALOG),
            official_source_count=official_count,
            official_entry_count=official_entry_count,
            live_or_hub_entry_count=live_or_hub_entry_count,
            enterprises=candidates,
            warnings=_unique(warnings),
            notice="结果按 Base、专业/岗位、行业与来源可信度排序；用户逐企业确认后，可由浏览器副驾驶接管官网登录、填表与投递。",
        )

    def _catalog_candidates(
        self,
        request: EnterpriseDiscoveryRequest,
        bases: list[str],
        directions: list[str],
        industries: list[str],
    ) -> list[EnterpriseLead]:
        leads: list[EnterpriseLead] = []
        for entry in CHINA_ENTERPRISE_CATALOG:
            if request.company_keywords and not any(
                keyword.casefold() in entry.name.casefold()
                for keyword in request.company_keywords
            ):
                continue
            base_matches = [base for base in bases if base in entry.bases or "全国" in entry.bases]
            industry_matches = [
                industry
                for industry in industries
                if any(industry.casefold() in value.casefold() or value.casefold() in industry.casefold() for value in entry.industries)
            ]
            employer_match = not request.employer_types or any(
                value.casefold() in entry.employer_type.casefold()
                for value in request.employer_types
            )
            score = 35.0
            if base_matches:
                score += 30
            elif bases:
                score -= 12
            if industry_matches:
                score += 18
            if employer_match:
                score += 7
            leads.append(self._catalog_lead(entry, score, base_matches, directions, industry_matches))
        return leads

    @staticmethod
    def _catalog_lead(
        entry: CatalogEnterprise,
        score: float,
        base_matches: list[str],
        directions: list[str],
        industry_matches: list[str],
    ) -> EnterpriseLead:
        rationale_bits = []
        if base_matches:
            rationale_bits.append(f"覆盖意向 Base：{'、'.join(base_matches)}")
        if industry_matches:
            rationale_bits.append(f"命中行业：{'、'.join(industry_matches)}")
        if not rationale_bits:
            rationale_bits.append("中国企业官方招聘入口，可进一步按专业检索")
        return EnterpriseLead(
            id=_lead_id(entry.career_url),
            company=entry.name,
            source_title=f"{entry.name}官方招聘入口",
            source_url=entry.career_url,
            bases=list(entry.bases),
            industries=list(entry.industries),
            recommended_roles=directions[:4],
            source_kind="official_catalog",
            source_authority="official_known",
            score=max(0, min(100, score)),
            rationale="；".join(rationale_bits),
            application_channels=_application_channels(entry),
            application_readiness=_application_readiness(entry),
            channel_notice="只接管企业官方或官方公告指定的系统；验证码与逐岗位最终投递仍需用户确认。",
        )

    def _web_candidates(
        self,
        hits: list[WebSearchHit],
        bases: list[str],
        directions: list[str],
        industries: list[str],
    ) -> list[EnterpriseLead]:
        leads: list[EnterpriseLead] = []
        for hit in hits:
            company = _infer_company(hit.title, hit.highlights)
            domain = (urlparse(hit.url).hostname or "").casefold()
            authority = (
                "official_known"
                if domain in KNOWN_OFFICIAL_DOMAINS or any(domain.endswith(f".{known}") for known in KNOWN_OFFICIAL_DOMAINS)
                else "likely_official"
                if any(marker in hit.title for marker in ("官网", "官方", "股份有限公司", "集团", "交易所", "银行"))
                else "unverified"
            )
            catalog_entry = _catalog_entry_for_domain(domain)
            haystack = f"{hit.title} {hit.highlights}".casefold()
            base_matches = [base for base in bases if base.casefold() in haystack]
            industry_matches = [industry for industry in industries if industry.casefold() in haystack]
            direction_matches = [direction for direction in directions if _token_overlap(direction, haystack)]
            score = 26 + min(24, len(base_matches) * 12) + min(20, len(direction_matches) * 10)
            score += min(14, len(industry_matches) * 7)
            score += {"official_known": 16, "likely_official": 8, "unverified": 0}[authority]
            leads.append(
                EnterpriseLead(
                    id=_lead_id(hit.url),
                    company=company,
                    source_title=hit.title,
                    source_url=hit.url,
                    bases=base_matches or _extract_bases(haystack),
                    industries=industry_matches,
                    recommended_roles=direction_matches or directions[:3],
                    source_kind="exa_web",
                    source_authority=authority,
                    score=min(100, score),
                    rationale=(
                        f"Exa AI 搜索命中；Base：{'、'.join(base_matches) or '待核对'}；"
                        f"来源可信度：{authority}"
                    ),
                    application_channels=(
                        _application_channels(catalog_entry) if catalog_entry else []
                    ),
                    application_readiness=(
                        _application_readiness(catalog_entry)
                        if catalog_entry
                        else "needs_channel_verification"
                    ),
                    channel_notice=(
                        "已映射到官方招聘入口；仍需人工核对岗位和截止日期。"
                        if catalog_entry
                        else "搜索结果仅作企业发现线索，尚不能作为简历投递入口。"
                    ),
                )
            )
        return leads

    async def _rank_with_ai(
        self,
        candidates: list[EnterpriseLead],
        resume: ResumeProfile,
        bases: list[str],
        directions: list[str],
        industries: list[str],
    ) -> list[EnterpriseLead]:
        model = OpenAIChatModel(
            self.settings.llm_model or "",
            provider=OpenAIProvider(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
            ),
        )
        agent = Agent(
            model,
            output_type=AIRankingOutput,
            retries=1,
            instructions=(
                "你是中国就业企业检索排序器。只能依据给定来源排序，不得发明企业、岗位或招聘状态。"
                "优先 Base 地匹配、专业/岗位可迁移性、行业偏好和官方来源。任何专业都应公平处理，"
                "不得默认技术岗。返回候选索引、0-100 分、简短理由和建议检索的岗位关键词。"
            ),
        )
        compact = [
            {
                "index": index,
                "company": lead.company,
                "title": lead.source_title,
                "bases": lead.bases[:8],
                "industries": lead.industries[:8],
                "source_authority": lead.source_authority,
                "base_score": lead.score,
            }
            for index, lead in enumerate(candidates)
        ]
        prompt = json.dumps(
            {
                "candidate": {
                    "bases": bases,
                    "directions": directions,
                    "industries": industries,
                    "major": resume.education[0].major if resume.education else None,
                    "years_experience": resume.years_experience,
                    "skills": resume.skills[:15],
                },
                "sources": compact,
            },
            ensure_ascii=False,
        )
        result = await agent.run(prompt)
        ranking = {item.index: item for item in result.output.items if item.index < len(candidates)}
        reranked: list[EnterpriseLead] = []
        for index, lead in enumerate(candidates):
            item = ranking.get(index)
            if item:
                lead = lead.model_copy(
                    update={
                        "score": item.score,
                        "rationale": item.rationale,
                        "recommended_roles": item.recommended_roles or lead.recommended_roles,
                    }
                )
            reranked.append(lead)
        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked


def _infer_company(title: str, highlights: str) -> str:
    for entry in CHINA_ENTERPRISE_CATALOG:
        if entry.name in title or entry.name in highlights[:500]:
            return entry.name
    cleaned = re.sub(r"\s*[-_|].*$", "", title).strip()
    prefix_removed = re.sub(r"^(校园招聘|社会招聘|招聘信息|招聘公告)\s*[-—:：]?\s*", "", cleaned)
    suffix_removed = re.sub(
        r"(校园招聘|社会招聘|招聘信息|招聘公告|招聘官网|官方招聘|招聘)$", "", prefix_removed
    ).strip(" -—_|：:")
    return (suffix_removed or title)[:100]


def _token_overlap(direction: str, haystack: str) -> bool:
    tokens = [token for token in re.findall(r"[\w+#.-]+", direction.casefold()) if len(token) > 1]
    return any(token in haystack for token in tokens)


def _extract_bases(haystack: str) -> list[str]:
    return [base for base in COMMON_BASES if base.casefold() in haystack][:8]


def _lead_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = str(raw).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _deduplicate_leads(leads: list[EnterpriseLead]) -> list[EnterpriseLead]:
    by_key: dict[str, EnterpriseLead] = {}
    for lead in leads:
        domain = (urlparse(str(lead.source_url)).hostname or "").casefold()
        company_key = re.sub(r"\W+", "", lead.company.casefold())
        key = company_key or domain or lead.id
        existing = by_key.get(key)
        lead_has_entry = bool(lead.application_channels)
        existing_has_entry = bool(existing and existing.application_channels)
        if (
            existing is None
            or (lead_has_entry and not existing_has_entry)
            or (lead_has_entry == existing_has_entry and lead.score > existing.score)
        ):
            by_key[key] = lead
    return list(by_key.values())


def _catalog_entry_for_domain(domain: str) -> CatalogEnterprise | None:
    for entry in CHINA_ENTERPRISE_CATALOG:
        entry_domain = (urlparse(entry.career_url).hostname or "").casefold()
        if domain == entry_domain or domain.endswith(f".{entry_domain}"):
            return entry
    return None


def _application_channels(entry: CatalogEnterprise) -> list[ApplicationChannel]:
    return [
        ApplicationChannel(
            label=channel.label,
            url=channel.url,
            channel_type=channel.channel_type,
            official_evidence_url=channel.official_evidence_url,
            availability=channel.availability,
            login_required=channel.login_required,
            supports_job_search=channel.supports_job_search,
            notes=channel.notes,
            verified_on=date(2026, 8, 4),
        )
        for channel in application_channels_for(entry)
    ]


def _application_readiness(entry: CatalogEnterprise) -> str:
    channels = application_channels_for(entry)
    direct_types = {"official_career_home", "campus_portal", "social_portal", "internship_portal"}
    if any(
        channel.channel_type in direct_types
        and channel.availability in {"openings_live", "entry_hub", "check_required"}
        for channel in channels
    ):
        return "direct_official"
    return "official_hub"
