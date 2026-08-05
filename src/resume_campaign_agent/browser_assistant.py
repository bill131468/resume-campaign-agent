from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import Settings
from .models import (
    BrowserAnalyzeRequest,
    BrowserFillAction,
    BrowserFillPlan,
    BrowserFormField,
    BrowserJobRankRequest,
    BrowserJobSelection,
    BrowserSkippedField,
    ResumeProfile,
    SessionState,
)
from .campaign import is_seniority_compatible


PROTECTED_WORDS = (
    "password", "passcode", "密码", "验证码", "captcha", "otp", "短信验证",
    "身份证", "证件号", "护照", "passport", "社会保障", "social security",
    "性别", "gender", "出生", "birth", "婚姻", "marital", "民族", "ethnicity",
    "政治面貌", "户籍", "户口", "家庭成员", "紧急联系人", "home address",
    "家庭住址", "详细地址", "期望薪资", "expected salary", "薪酬", "salary",
    "同意", "授权", "隐私", "consent", "agreement",
)

UNSUPPORTED_TYPES = {
    "password", "hidden", "file", "submit", "button", "reset", "image",
    "checkbox", "radio", "color", "range",
}

# Order matters: specific labels must win over generic terms such as "name".
FIELD_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("email", ("email", "e-mail", "邮箱", "电子邮件")),
    ("phone", ("phone", "mobile", "tel", "手机号", "手机号码", "联系电话", "电话")),
    ("preferred_name", ("preferred name", "常用名", "英文名")),
    ("full_name", ("full name", "candidate name", "真实姓名", "姓名", "name")),
    ("wechat", ("wechat", "微信号", "微信")),
    ("city", ("current city", "current location", "现居城市", "现居地", "当前城市", "所在城市")),
    ("base_location", ("preferred location", "desired location", "work location preference", "意向工作地", "期望工作地点", "目标城市", "意向城市")),
    ("target_role", ("target role", "position applied", "申请岗位", "应聘岗位", "意向岗位", "目标职位")),
    ("professional_headline", ("headline", "职业标题", "个人头衔")),
    ("years_experience", ("years of experience", "工作年限", "从业年限")),
    ("skills", ("skills", "技能专长", "专业技能", "技能")),
    ("summary", ("professional summary", "self evaluation", "个人简介", "自我评价", "个人总结", "简介")),
    ("portfolio_url", ("portfolio", "作品集", "个人网站")),
    ("linkedin_url", ("linkedin", "领英")),
    ("education.0.school", ("university", "school", "毕业院校", "学校", "院校")),
    ("education.0.major", ("major", "专业名称", "所学专业", "专业")),
    ("education.0.degree", ("degree", "学历", "学位")),
    ("education.0.graduation_year", ("graduation year", "毕业年份", "毕业年")),
    ("work_experience.0.company", ("current company", "最近公司", "公司名称", "工作单位")),
    ("work_experience.0.title", ("current title", "current position", "最近职位", "当前职位", "职务")),
    ("available_date", ("available date", "到岗日期", "可入职日期")),
    ("job_seeking_status", ("job seeking status", "求职状态", "当前求职状态")),
    ("target_industries", ("preferred industry", "target industry", "意向行业", "目标行业")),
    ("employment_types", ("employment type", "job type", "工作类型", "用工类型", "期望工作性质")),
    ("relocation_preference", ("willing to relocate", "relocation preference", "是否接受异地", "是否愿意调动")),
    ("work_authorization", ("work authorization", "right to work", "工作许可", "就业许可")),
    ("education.0.college", ("college or faculty", "学院名称", "院系名称", "院系")),
    ("education.0.location", ("school location", "学校所在地", "院校所在地")),
    ("education.0.education_type", ("education type", "学习形式", "教育类型")),
    ("education.0.minor", ("minor", "辅修专业", "第二专业")),
    ("education.0.gpa", ("gpa", "平均绩点")),
    ("education.0.rank", ("class rank", "年级排名", "专业排名")),
    ("education.0.core_courses", ("core courses", "主修课程", "核心课程")),
    ("education.0.thesis", ("thesis", "毕业论文", "论文题目")),
    ("work_experience.0.department", ("current department", "部门名称", "所在部门")),
    ("work_experience.0.location", ("work location", "工作地点", "工作所在地")),
    ("work_experience.0.responsibilities", ("job responsibilities", "work description", "工作职责", "工作内容", "经历描述")),
    ("projects.0.name", ("project name", "项目名称")),
    ("projects.0.role", ("project role", "项目角色", "项目职务")),
    ("projects.0.description", ("project description", "项目描述", "项目简介")),
    ("campus_experience.0.organization", ("campus organization", "社团组织", "校园组织")),
    ("campus_experience.0.role", ("campus role", "社团职务", "校园职务")),
    ("campus_experience.0.description", ("campus experience description", "校园经历描述", "社团经历描述")),
    ("certificates", ("certificates", "资格证书", "专业证书", "证书")),
    ("awards", ("awards", "honors", "获奖情况", "荣誉奖励")),
    ("languages", ("languages", "language skills", "语言能力", "外语能力")),
    ("additional_information", ("additional information", "其他信息", "补充信息")),
]


