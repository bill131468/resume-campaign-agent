from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .campaign import missing_resume_fields
from .config import Settings
from .models import (
    ResumeOptimizationRequest,
    ResumeOptimizationResponse,
    ResumeOptimizationSuggestion,
    ResumeProfile,
    ResumeReviewDimension,
    ResumeReviewFinding,
    ResumeReviewRequest,
    ResumeReviewResponse,
    SessionState,
)


DIMENSION_LABELS = {
    "completeness": "完整性",
    "relevance": "岗位匹配",
    "evidence": "成果证据",
    "credibility": "可信度",
    "clarity": "表达清晰",
    "readability": "结构可读",
}

DIRECT_IDENTIFIER_FIELDS = {
    "full_name", "preferred_name", "email", "phone", "wechat",
    "expected_salary", "work_authorization",
}


class AIReviewFinding(BaseModel):
    field_path: str = Field(min_length=1, max_length=200)
    severity: Literal["critical", "warning", "suggestion"]
    title: str = Field(min_length=2, max_length=160)
    observation: str = Field(min_length=2, max_length=800)
    recommendation: str = Field(min_length=2, max_length=800)
    question_to_user: str | None = Field(default=None, max_length=500)


class AIReviewOutput(BaseModel):
    findings: list[AIReviewFinding] = Field(default_factory=list, max_length=16)
    strengths: list[str] = Field(default_factory=list, max_length=8)
    evidence_questions: list[str] = Field(default_factory=list, max_length=10)


class AIOptimizationItem(BaseModel):
    field_path: str = Field(min_length=1, max_length=200)
    change_type: Literal["clarify", "compress", "structure", "target", "grammar", "evidence_prompt"] = "clarify"
    suggested_text: str = Field(min_length=2, max_length=3000)
    rationale: str = Field(min_length=2, max_length=600)
    evidence_paths: list[str] = Field(default_factory=list, max_length=8)


class AIOptimizationOutput(BaseModel):
    suggestions: list[AIOptimizationItem] = Field(default_factory=list, max_length=20)


def _clean(value: object | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _redact_direct_identifiers(text: str | None) -> str | None:
    if text is None:
        return None
    value = str(text)
    value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[已移除邮箱]", value, flags=re.I)
    value = re.sub(r"(?<!\d)(?:\+?86[ -]?)?1[3-9]\d(?:[ -]?\d){8}(?!\d)", "[已移除手机号]", value)
    value = re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "[已移除证件号]", value)
    value = re.sub(r"(?:微信|wechat|weixin)\s*(?:号|id)?\s*[:：]?\s*[A-Za-z][A-Za-z0-9_-]{5,19}", "[已移除微信号]", value, flags=re.I)
    return value


def _deidentified_resume(resume: ResumeProfile) -> dict:
    data = resume.model_dump(mode="json", exclude_none=True)
    for field in DIRECT_IDENTIFIER_FIELDS:
        data.pop(field, None)
    for education in data.get("education", []):
        education.pop("student_id", None)
    for certificate in data.get("certificates", []):
        certificate.pop("credential_id", None)
    for experience in data.get("work_experience", []):
        experience.pop("leaving_reason", None)

    def scrub(value):
        if isinstance(value, str):
            return _redact_direct_identifiers(value)
        if isinstance(value, list):
            return [scrub(item) for item in value]
        if isinstance(value, dict):
            return {key: scrub(item) for key, item in value.items()}
        return value

    return scrub(data)


def _editable_text_fields(resume: ResumeProfile) -> dict[str, str]:
    fields: dict[str, str] = {}

    def put(path: str, value: object | None) -> None:
        text = _clean(value)
        if text:
            fields[path] = text

    put("professional_headline", resume.professional_headline)
    put("summary", resume.summary)
    put("self_evaluation", resume.self_evaluation)
    put("additional_information", resume.additional_information)
    for index, item in enumerate(resume.work_experience[:6]):
        put(f"work_experience.{index}.responsibilities", item.responsibilities)
        for bullet_index, bullet in enumerate(item.highlights):
            put(f"work_experience.{index}.highlights.{bullet_index}", bullet)
    for index, item in enumerate(resume.projects[:6]):
        put(f"projects.{index}.description", item.description)
        for bullet_index, bullet in enumerate(item.highlights):
            put(f"projects.{index}.highlights.{bullet_index}", bullet)
    for index, item in enumerate(resume.campus_experience[:4]):
        put(f"campus_experience.{index}.description", item.description)
    return fields


