from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .campaign import CampaignService, missing_resume_fields
from .config import Settings
from .models import AgentReply, JobSearchQuery, ResumePatch, public_model_dict
from .store import InMemorySessionStore


@dataclass
class AgentDependencies:
    session_id: str
    store: InMemorySessionStore
    campaign_service: CampaignService


def build_agent(settings: Settings) -> Agent[AgentDependencies, AgentReply]:
    if not settings.llm_configured:
        raise RuntimeError("LLM configuration is missing; run the llm-api-config skill first")
    provider = OpenAIProvider(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )
    model = OpenAIChatModel(settings.llm_model or "", provider=provider)
    agent = Agent[AgentDependencies, AgentReply](
        model,
        deps_type=AgentDependencies,
        output_type=AgentReply,
        retries=2,
        instructions=(
            "你是简历海投辅助 Agent。你只能帮助用户完善真实简历、搜索职位、推荐就业目的地，"
            "以及生成 dry-run 投递草稿。严禁虚构经历、学历、技能或成果。"
            "你服务所有专业与行业，不得把未指定方向的用户默认成软件、技术或人工智能岗位。"
            "严禁声称已经投递，也不能绕过人工复核。若缺少字段，应明确逐项询问。"
            "用户给出字段值后，调用 update_resume_template 写入模板。"
            "最终必须用简体中文返回结构化结果。"
        ),
    )

    @agent.tool
    async def inspect_resume(ctx: RunContext[AgentDependencies]) -> dict[str, Any]:
        """Inspect the current resume template and its canonical missing fields."""
        session = await ctx.deps.store.get(ctx.deps.session_id)
        return {
            "resume": public_model_dict(session.resume),
            "missing_fields": [public_model_dict(item) for item in missing_resume_fields(session.resume)],
        }

    @agent.tool
    async def update_resume_template(
        ctx: RunContext[AgentDependencies], field: str, value: Any
    ) -> dict[str, Any]:
        """Write a user-provided value into one supported resume-template field."""
        allowed = set(ResumePatch.model_fields)
        if field not in allowed:
            return {"updated": False, "error": f"unsupported field: {field}"}
        patch = ResumePatch.model_validate({field: value})
        session = await ctx.deps.store.update_resume(ctx.deps.session_id, patch)
        return {
            "updated": True,
            "field": field,
            "missing_fields": [item.field for item in missing_resume_fields(session.resume)],
        }

    @agent.tool
    async def search_matching_jobs(
        ctx: RunContext[AgentDependencies], direction: str, limit: int = 8
    ) -> dict[str, Any]:
        """Read current public job listings; this tool never applies to a job."""
        session = await ctx.deps.store.get(ctx.deps.session_id)
        jobs = await ctx.deps.campaign_service.job_provider.search(
            JobSearchQuery(
                direction=direction,
                preferred_locations=session.resume.base_locations or session.preferred_locations,
                remote_preference=session.remote_preference,
                limit=min(max(limit, 1), 12),
            )
        )
        return {
            "count": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "remote": job.remote,
                    "url": str(job.url),
                }
                for job in jobs
            ],
        }

    @agent.tool
    async def preview_campaign(ctx: RunContext[AgentDependencies]) -> dict[str, Any]:
        """Generate a non-sending campaign preview behind the hard dry-run gate."""
        session = await ctx.deps.store.get(ctx.deps.session_id)
        preview = await ctx.deps.campaign_service.preview(session, limit=8)
        return {
            "status": preview.status,
            "delivery_mode": preview.delivery_mode,
            "missing_fields": [item.field for item in preview.missing_fields],
            "job_count": len(preview.jobs),
            "draft_count": len(preview.application_drafts),
            "destinations": [item.destination for item in preview.recommended_destinations],
            "notice": preview.notice,
        }

    return agent


def compact_session_context(session_data: dict[str, Any]) -> str:
    return json.dumps(session_data, ensure_ascii=False, separators=(",", ":"))
