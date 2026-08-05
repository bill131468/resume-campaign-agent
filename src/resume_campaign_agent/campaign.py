from __future__ import annotations

import re

from .jobs import JobProvider, recommend_destinations
from .models import (
    ApplicationDraft,
    CampaignPreview,
    JobSearchQuery,
    MissingField,
    ResumeProfile,
    SessionState,
)


def missing_resume_fields(resume: ResumeProfile) -> list[MissingField]:
    checks: list[tuple[bool, MissingField]] = [
        (
            bool(resume.full_name and resume.full_name.strip()),
            MissingField(field="full_name", label="姓名", reason="招聘方需要识别候选人", prompt="请提供你的姓名。"),
        ),
        (
            resume.email is not None,
            MissingField(field="email", label="邮箱", reason="招聘方需要联系邮箱", prompt="请提供常用求职邮箱。"),
        ),
        (
            bool(resume.phone and len(resume.phone.strip()) >= 7),
            MissingField(field="phone", label="电话", reason="招聘方需要有效联系电话", prompt="请提供带区号的联系电话。"),
        ),
        (
            bool(resume.city and resume.city.strip()),
            MissingField(field="city", label="当前城市", reason="用于判断通勤与搬迁匹配", prompt="你目前在哪个城市？"),
        ),
        (
            bool(resume.target_roles or resume.target_industries or resume.education),
            MissingField(field="target_roles", label="专业/岗位方向", reason="企业和职位搜索需要专业、岗位或教育专业中的至少一项", prompt="请填写目标岗位、目标行业，或完整教育专业。"),
        ),
        (
            len(resume.skills) >= 3,
            MissingField(field="skills", label="技能", reason="至少 3 项技能才能进行基础岗位匹配", prompt="请提供至少 3 项真实技能。"),
        ),
        (
            bool(resume.summary and len(resume.summary.strip()) >= 20),
            MissingField(field="summary", label="个人简介", reason="需要至少 20 字的真实职业摘要", prompt="请用 2-4 句话说明经验、专长与目标。"),
        ),
        (
            bool(resume.education),
            MissingField(field="education", label="教育经历", reason="简历模板需要至少一段教育经历", prompt="请提供学校、学历、专业和毕业年份。"),
        ),
        (
            resume.years_experience <= 0 or bool(resume.work_experience),
            MissingField(field="work_experience", label="工作经历", reason="已有工作年限时需提供对应经历", prompt="请提供公司、岗位、起止日期和成果。"),
        ),
    ]
    return [missing for valid, missing in checks if not valid]


class CampaignService:
    def __init__(self, job_provider: JobProvider) -> None:
        self.job_provider = job_provider

    async def preview(self, session: SessionState, limit: int = 10) -> CampaignPreview:
        missing = missing_resume_fields(session.resume)
        directions = (
            session.resume.target_roles
            or session.resume.target_industries
            or ([session.resume.education[0].major] if session.resume.education else [])
        )
        preferred_locations = (
            session.resume.base_locations or session.preferred_locations
        )
        jobs = []
        seen: set[str] = set()
        for direction in directions[:3]:
            found = await self.job_provider.search(
                JobSearchQuery(
                    direction=direction,
                    preferred_locations=preferred_locations,
                    remote_preference=session.remote_preference,
                    limit=limit,
                )
            )
            for job in found:
                if job.id not in seen:
                    seen.add(job.id)
                    jobs.append(job)
                if len(jobs) >= limit:
                    break
            if len(jobs) >= limit:
                break

        jobs = [
            job
            for job in jobs
            if is_seniority_compatible(job.title, session.resume.years_experience)
        ]

        destinations = recommend_destinations(jobs, preferred_locations)
        drafts: list[ApplicationDraft] = []
        if not missing:
            skill_set = {skill.casefold(): skill for skill in session.resume.skills}
            for job in jobs:
                job_text = " ".join([job.title, job.description_excerpt, *job.tags]).casefold()
                matched = [original for key, original in skill_set.items() if key in job_text]
                note = (
                    f"您好，我希望应聘贵公司的{job.title}岗位。"
                    f"我的目标方向与该岗位一致，并具备{('、'.join(matched[:4]) or '相关')}经验。"
                    "附件内容为待本人复核的简历草稿，本系统不会自动发送。"
                )
                drafts.append(
                    ApplicationDraft(
                        job_id=job.id,
                        job_title=job.title,
                        company=job.company,
                        destination="Remote" if job.remote else job.location,
                        job_url=job.url,
                        resume_snapshot=session.resume.model_copy(deep=True),
                        cover_note=note,
                        matched_skills=matched,
                    )
                )
        status = "needs_input" if missing else "ready_for_review"
        notice = (
            "简历仍有必填项缺失；已完成职位搜索，但不会生成或发送申请。"
            if missing
            else "已生成仅供人工复核的投递草稿；发送能力被永久禁用。"
        )
        return CampaignPreview(
            session_id=session.id,
            status=status,
            missing_fields=missing,
            jobs=jobs,
            recommended_destinations=destinations,
            application_drafts=drafts,
            notice=notice,
        )


def is_seniority_compatible(title: str, years_experience: float) -> bool:
    """Fail closed on obvious seniority mismatches before a draft is created."""
    normalized = title.casefold()
    tokens = set(re.findall(r"[a-z]+", normalized))
    executive = {"director", "head", "principal", "staff"}
    advanced = executive | {"senior", "lead", "manager"}
    if years_experience < 2 and tokens & advanced:
        return False
    if years_experience < 5 and tokens & executive:
        return False
    return True