def _resume_corpus(resume: ResumeProfile) -> str:
    data = _deidentified_resume(resume)
    return json.dumps(data, ensure_ascii=False).casefold()


def _target_tokens(target: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[a-zA-Z0-9+#.]{2,}|[\u4e00-\u9fff]{2,8}", target)
        if token.strip()
    }


def _has_metric(text: str) -> bool:
    return bool(re.search(r"\d|%|％|余|超过|不少于|提升|降低|增长|缩短|节省", text))


def _rule_review(resume: ResumeProfile, target: str | None, job_description: str | None) -> tuple[dict[str, int], list[ResumeReviewFinding], list[str], list[str]]:
    missing = missing_resume_fields(resume)
    findings: list[ResumeReviewFinding] = []
    questions: list[str] = []
    for index, item in enumerate(missing):
        findings.append(ResumeReviewFinding(
            id=f"missing-{index}-{item.field.replace('.', '-')}",
            field_path=item.field,
            severity="critical",
            title=f"缺少{item.label}",
            observation=item.reason,
            recommendation=item.prompt,
            question_to_user=item.prompt,
        ))
        questions.append(item.prompt)

    completeness = max(20, 100 - len(missing) * 11)
    if not resume.projects and not resume.work_experience and not resume.campus_experience:
        completeness = max(20, completeness - 15)
        findings.append(ResumeReviewFinding(
            id="no-experience-evidence",
            field_path="work_experience|projects|campus_experience",
            severity="warning",
            title="缺少经历证据",
            observation="简历目前没有工作、项目或校园经历，招聘方难以判断能力如何落地。",
            recommendation="至少补充一段真实经历，并写清任务、行动、产出和可核验结果。",
            question_to_user="哪一段真实经历最能证明你的核心能力？你具体做了什么？",
        ))
        questions.append("哪一段真实经历最能证明你的核心能力？你具体做了什么？")

    effective_target = _clean(target) or (resume.target_roles[0] if resume.target_roles else "")
    target_text = " ".join(filter(None, [effective_target, _clean(job_description)]))
    if target_text:
        tokens = _target_tokens(target_text)
        corpus = _resume_corpus(resume)
        matched = {token for token in tokens if token in corpus}
        relevance = min(96, 42 + int(54 * len(matched) / max(1, len(tokens))))
        if len(matched) < max(1, len(tokens) // 3):
            findings.append(ResumeReviewFinding(
                id="weak-target-match",
                field_path="summary|skills|work_experience|projects",
                severity="warning",
                title="目标方向的关键词证据偏少",
                observation=f"目标“{effective_target or '岗位说明'}”与当前简历的直接匹配信号不足。",
                recommendation="只从真实经历中选择与目标职责相关的技能、任务和成果，前置到摘要及经历要点。",
                question_to_user="你有哪些真实任务与目标岗位的核心职责直接对应？",
            ))
            questions.append("你有哪些真实任务与目标岗位的核心职责直接对应？")
    else:
        relevance = 55
        findings.append(ResumeReviewFinding(
            id="missing-review-target",
            field_path="target_roles",
            severity="suggestion",
            title="尚未指定审核目标",
            observation="通用审核可以检查质量，但无法判断针对某一岗位的取舍。",
            recommendation="填写一个目标岗位；有职位描述时一并粘贴，可获得更准确的匹配审核。",
        ))

    bullets = [
        bullet for item in resume.work_experience for bullet in item.highlights
    ] + [bullet for item in resume.projects for bullet in item.highlights]
    metric_count = sum(_has_metric(item) for item in bullets)
    evidence = min(96, 38 + min(len(bullets), 5) * 7 + (metric_count / max(1, len(bullets))) * 25)
    if not bullets:
        evidence = 30
    if bullets and metric_count == 0:
        findings.append(ResumeReviewFinding(
            id="unquantified-results",
            field_path="work_experience.highlights|projects.highlights",
            severity="warning",
            title="成果缺少可核验尺度",
            observation="现有成果要点没有时间、数量、范围、质量或影响等尺度。",
            recommendation="不要编造数字；回查真实记录，补充能核实的规模、频次、周期或交付物。",
            question_to_user="这些成果能用哪些真实的数量、范围、周期或交付物来验证？",
        ))
        questions.append("这些成果能用哪些真实的数量、范围、周期或交付物来验证？")

    credibility = 92
    if resume.years_experience > 0 and not resume.work_experience:
        credibility -= 40
    risky_claims = re.findall(r"行业第一|业内领先|顶尖|精通|专家|显著提升", _resume_corpus(resume))
    if risky_claims and not bullets:
        credibility -= 20
        findings.append(ResumeReviewFinding(
            id="unsupported-strong-claims",
            field_path="summary|self_evaluation",
            severity="warning",
            title="强结论缺少支撑",
            observation="摘要或评价包含较强能力结论，但经历区缺少对应证据。",
            recommendation="降低无法证明的强度，或补充真实项目、职责和结果作为证据。",
        ))

    summary_length = len(_clean(resume.summary))
    clarity = 85
    if summary_length == 0:
        clarity = 35
    elif summary_length < 35:
        clarity = 58
    elif summary_length > 500:
        clarity = 62
        findings.append(ResumeReviewFinding(
            id="summary-too-long",
            field_path="summary",
            severity="suggestion",
            title="职业摘要过长",
            observation="摘要超过 500 字，核心定位和证据容易被淹没。",
            recommendation="压缩为定位、核心能力、代表性证据和求职方向四部分。",
        ))

    section_count = sum(bool(section) for section in (
        resume.education, resume.work_experience, resume.projects,
        resume.campus_experience, resume.certificates, resume.awards,
    ))
    readability = min(94, 48 + section_count * 7 + (10 if bullets else 0))
    if len(resume.skills) > 20:
        readability -= 8
        findings.append(ResumeReviewFinding(
            id="skills-too-wide",
            field_path="skills",
            severity="suggestion",
            title="技能列表过宽",
            observation="技能数量较多，重点不够清晰。",
            recommendation="围绕目标岗位保留最相关且能被经历证明的技能，其余降级或删除。",
        ))

    strengths: list[str] = []
    if resume.education:
        strengths.append("教育背景信息完整，可支持通用网申字段填写。")
    if bullets:
        strengths.append(f"已有 {len(bullets)} 条成果或产出，可进一步做证据化表达。")
    if len(resume.skills) >= 3:
        strengths.append("技能信息已形成基础集合，可用于岗位匹配。")
    if resume.projects:
        strengths.append("项目经历能够补充工作经历之外的能力证据。")

    scores = {
        "completeness": int(completeness),
        "relevance": int(relevance),
        "evidence": int(evidence),
        "credibility": max(0, int(credibility)),
        "clarity": int(clarity),
        "readability": max(0, int(readability)),
    }
    return scores, findings, strengths, list(dict.fromkeys(questions))[:12]


def _dimension_summary(key: str, score: int) -> str:
    band = "表现稳定" if score >= 80 else "仍有提升空间" if score >= 60 else "建议优先处理"
    return f"{DIMENSION_LABELS[key]}得分 {score}，{band}。"


def _grade(score: int) -> Literal["A", "B", "C", "D"]:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def _rule_optimization(resume: ResumeProfile, limit: int) -> list[ResumeOptimizationSuggestion]:
    suggestions: list[ResumeOptimizationSuggestion] = []

    def add(path: str, change_type: str, original: str, suggested: str, rationale: str) -> None:
        if len(suggestions) >= limit:
            return
        suggestions.append(ResumeOptimizationSuggestion(
            id=f"rule-{len(suggestions) + 1}-{path.replace('.', '-')}",
            field_path=path,
            change_type=change_type,
            original_text=original,
            suggested_text=suggested,
            rationale=rationale,
            evidence_basis=[original] if original else [],
        ))

    summary = _clean(resume.summary)
    if not summary:
        add(
            "summary", "evidence_prompt", "",
            "【待你补充】用 2–4 句话写明职业定位、真实年限或阶段、核心能力、代表性证据和目标方向。",
            "缺少职业摘要；先向用户取证，不能由模型代编。",
        )
    elif resume.professional_headline and not summary.startswith(resume.professional_headline):
        add(
            "summary", "structure", summary,
            f"{_clean(resume.professional_headline)}。{summary}",
            "把已有职业定位前置，未添加新的经历或数字。",
        )

    for path, original in _editable_text_fields(resume).items():
        if "highlights" in path and not _has_metric(original):
            add(
                path, "evidence_prompt", original,
                f"{original}【请补充可核实的范围、数量、周期、质量标准或交付物；没有记录则保持原文】",
                "当前要点描述了结果，但缺少可核验尺度；明确要求用户提供事实，不生成数字。",
            )
        elif len(original) > 450 and path in {"summary", "self_evaluation", "additional_information"}:
            add(
                path, "compress", original,
                original[:440].rstrip("，。；; ") + "……【请由本人确认删减内容】",
                "文本较长，先生成保守删减预览；必须由用户确认，避免误删关键事实。",
            )
    return suggestions[:limit]


@dataclass
class ResumeReviewService:
    settings: Settings
    _review_agent: Agent[None, AIReviewOutput] | None = None
    _optimization_agent: Agent[None, str] | None = None

    def _model(self) -> OpenAIChatModel:
        provider = OpenAIProvider(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_base_url,
        )
        return OpenAIChatModel(self.settings.llm_model or "", provider=provider)

    def _get_review_agent(self) -> Agent[None, AIReviewOutput]:
        if self._review_agent is None:
            self._review_agent = Agent(
                self._model(),
                output_type=AIReviewOutput,
                retries=1,
                instructions=(
                    "你是通用职业简历审核员，服务任意专业与行业。只审核给定事实，不得补造经历、数字、技能、学历或结论。"
                    "发现证据不足时必须提出问题，不得替用户回答。审核应关注岗位匹配、可信度、清晰度、成果证据与机器可读性。"
                    "不要输出联系方式，不要建议填写年龄、性别、婚育、证件、民族等敏感信息。输出简体中文。"
                ),
            )
        return self._review_agent

    def _get_optimization_agent(self) -> Agent[None, str]:
        if self._optimization_agent is None:
            self._optimization_agent = Agent(
                self._model(),
                output_type=str,
                retries=0,
                instructions=(
                    "你是通用职业简历编辑。只能重组、压缩或澄清提供的原文；不得创造新公司、新项目、新职责、新技能、新数字或因果关系。"
                    "证据不足时输出 evidence_prompt，并在建议文本中明确标记需要用户补充，不能代填。"
                    "field_path 和 evidence_paths 必须来自 allowed_fields。若把其他经历证据前置到摘要，必须在 evidence_paths 中列出来源路径。"
                    "每条建议应能直接与原文对照。只输出一个 JSON 对象，不要 Markdown："
                    '{"suggestions":[{"field_path":"...","change_type":"clarify","suggested_text":"...",'
                    '"rationale":"...","evidence_paths":["..."]}]}。输出简体中文。'
                ),
            )
        return self._optimization_agent

    async def review(self, request: ResumeReviewRequest, session: SessionState) -> ResumeReviewResponse:
        target = _clean(request.target_role) or (session.resume.target_roles[0] if session.resume.target_roles else None)
        scores, findings, strengths, questions = _rule_review(
            session.resume, target, request.target_job_description
        )
        ai_used = False
        if request.use_ai and self.settings.llm_configured:
            safe_target = _redact_direct_identifiers(target)
            prompt = json.dumps({
                "target_role": safe_target,
                "target_job_description": _redact_direct_identifiers(request.target_job_description),
                "resume_without_direct_identifiers": _deidentified_resume(session.resume),
                "rule_scores": scores,
                "rule_findings": [item.model_dump(mode="json") for item in findings],
            }, ensure_ascii=False)
            try:
                result = await asyncio.wait_for(
                    self._get_review_agent().run(prompt),
                    timeout=max(self.settings.ai_ranking_timeout_seconds, 75),
                )
                existing = {(item.field_path, item.title) for item in findings}
                for item in result.output.findings:
                    if (item.field_path, item.title) in existing:
                        continue
                    findings.append(ResumeReviewFinding(
                        id=f"ai-{len(findings) + 1}",
                        **item.model_dump(),
                    ))
                strengths.extend(result.output.strengths)
                questions.extend(result.output.evidence_questions)
                ai_used = True
            except Exception:
                ai_used = False

        weights = {
            "completeness": .20, "relevance": .20, "evidence": .20,
            "credibility": .18, "clarity": .12, "readability": .10,
        }
        overall = round(sum(scores[key] * weights[key] for key in weights))
        dimensions = [
            ResumeReviewDimension(
                key=key,
                label=DIMENSION_LABELS[key],
                score=score,
                summary=_dimension_summary(key, score),
            )
            for key, score in scores.items()
        ]
        return ResumeReviewResponse(
            session_id=session.id,
            overall_score=overall,
            grade=_grade(overall),
            target_role=target,
            dimensions=dimensions,
            findings=findings[:30],
            strengths=list(dict.fromkeys(strengths))[:12],
            evidence_questions=list(dict.fromkeys(questions))[:12],
            ai_used=ai_used,
            notice="审核不会修改原简历；模型仅接收移除姓名、联系方式、微信、证件编号等直接标识后的职业内容。",
        )

    async def optimize(
        self, request: ResumeOptimizationRequest, session: SessionState
    ) -> ResumeOptimizationResponse:
        target = _clean(request.target_role) or (session.resume.target_roles[0] if session.resume.target_roles else None)
        editable = _editable_text_fields(session.resume)
        safe_editable = {
            path: _redact_direct_identifiers(text) or ""
            for path, text in editable.items()
        }
        suggestions = _rule_optimization(session.resume, request.max_suggestions)
        ai_used = False
        if request.use_ai and self.settings.llm_configured and editable:
            prompt = json.dumps({
                "target_role": _redact_direct_identifiers(target),
                "target_job_description": _redact_direct_identifiers(request.target_job_description),
                "allowed_fields": safe_editable,
                "known_context": {
                    "target_roles": session.resume.target_roles,
                    "skills": session.resume.skills,
                    "major": session.resume.education[0].major if session.resume.education else None,
                },
                "max_suggestions": min(request.max_suggestions, 6),
            }, ensure_ascii=False)
            try:
                result = await asyncio.wait_for(
                    self._get_optimization_agent().run(prompt),
                    timeout=max(self.settings.ai_ranking_timeout_seconds, 75),
                )
                raw_output = result.output.strip()
                if raw_output.startswith("```"):
                    raw_output = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_output, flags=re.I)
                start, end = raw_output.find("{"), raw_output.rfind("}")
                if start < 0 or end <= start:
                    raise ValueError("optimization model did not return a JSON object")
                parsed_output = AIOptimizationOutput.model_validate_json(raw_output[start:end + 1])
                accepted: list[ResumeOptimizationSuggestion] = []
                accepted_paths: set[str] = set()
                for item in parsed_output.suggestions:
                    original = editable.get(item.field_path)
                    if not original or item.field_path in accepted_paths:
                        continue
                    evidence_paths = [
                        path for path in item.evidence_paths
                        if path in editable and path != item.field_path
                    ]
                    evidence_texts = [original, *(editable[path] for path in evidence_paths)]
                    supported_numbers = set(re.findall(r"\d+(?:\.\d+)?", " ".join(evidence_texts)))
                    new_numbers = set(re.findall(r"\d+(?:\.\d+)?", item.suggested_text)) - supported_numbers
                    if new_numbers:
                        continue
                    accepted.append(ResumeOptimizationSuggestion(
                        id=f"ai-{len(accepted) + 1}-{item.field_path.replace('.', '-')}",
                        field_path=item.field_path,
                        change_type=item.change_type,
                        original_text=original,
                        suggested_text=item.suggested_text,
                        rationale=item.rationale,
                        evidence_basis=evidence_texts,
                    ))
                    accepted_paths.add(item.field_path)
                if accepted:
                    suggestions = accepted[:request.max_suggestions]
                    ai_used = True
            except Exception:
                ai_used = False

        return ResumeOptimizationResponse(
            session_id=session.id,
            target_role=target,
            suggestions=suggestions[:request.max_suggestions],
            priority_order=[item.id for item in suggestions[:request.max_suggestions]],
            ai_used=ai_used,
            notice="优化结果是待确认建议，不会写回原简历；任何新增事实、数字或敏感字段都必须由用户本人提供。",
        )