class AIFieldMapping(BaseModel):
    field_index: int = Field(ge=0)
    resume_field: str
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(max_length=200)


class AIFieldMappingResult(BaseModel):
    mappings: list[AIFieldMapping] = Field(default_factory=list, max_length=100)


class AIJobChoice(BaseModel):
    selected_index: int | None = Field(default=None, ge=0, le=200)
    confidence: float = Field(default=0, ge=0, le=1)
    rationale: str = Field(min_length=2, max_length=300)


def _text(field: BrowserFormField) -> str:
    return " ".join(
        part for part in (
            field.label, field.placeholder, field.name, field.element_id, field.autocomplete
        ) if part
    ).casefold()


def _protected_reason(field: BrowserFormField) -> str | None:
    if field.input_type.casefold() in UNSUPPORTED_TYPES:
        return f"字段类型 {field.input_type} 不允许自动填写"
    text = _text(field)
    matched = next((word for word in PROTECTED_WORDS if word.casefold() in text), None)
    if matched:
        return f"命中受保护字段规则：{matched}"
    return None


def _resume_values(resume: ResumeProfile) -> dict[str, str]:
    values: dict[str, str] = {}

    def put(key: str, value: object | None) -> None:
        if value is None:
            return
        text = str(value).strip()
        if text:
            values[key] = text

    put("full_name", resume.full_name)
    put("preferred_name", resume.preferred_name)
    put("email", resume.email)
    put("phone", resume.phone)
    put("wechat", resume.wechat)
    put("city", resume.city)
    put("target_role", resume.target_roles[0] if resume.target_roles else None)
    put("professional_headline", resume.professional_headline)
    if resume.years_experience > 0:
        put("years_experience", resume.years_experience)
    put("skills", "、".join(resume.skills))
    put("summary", resume.summary or resume.self_evaluation)
    put("portfolio_url", resume.portfolio_url)
    put("linkedin_url", resume.linkedin_url)
    put("available_date", resume.available_date)
    put("job_seeking_status", resume.job_seeking_status)
    put("base_location", resume.base_locations[0] if resume.base_locations else None)
    put("target_industries", "、".join(resume.target_industries))
    put("employment_types", "、".join(resume.employment_types))
    put("relocation_preference", resume.relocation_preference)
    put("work_authorization", resume.work_authorization)
    put("languages", "、".join(resume.languages))
    put("certificates", "、".join(item.name for item in resume.certificates))
    put("awards", "、".join(item.name for item in resume.awards))
    put("additional_information", resume.additional_information)
    if resume.education:
        education = resume.education[0]
        put("education.0.school", education.school)
        put("education.0.major", education.major)
        put("education.0.degree", education.degree)
        put("education.0.graduation_year", education.graduation_year)
        put("education.0.college", education.college)
        put("education.0.location", education.location)
        put("education.0.education_type", education.education_type)
        put("education.0.minor", education.minor)
        put("education.0.gpa", education.gpa)
        put("education.0.rank", education.rank)
        put("education.0.core_courses", "、".join(education.core_courses))
        put("education.0.thesis", education.thesis)
    if resume.work_experience:
        experience = resume.work_experience[0]
        put("work_experience.0.company", experience.company)
        put("work_experience.0.title", experience.title)
        put("work_experience.0.department", experience.department)
        put("work_experience.0.location", experience.location)
        put("work_experience.0.responsibilities", experience.responsibilities or "\n".join(experience.highlights))
    if resume.projects:
        project = resume.projects[0]
        put("projects.0.name", project.name)
        put("projects.0.role", project.role)
        put("projects.0.description", project.description)
    if resume.campus_experience:
        campus = resume.campus_experience[0]
        put("campus_experience.0.organization", campus.organization)
        put("campus_experience.0.role", campus.role)
        put("campus_experience.0.description", campus.description)
    return values


def _mask(field: str, value: str) -> str:
    if field == "email" and "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:1]}***@{domain}"
    if field == "phone":
        return f"***{value[-4:]}" if len(value) > 4 else "***"
    if field in {"full_name", "preferred_name"}:
        return f"{value[:1]}**"
    return value if len(value) <= 28 else f"{value[:25]}…"


def _deterministic_match(field: BrowserFormField) -> tuple[str, float] | None:
    text = _text(field)
    for resume_field, aliases in FIELD_RULES:
        if resume_field == "skills" and re.search(r"language|语言|外语", text):
            continue
        for alias in aliases:
            alias_folded = alias.casefold()
            if re.search(r"[\u4e00-\u9fff]", alias_folded):
                matched = alias_folded in text
            else:
                matched = re.search(rf"(?<![a-z]){re.escape(alias_folded)}(?![a-z])", text) is not None
            if matched:
                return resume_field, 0.98 if alias_folded in field.label.casefold() else 0.92
    return None


@dataclass
class BrowserAssistant:
    settings: Settings
    _agent: Agent[None, AIFieldMappingResult] | None = None
    _job_agent: Agent[None, AIJobChoice] | None = None

    def _build_agent(self) -> Agent[None, AIFieldMappingResult]:
        provider = OpenAIProvider(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
        )
        model = OpenAIChatModel(self.settings.llm_model or "", provider=provider)
        return Agent(
            model,
            output_type=AIFieldMappingResult,
            retries=1,
            instructions=(
                "你是招聘网站字段映射器。只把网页字段映射到给定的简历语义字段；"
                "不得猜测简历值，不得映射验证码、密码、证件、人口统计、同意授权或提交控件。"
                "不确定时不要返回映射。输出简体中文理由。"
            ),
        )

    def _build_job_agent(self) -> Agent[None, AIJobChoice]:
        provider = OpenAIProvider(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
        )
        model = OpenAIChatModel(self.settings.llm_model or "", provider=provider)
        return Agent(
            model,
            output_type=AIJobChoice,
            retries=1,
            instructions=(
                "你是招聘官网岗位选择器。只能从给定的当前官网岗位链接中选择一个仍在线且最匹配候选人方向、"
                "技能、工作年限和 Base 的岗位。不得发明 URL 或索引，不得选择明显高级于候选人资历的岗位。"
                "如果没有足够匹配的岗位，selected_index 返回 null。"
            ),
        )

    async def rank_jobs(
        self, request: BrowserJobRankRequest, session: SessionState
    ) -> BrowserJobSelection:
        page_origin = _origin(str(request.page_url))
        safe_candidates = [
            item for item in request.candidates
            if _origin(str(item.url)) == page_origin and not _closed_job_text(f"{item.title} {item.metadata}")
        ]
        unsafe_indexes = {item.index for item in request.candidates} - {item.index for item in safe_candidates}
        if not safe_candidates:
            return BrowserJobSelection(
                rationale="当前官网页面没有同源、可核验的在线岗位链接",
                rejected_indexes=[item.index for item in request.candidates],
            )

        scored = sorted(
            (
                (_job_match_score(item.title, item.metadata, session.resume, session.preferred_locations), item)
                for item in safe_candidates
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        rejected = sorted(unsafe_indexes | {
            item.index for score, item in scored
            if score < 0 or not is_seniority_compatible(item.title, session.resume.years_experience)
        })
        eligible = [(score, item) for score, item in scored if item.index not in rejected]
        if not eligible or eligible[0][0] <= 0:
            return BrowserJobSelection(
                rationale="页面岗位与简历方向、技能或 Base 没有足够可靠的匹配",
                rejected_indexes=rejected,
            )

        selected = eligible[0][1]
        confidence = min(0.9, 0.45 + eligible[0][0] / 100)
        rationale = "确定性规则按岗位方向、技能、Base 与资历匹配"
        ai_used = False
        if self.settings.llm_configured:
            if self._job_agent is None:
                self._job_agent = self._build_job_agent()
            prompt = json.dumps(
                {
                    "candidate": {
                        "target_roles": session.resume.target_roles[:8],
                        "skills": session.resume.skills[:20],
                        "years_experience": session.resume.years_experience,
                        "bases": (session.resume.base_locations or session.preferred_locations)[:10],
                        "major": session.resume.education[0].major if session.resume.education else None,
                    },
                    "jobs": [
                        {
                            "index": item.index,
                            "title": item.title,
                            "metadata": item.metadata,
                            "rule_score": score,
                        }
                        for score, item in eligible[:30]
                    ],
                },
                ensure_ascii=False,
            )
            try:
                result = await self._job_agent.run(prompt)
                choice = result.output
                by_index = {item.index: item for _, item in eligible}
                if choice.selected_index in by_index and choice.confidence >= 0.55:
                    selected = by_index[choice.selected_index]
                    confidence = choice.confidence
                    rationale = f"AI 岗位匹配：{choice.rationale}"
                    ai_used = True
            except Exception:
                pass

        return BrowserJobSelection(
            selected_index=selected.index,
            selected_url=selected.url,
            selected_title=selected.title,
            confidence=confidence,
            rationale=rationale,
            ai_used=ai_used,
            rejected_indexes=rejected,
        )

    async def analyze(
        self, request: BrowserAnalyzeRequest, session: SessionState
    ) -> BrowserFillPlan:
        values = _resume_values(session.resume)
        actions: list[BrowserFillAction] = []
        skipped: list[BrowserSkippedField] = []
        unmatched: list[BrowserFormField] = []
        used_indexes: set[int] = set()

        def add_action(field: BrowserFormField, resume_field: str, confidence: float, rationale: str) -> bool:
            value = values.get(resume_field)
            if not value:
                skipped.append(BrowserSkippedField(
                    field_index=field.index,
                    label=field.label or field.name or f"字段 {field.index}",
                    reason=f"简历模板缺少 {resume_field}",
                    safety_category="missing_resume_value",
                ))
                return False
            actions.append(BrowserFillAction(
                field_index=field.index,
                field_signature=field.signature,
                resume_field=resume_field,
                value=value,
                masked_preview=_mask(resume_field, value),
                confidence=confidence,
                rationale=rationale,
            ))
            used_indexes.add(field.index)
            return True

        for field in request.page.fields:
            reason = _protected_reason(field)
            if reason:
                category = "unsupported" if field.input_type.casefold() in UNSUPPORTED_TYPES else "protected"
                skipped.append(BrowserSkippedField(
                    field_index=field.index,
                    label=field.label or field.name or f"字段 {field.index}",
                    reason=reason,
                    safety_category=category,
                ))
                continue
            match = _deterministic_match(field)
            if match:
                add_action(field, match[0], match[1], "本机确定性字段规则")
            else:
                unmatched.append(field)

        ai_used = False
        if request.use_ai and unmatched and self.settings.llm_configured:
            if self._agent is None:
                self._agent = self._build_agent()
            safe_schema = [
                {
                    "field_index": field.index,
                    "tag": field.tag,
                    "input_type": field.input_type,
                    "label": field.label,
                    "placeholder": field.placeholder,
                    "name": field.name,
                    "options": [option.label for option in field.options[:30]],
                }
                for field in unmatched
            ]
            prompt = json.dumps(
                {"available_resume_fields": sorted(values), "web_fields": safe_schema},
                ensure_ascii=False,
            )
            try:
                result = await self._agent.run(prompt)
                lookup = {field.index: field for field in unmatched}
                for mapping in result.output.mappings:
                    field = lookup.get(mapping.field_index)
                    if (
                        field is None
                        or mapping.field_index in used_indexes
                        or mapping.resume_field not in values
                        or mapping.confidence < 0.72
                    ):
                        continue
                    add_action(
                        field,
                        mapping.resume_field,
                        mapping.confidence,
                        f"AI 语义映射：{mapping.rationale}",
                    )
                    ai_used = True
            except Exception:
                # Form preparation remains usable when the model endpoint is unavailable.
                ai_used = False

        accounted = used_indexes | {item.field_index for item in skipped}
        for field in request.page.fields:
            if field.index not in accounted:
                skipped.append(BrowserSkippedField(
                    field_index=field.index,
                    label=field.label or field.name or f"字段 {field.index}",
                    reason="没有足够可靠的简历字段映射",
                    safety_category="unmapped",
                ))

        return BrowserFillPlan(
            session_id=session.id,
            page_url=request.page.url,
            actions=sorted(actions, key=lambda item: item.field_index),
            skipped=sorted(skipped, key=lambda item: item.field_index),
            ai_mapping_used=ai_used,
            notice="只生成本页填表计划；不会读取密码/验证码，不会勾选同意项，也不会点击提交。",
        )


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlparse(url)
    return parsed.scheme.casefold(), (parsed.hostname or "").casefold(), parsed.port


def _closed_job_text(text: str) -> bool:
    folded = text.casefold()
    return any(marker in folded for marker in (
        "职位已下线", "职位已关闭", "招聘已结束", "岗位已下线", "已停止招聘",
        "job closed", "position closed", "no longer accepting", "not available",
    ))


def _job_match_score(title: str, metadata: str, resume: ResumeProfile, preferred: list[str]) -> float:
    haystack = f"{title} {metadata}".casefold()
    score = 0.0
    for role in resume.target_roles[:8]:
        role_folded = role.casefold().strip()
        if role_folded and role_folded in haystack:
            score += 32
        for token in re.findall(r"[a-z0-9+#.]{2,}|[\u4e00-\u9fff]{2,8}", role_folded):
            if token in haystack:
                score += 8
    for skill in resume.skills[:20]:
        if len(skill.strip()) > 1 and skill.casefold() in haystack:
            score += 4
    bases = resume.base_locations or preferred or ([resume.city] if resume.city else [])
    if any(base.casefold() in haystack for base in bases if base):
        score += 22
    if not is_seniority_compatible(title, resume.years_experience):
        score -= 100
    return min(100, score)
