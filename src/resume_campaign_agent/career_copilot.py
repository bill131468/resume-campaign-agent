from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import uuid4

from cryptography.fernet import Fernet

from .career_models import (
    ApplicationCreateRequest,
    ApplicationHistoryEvent,
    ApplicationRecord,
    ApplicationUpdateRequest,
    CandidateJob,
    EvidenceItem,
    EvidenceItemCreate,
    FunnelAnalytics,
    FunnelStage,
    InterviewKitRequest,
    InterviewKitResponse,
    InterviewQuestion,
    InterviewSimulationRequest,
    InterviewSimulationResponse,
    JobDossierRequest,
    JobDossierResponse,
    JobRankingRequest,
    JobRankingResponse,
    JobRequirement,
    PortalAdapter,
    PortalPreflightRequest,
    PortalPreflightResponse,
    RankedJob,
    RecoveryCheckpoint,
    RecoveryCheckpointCreate,
    RecruitmentRiskRequest,
    RecruitmentRiskResponse,
    RecruitmentRiskSignal,
    Reminder,
    ResumeVersion,
    ResumeVersionChange,
    ResumeVersionCreateRequest,
    VaultLeaseRequest,
    VaultLeaseResponse,
    VaultMetadata,
    VaultPutRequest,
    VersionAuditFinding,
    VersionAuditResponse,
)
from .models import ResumeProfile, SessionState


WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{1,30}|[\u4e00-\u9fff]{2,10}")
METRIC_PATTERN = re.compile(r"\d+(?:\.\d+)?")
HARD_MARKERS = ("必须", "要求", "本科及以上", "硕士及以上", "不少于", "至少", "具备", "通过", "持有")
PREFERRED_MARKERS = ("优先", "加分", "熟悉", "有经验者", "preferred", "plus")
SENSITIVE_FIELDS = {
    "identity_number", "home_address", "household_location", "emergency_contact",
    "emergency_phone", "student_id", "birth_date", "family_information",
    "身份证", "家庭地址", "户籍", "紧急联系人", "学号", "出生日期", "家庭成员",
}


PORTAL_ADAPTERS = [
    PortalAdapter(
        id="moka", name="Moka 招聘门户", host_patterns=["mokahr.com", "moka.jobs"],
        capabilities=["岗位识别", "登录接力", "结构化填表", "附件检查", "提交回执"],
        human_steps=["验证码", "人机验证", "最终逐岗位确认"],
    ),
    PortalAdapter(
        id="beisen", name="北森招聘门户", host_patterns=["beisen.com", "italent.cn"],
        capabilities=["岗位识别", "多步骤表单", "附件检查", "断点恢复"],
        human_steps=["登录验证", "敏感字段确认", "最终逐岗位确认"],
    ),
    PortalAdapter(
        id="nowcoder", name="牛客企业招聘", host_patterns=["nowcoder.com"],
        capabilities=["岗位识别", "简历选择", "状态回执"],
        human_steps=["账号登录", "人机验证", "最终逐岗位确认"],
    ),
    PortalAdapter(
        id="liepin", name="猎聘企业门户", host_patterns=["liepin.com"],
        capabilities=["岗位识别", "账号投递", "回执检查"],
        human_steps=["账号登录", "最终逐岗位确认"],
    ),
    PortalAdapter(
        id="generic", name="通用官网表单", host_patterns=["*"],
        capabilities=["可见字段扫描", "字段映射", "只填空白安全字段", "断点恢复"],
        human_steps=["验证码", "附件上传", "敏感字段", "最终逐岗位确认"],
    ),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normal(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.casefold())


def _tokens(value: str) -> list[str]:
    stop = {"负责", "相关", "岗位", "工作", "能力", "进行", "以及", "公司", "要求", "优先", "以上", "具有"}
    result = []
    for token in WORD_PATTERN.findall(value):
        token = token.casefold().strip("./-")
        if len(token) >= 2 and token not in stop:
            result.append(token)
    return list(dict.fromkeys(result))


def _resume_paths(resume: ResumeProfile) -> dict[str, str]:
    output: dict[str, str] = {}

    def walk(value, path: str = ""):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"full_name", "email", "phone", "wechat", "expected_salary", "work_authorization"}:
                    continue
                walk(item, f"{path}.{key}".strip("."))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}.{index}")
        elif value not in (None, ""):
            output[path] = _normal(value)

    walk(resume.model_dump(mode="json", exclude_none=True))
    return output


def _evidence_for(text: str, paths: dict[str, str]) -> list[str]:
    wanted = _tokens(text)
    ranked = []
    for path, value in paths.items():
        corpus = value.casefold()
        score = sum(token in corpus for token in wanted)
        if score:
            ranked.append((score, path))
    return [path for _, path in sorted(ranked, reverse=True)[:6]]


def _description_lines(description: str) -> list[str]:
    lines = []
    for raw in re.split(r"[\r\n；;。]+", description):
        value = raw.strip(" -•\t")
        if len(value) >= 4:
            lines.append(value[:800])
    return list(dict.fromkeys(lines))[:40]


def _classify_requirement(line: str) -> str:
    lowered = line.casefold()
    if any(marker in lowered for marker in HARD_MARKERS) or re.search(r"\d+\s*年", line):
        return "hard"
    if any(marker in lowered for marker in PREFERRED_MARKERS):
        return "preferred"
    if any(marker in line for marker in ("负责", "职责", "推进", "支持", "完成", "协助")):
        return "responsibility"
    return "keyword"


def _resume_hash(resume: ResumeProfile) -> str:
    payload = json.dumps(resume.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _risk_check(request: RecruitmentRiskRequest) -> RecruitmentRiskResponse:
    text = " ".join([request.company, request.title, request.description, request.contact_message]).casefold()
    host = urlparse(request.url).hostname or ""
    signals: list[RecruitmentRiskSignal] = []

    def add(code: str, severity: str, title: str, evidence: str, action: str):
        signals.append(RecruitmentRiskSignal(
            code=code, severity=severity, title=title, evidence=evidence, action=action
        ))

    if any(word in text for word in ("培训贷", "分期培训", "贷款培训")):
        add("training-loan", "critical", "疑似培训贷", "信息中出现培训贷款或分期培训表述", "立即停止并勿提交银行卡或征信信息")
    if any(word in text for word in ("押金", "保证金", "报名费", "入职费", "付费内推", "先交费")):
        add("advance-fee", "critical", "要求预先付费", "招聘信息要求押金、报名费或付费内推", "不要付款，通过企业官网核实")
    if any(word in text for word in ("银行卡密码", "短信验证码", "支付密码", "共享屏幕")):
        add("credential-theft", "critical", "索取高风险凭据", "对方索取支付凭据、短信验证码或要求共享屏幕", "立即终止联系并保留证据")
    if any(word in text for word in ("轻松月入", "日结高薪", "无需面试", "居家刷单")):
        add("unrealistic-claim", "high", "收益承诺异常", "存在无需审核或高收益承诺", "不要提供身份材料，先核验工商与官网信息")
    if request.url and not host:
        add("invalid-url", "high", "投递链接格式异常", "无法解析投递链接域名", "只从企业官网重新进入")
    elif request.url and not request.url.startswith("https://"):
        add("insecure-channel", "medium", "渠道未使用 HTTPS", "链接不是 HTTPS", "不要在该页面填写敏感信息")
    if request.url and host and any(domain in host for domain in ("weidian.com", "pan.baidu.com", "docs.qq.com")):
        add("non-career-host", "high", "投递渠道不像招聘官网", f"当前域名为 {host}", "从企业官网招聘栏目重新核验入口")
    score = min(100, sum({"low": 8, "medium": 20, "high": 35, "critical": 60}[item.severity] for item in signals))
    level = "critical" if score >= 60 else "high" if score >= 35 else "medium" if score >= 15 else "low"
    action = "停止并人工核验" if score >= 35 else "谨慎核验后继续" if score else "未发现明显诈骗信号，仍需核对官网域名"
    return RecruitmentRiskResponse(risk_level=level, score=score, signals=signals, recommended_action=action)


@dataclass
class CareerCopilotService:
    versions: dict[str, ResumeVersion] = field(default_factory=dict)
    applications: dict[str, ApplicationRecord] = field(default_factory=dict)
    checkpoints: dict[str, RecoveryCheckpoint] = field(default_factory=dict)
    evidence_items: dict[str, EvidenceItem] = field(default_factory=dict)
    vault_tokens: dict[str, dict[str, bytes]] = field(default_factory=dict)
    vault_leases: dict[str, tuple[str, list[str], datetime]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _fernet: Fernet = field(default_factory=lambda: Fernet(Fernet.generate_key()))

    def job_dossier(self, request: JobDossierRequest, session: SessionState) -> JobDossierResponse:
        paths = _resume_paths(session.resume)
        corpus = " ".join(paths.values()).casefold()
        lines = _description_lines(request.description)
        requirements: list[JobRequirement] = []
        for line in lines:
            evidence = _evidence_for(line, paths)
            tokens = _tokens(line)
            token_hits = sum(token in corpus for token in tokens)
            matched = bool(evidence) and token_hits >= max(1, min(2, len(tokens)))
            kind = _classify_requirement(line)
            requirements.append(JobRequirement(
                kind=kind,
                text=line,
                matched=matched,
                evidence_paths=evidence,
                gap_reason=None if matched else ("简历中没有找到可引用证据" if kind == "hard" else "尚未形成直接关键词证据"),
            ))
        if not requirements:
            requirements.append(JobRequirement(
                kind="keyword", text=request.description[:800], matched=False,
                gap_reason="职位描述无法拆分，请补充完整 JD",
            ))

        weighted_total = sum(3 if item.kind == "hard" else 2 if item.kind in {"preferred", "responsibility"} else 1 for item in requirements)
        weighted_hit = sum((3 if item.kind == "hard" else 2 if item.kind in {"preferred", "responsibility"} else 1) for item in requirements if item.matched)
        title_tokens = _tokens(request.title)
        title_hits = sum(token in corpus for token in title_tokens)
        score = round(20 + 65 * weighted_hit / max(1, weighted_total) + 15 * title_hits / max(1, len(title_tokens)))
        score = max(0, min(100, score))
        hard_gaps = [item.text for item in requirements if item.kind == "hard" and not item.matched]
        jd_tokens = _tokens(" ".join([request.title, request.description]))
        matched_keywords = [token for token in jd_tokens if token in corpus][:20]
        missing_keywords = [token for token in jd_tokens if token not in corpus][:20]
        risk = _risk_check(RecruitmentRiskRequest(
            company=request.company, title=request.title, description=request.description, url=request.url or ""
        ))
        if risk.risk_level in {"critical", "high"}:
            action = "block"
        elif hard_gaps:
            action = "verify" if score >= 45 else "deprioritize"
        else:
            action = "apply" if score >= 60 else "verify"
        return JobDossierResponse(
            company=request.company,
            title=request.title,
            match_score=score,
            requirements=requirements,
            hard_gaps=hard_gaps,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            resume_evidence=list(dict.fromkeys(path for item in requirements for path in item.evidence_paths))[:20],
            risk_signals=risk.signals,
            recommended_action=action,
            rationale=f"{sum(item.matched for item in requirements)}/{len(requirements)} 条要求找到简历证据；{len(hard_gaps)} 条硬性条件待核验。",
        )

    async def create_version(self, request: ResumeVersionCreateRequest, session: SessionState) -> ResumeVersion:
        original = session.resume.model_copy(deep=True)
        targeted = original.model_copy(deep=True)
        changes: list[ResumeVersionChange] = []
        jd = request.job_description.casefold()

        roles_before = list(targeted.target_roles)
        targeted.target_roles = [request.target_title, *[role for role in targeted.target_roles if role.casefold() != request.target_title.casefold()]]
        if roles_before != targeted.target_roles:
            changes.append(ResumeVersionChange(
                field_path="target_roles", before=" / ".join(roles_before), after=" / ".join(targeted.target_roles),
                reason="将本岗位放在目标方向首位，仅调整顺序。", evidence_paths=["target_roles"],
            ))

        skills_before = list(targeted.skills)
        targeted.skills = sorted(targeted.skills, key=lambda skill: (skill.casefold() not in jd, skills_before.index(skill)))
        if skills_before != targeted.skills:
            changes.append(ResumeVersionChange(
                field_path="skills", before=" / ".join(skills_before), after=" / ".join(targeted.skills),
                reason="把 JD 已出现的既有技能前置，未添加新技能。", evidence_paths=["skills"],
            ))

        experience_before = [item.company for item in targeted.work_experience]
        targeted.work_experience = sorted(
            targeted.work_experience,
            key=lambda item: -sum(token in json.dumps(item.model_dump(mode="json"), ensure_ascii=False).casefold() for token in _tokens(request.job_description)),
        )
        experience_after = [item.company for item in targeted.work_experience]
        if experience_before != experience_after:
            changes.append(ResumeVersionChange(
                field_path="work_experience", before=" / ".join(experience_before), after=" / ".join(experience_after),
                reason="按岗位关键词证据强度重排既有经历。", evidence_paths=["work_experience"],
            ))

        project_before = [item.name for item in targeted.projects]
        targeted.projects = sorted(
            targeted.projects,
            key=lambda item: -sum(token in json.dumps(item.model_dump(mode="json"), ensure_ascii=False).casefold() for token in _tokens(request.job_description)),
        )
        project_after = [item.name for item in targeted.projects]
        if project_before != project_after:
            changes.append(ResumeVersionChange(
                field_path="projects", before=" / ".join(project_before), after=" / ".join(project_after),
                reason="按岗位关键词证据强度重排既有项目。", evidence_paths=["projects"],
            ))

        version = ResumeVersion(
            id=f"rv_{uuid4().hex[:12]}", session_id=session.id,
            label=request.label or f"{request.target_company} · {request.target_title}",
            target_company=request.target_company, target_title=request.target_title,
            source_resume_hash=_resume_hash(original), resume=targeted, changes=changes, created_at=_now(),
        )
        async with self._lock:
            self.versions[version.id] = version
        return version.model_copy(deep=True)

    async def list_versions(self, session_id: str) -> list[ResumeVersion]:
        async with self._lock:
            return [item.model_copy(deep=True) for item in self.versions.values() if item.session_id == session_id]

    async def audit_version(self, version_id: str, session: SessionState) -> VersionAuditResponse:
        async with self._lock:
            version = self.versions.get(version_id)
        if version is None or version.session_id != session.id:
            raise KeyError(version_id)
        findings: list[VersionAuditFinding] = []
        if version.source_resume_hash != _resume_hash(session.resume):
            findings.append(VersionAuditFinding(
                severity="warning", code="master-changed",
                message="事实母版在该版本创建后发生变化，建议重新生成版本。", field_paths=["resume"],
            ))
        source_numbers = Counter(METRIC_PATTERN.findall(json.dumps(session.resume.model_dump(mode="json"), ensure_ascii=False)))
        version_numbers = Counter(METRIC_PATTERN.findall(json.dumps(version.resume.model_dump(mode="json"), ensure_ascii=False)))
        extra_numbers = list((version_numbers - source_numbers).elements())
        if extra_numbers:
            findings.append(VersionAuditFinding(
                severity="critical", code="invented-number",
                message=f"岗位版本出现母版不存在的数字：{', '.join(extra_numbers[:10])}", field_paths=["resume"],
            ))
        if any(change.fact_changed for change in version.changes):
            findings.append(VersionAuditFinding(
                severity="critical", code="fact-change", message="检测到事实字段被改写。", field_paths=[c.field_path for c in version.changes if c.fact_changed],
            ))
        if not findings:
            findings.append(VersionAuditFinding(
                severity="info", code="facts-stable", message="仅检测到顺序或取舍变化，没有新增事实与数字。",
            ))
        return VersionAuditResponse(version_id=version.id, passed=not any(item.severity == "critical" for item in findings), findings=findings)

    def rank_jobs(self, request: JobRankingRequest, session: SessionState) -> JobRankingResponse:
        today = date.today()
        seen: dict[tuple[str, str], str] = {}
        groups: dict[str, list[str]] = defaultdict(list)
        ranked: list[RankedJob] = []
        for index, job in enumerate(request.jobs):
            job_id = job.id or f"job_{index + 1}"
            key = (_compact(job.company), _compact(job.title))
            duplicate_of = seen.get(key)
            if duplicate_of:
                groups[duplicate_of].append(job_id)
            else:
                seen[key] = job_id
                groups[job_id].append(job_id)
            invalid = []
            if job.deadline and job.deadline < today:
                invalid.append("岗位已超过截止日期")
            if job.url and not urlparse(job.url).hostname:
                invalid.append("投递链接无法解析")
            if job.source.casefold() not in {"official", "official_career", "企业官网", "官方"}:
                invalid.append("渠道不是已核验企业官网")
            dossier = self.job_dossier(JobDossierRequest(
                session_id=session.id, company=job.company, title=job.title,
                description=job.description or f"{job.title} 岗位信息待补充",
                location=job.location, url=job.url or None, salary=job.salary, deadline=job.deadline,
            ), session)
            base_score = 100 if not job.location or any(base.casefold() in job.location.casefold() for base in session.resume.base_locations or session.preferred_locations) else 40
            if job.deadline:
                days = (job.deadline - today).days
                urgency = 100 if 0 <= days <= 3 else 80 if days <= 7 else 55
            else:
                urgency = 45
            channel = 95 if job.source.casefold() in {"official", "official_career", "企业官网", "官方"} and job.url.startswith("https://") else 60
            effort = max(20, 100 - job.application_minutes // 2)
            score = round(dossier.match_score * .45 + base_score * .18 + urgency * .15 + channel * .15 + effort * .07)
            if invalid or duplicate_of:
                score = max(0, score - 35 - 20 * bool(duplicate_of))
            ranked.append(RankedJob(
                job=job.model_copy(update={"id": job_id}), score=score, match_score=dossier.match_score,
                base_score=base_score, urgency_score=urgency, channel_score=channel,
                reasons=[dossier.rationale, f"Base {base_score}", f"截止紧迫度 {urgency}", f"渠道可信度 {channel}"],
                duplicate_of=duplicate_of, invalid_reasons=invalid,
            ))
        ranked.sort(key=lambda item: item.score, reverse=True)
        duplicate_groups = [ids for ids in groups.values() if len(ids) > 1]
        recommended = [item.job.id for item in ranked if not item.invalid_reasons and not item.duplicate_of][:10]
        return JobRankingResponse(ranked_jobs=ranked, duplicate_groups=duplicate_groups, recommended_today=recommended)

    async def create_application(self, request: ApplicationCreateRequest) -> ApplicationRecord:
        now = _now()
        record = ApplicationRecord(
            id=f"app_{uuid4().hex[:12]}", created_at=now, updated_at=now,
            history=[ApplicationHistoryEvent(at=now, to_status=request.status, note=request.note)],
            **request.model_dump(exclude={"note"}),
        )
        async with self._lock:
            self.applications[record.id] = record
        return record.model_copy(deep=True)

    async def list_applications(self, session_id: str) -> list[ApplicationRecord]:
        async with self._lock:
            items = [item.model_copy(deep=True) for item in self.applications.values() if item.session_id == session_id]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    async def update_application(self, application_id: str, request: ApplicationUpdateRequest, session_id: str) -> ApplicationRecord:
        async with self._lock:
            record = self.applications.get(application_id)
            if record is None or record.session_id != session_id:
                raise KeyError(application_id)
            previous = record.status
            record.status = request.status
            record.next_action_at = request.next_action_at
            if request.receipt_reference:
                record.receipt_reference = request.receipt_reference
            record.updated_at = _now()
            record.history.append(ApplicationHistoryEvent(
                at=record.updated_at, from_status=previous, to_status=request.status, note=request.note,
            ))
            return record.model_copy(deep=True)

    async def reminders(self, session_id: str) -> list[Reminder]:
        applications = await self.list_applications(session_id)
        now = _now()
        output: list[Reminder] = []
        for app in applications:
            if app.deadline and app.status in {"saved", "preparing", "ready"}:
                due = datetime.combine(app.deadline, datetime.max.time(), tzinfo=timezone.utc)
                output.append(Reminder(id=f"deadline-{app.id}", application_id=app.id, due_at=due, kind="deadline", title=f"{app.company} · {app.title} 投递截止", overdue=due < now))
            if app.next_action_at:
                kind = "interview" if app.status == "interview" else "assessment" if app.status == "assessment" else "follow_up"
                output.append(Reminder(id=f"next-{app.id}", application_id=app.id, due_at=app.next_action_at, kind=kind, title=f"{app.company} · {app.title} 下一步", overdue=app.next_action_at < now))
        return sorted(output, key=lambda item: item.due_at)

    def portal_adapters(self) -> list[PortalAdapter]:
        return [item.model_copy(deep=True) for item in PORTAL_ADAPTERS]

    def portal_preflight(self, request: PortalPreflightRequest, session: SessionState) -> PortalPreflightResponse:
        host = (urlparse(request.url).hostname or "").casefold()
        adapter = next((item for item in PORTAL_ADAPTERS[:-1] if any(pattern in host for pattern in item.host_patterns)), PORTAL_ADAPTERS[-1])
        fields = {field.casefold() for field in request.detected_fields}
        basic = {"name": session.resume.full_name, "email": session.resume.email, "phone": session.resume.phone}
        missing = [name for name, value in basic.items() if name in fields and not value]
        blocked = sorted(field for field in request.detected_fields if field.casefold() in {item.casefold() for item in SENSITIVE_FIELDS})
        attachment_checks = []
        if any(name in fields for name in {"resume", "简历", "attachment", "附件"}) and not request.available_attachments:
            attachment_checks.append("页面要求附件，但尚未确认可上传的岗位简历文件")
        checklist = [
            "已核对公司、岗位、Base 与当前官网域名",
            "已选择正确的一岗一简历版本",
            "已检查必填字段、附件和事实一致性",
            "验证码、人机验证与敏感字段由用户本人处理",
            "最终提交前必须再次显示页面摘要并逐岗位确认",
        ]
        ready = bool(host) and not missing and not attachment_checks and not blocked
        can_submit = ready and request.user_confirmed
        return PortalPreflightResponse(
            adapter=adapter, ready=ready, missing_required_fields=missing,
            blocked_sensitive_fields=blocked, attachment_checks=attachment_checks,
            checklist=checklist, can_submit=can_submit,
            notice="预检只授予当前岗位页面的下一步权限，不代表已经提交；成功必须以官网回执为准。",
        )

    async def save_checkpoint(self, request: RecoveryCheckpointCreate) -> RecoveryCheckpoint:
        now = _now()
        checkpoint = RecoveryCheckpoint(
            id=f"cp_{uuid4().hex[:12]}", created_at=now, expires_at=now + timedelta(hours=24),
            **request.model_dump(),
        )
        async with self._lock:
            self.checkpoints[checkpoint.id] = checkpoint
        return checkpoint.model_copy(deep=True)

    async def latest_checkpoint(self, application_id: str, session_id: str) -> RecoveryCheckpoint | None:
        async with self._lock:
            items = [item for item in self.checkpoints.values() if item.application_id == application_id and item.session_id == session_id and item.expires_at > _now()]
        return max(items, key=lambda item: item.created_at).model_copy(deep=True) if items else None

    def interview_kit(self, request: InterviewKitRequest, session: SessionState) -> InterviewKitResponse:
        paths = _resume_paths(session.resume)
        dossier = self.job_dossier(JobDossierRequest(
            session_id=session.id, company=request.company, title=request.title, description=request.job_description,
        ), session)
        evidence_paths = dossier.resume_evidence[:8]
        questions = []
        for path in evidence_paths[:5]:
            questions.append(InterviewQuestion(
                question=f"请具体说明你在“{paths[path][:80]}”中承担的任务、行动和结果。",
                why_asked="核验简历证据是否真实且能对应岗位职责。",
                evidence_paths=[path],
                answer_framework="背景/目标 → 你的具体行动 → 可核实结果 → 与目标岗位的联系",
            ))
        for gap in dossier.hard_gaps[:3]:
            questions.append(InterviewQuestion(
                question=f"岗位要求“{gap[:120]}”，你目前有哪些真实准备或可迁移经验？",
                why_asked="确认硬性条件是否真的满足，避免用空泛表述掩盖差距。",
                evidence_paths=[], answer_framework="如实说明现状 → 已完成的准备 → 学习或补齐计划",
            ))
        intro = [
            f"职业定位：{session.resume.professional_headline or request.title}",
            f"目标联系：说明为何申请 {request.company} 的 {request.title}",
            f"核心证据：从 {', '.join(evidence_paths[:3]) or '事实母版'} 选择 1–2 个真实例子",
            "结尾：说明能解决的岗位问题，不重复朗读整份简历",
        ]
        return InterviewKitResponse(
            company=request.company, title=request.title, self_intro_outline=intro,
            resume_questions=questions[:8],
            star_prompts=["当时的业务或项目背景是什么？", "目标和约束是什么？", "哪些动作由你本人完成？", "结果如何核验？", "如果重做会改变什么？"],
            questions_to_ask=["该岗位前三个月最重要的交付是什么？", "团队如何评价这个岗位的优秀表现？", "当前岗位面临的最大业务挑战是什么？"],
            risk_warnings=[f"不要声称满足尚未证实的硬性条件：{item}" for item in dossier.hard_gaps[:4]],
        )

    def simulate_interview(self, request: InterviewSimulationRequest, session: SessionState) -> InterviewSimulationResponse:
        answer = request.answer.strip()
        structure = 85 if any(word in answer for word in ("背景", "目标", "负责", "结果", "最后")) and len(answer) >= 100 else 65 if len(answer) >= 60 else 40
        resume_json = json.dumps(session.resume.model_dump(mode="json"), ensure_ascii=False)
        answer_numbers = set(METRIC_PATTERN.findall(answer))
        resume_numbers = set(METRIC_PATTERN.findall(resume_json))
        unsupported = sorted(answer_numbers - resume_numbers)
        evidence = 90 if answer_numbers and not unsupported else 65 if any(word in answer for word in ("完成", "交付", "发现", "整理", "协调")) else 40
        consistency = max(20, 100 - len(unsupported) * 25)
        improvements = []
        if structure < 70:
            improvements.append("按背景、目标、个人行动、结果四段组织回答。")
        if evidence < 70:
            improvements.append("引用事实母版中的真实任务、范围或交付物。")
        if unsupported:
            improvements.append(f"回答出现简历未记录的数字：{', '.join(unsupported)}；请核实后再使用。")
        strengths = []
        if structure >= 70:
            strengths.append("回答具有基本叙事结构。")
        if evidence >= 70:
            strengths.append("回答包含行动或结果证据。")
        overall = round(structure * .35 + evidence * .35 + consistency * .30)
        return InterviewSimulationResponse(
            overall_score=overall, structure_score=structure, evidence_score=evidence,
            consistency_score=consistency, strengths=strengths, improvements=improvements,
            follow_up_question="其中哪一步是你本人独立完成的？请给出可以核验的交付物或结果。",
        )

    async def funnel(self, session_id: str) -> FunnelAnalytics:
        apps = await self.list_applications(session_id)
        order = ["saved", "preparing", "ready", "applied", "assessment", "interview", "offer", "rejected", "withdrawn"]
        counts = Counter(item.status for item in apps)
        stages = []
        previous = None
        for status in order:
            count = counts[status]
            conversion = round(count / previous * 100, 1) if previous else None
            stages.append(FunnelStage(status=status, count=count, conversion_from_previous=conversion))
            if count:
                previous = count
        total = len(apps)
        applied = sum(counts[s] for s in ("applied", "assessment", "interview", "offer", "rejected"))
        responses = sum(counts[s] for s in ("assessment", "interview", "offer", "rejected"))
        interviews = counts["interview"] + counts["offer"]
        offers = counts["offer"]
        recommendations = []
        if applied >= 5 and responses / applied < .2:
            recommendations.append("响应率偏低：优先复查目标岗位筛选和一岗一简历证据匹配。")
        if responses >= 3 and interviews / responses < .3:
            recommendations.append("测评/沟通到面试转化偏低：加强职位硬条件与项目证据准备。")
        if interviews >= 3 and offers == 0:
            recommendations.append("已有多次面试但暂无 Offer：复盘追问一致性、案例深度和岗位动机。")
        if not recommendations:
            recommendations.append("样本仍少或转化正常，继续记录每次岗位版本与官方回执。")
        return FunnelAnalytics(
            total=total, stages=stages,
            response_rate=round(responses / applied * 100, 1) if applied else 0,
            interview_rate=round(interviews / applied * 100, 1) if applied else 0,
            offer_rate=round(offers / applied * 100, 1) if applied else 0,
            recommendations=recommendations,
        )

    def recruitment_risk(self, request: RecruitmentRiskRequest) -> RecruitmentRiskResponse:
        return _risk_check(request)

    async def add_evidence(self, request: EvidenceItemCreate) -> EvidenceItem:
        item = EvidenceItem(id=f"ev_{uuid4().hex[:12]}", created_at=_now(), **request.model_dump())
        async with self._lock:
            self.evidence_items[item.id] = item
        return item.model_copy(deep=True)

    async def list_evidence(self, session_id: str) -> list[EvidenceItem]:
        async with self._lock:
            return [item.model_copy(deep=True) for item in self.evidence_items.values() if item.session_id == session_id]

    async def put_vault(self, request: VaultPutRequest) -> VaultMetadata:
        async with self._lock:
            container = self.vault_tokens.setdefault(request.session_id, {})
            for name, value in request.values.items():
                container[name] = self._fernet.encrypt(value.encode("utf-8"))
            fields = sorted(container)
        return VaultMetadata(session_id=request.session_id, fields=fields, encrypted_items=len(fields))

    async def vault_metadata(self, session_id: str) -> VaultMetadata:
        async with self._lock:
            fields = sorted(self.vault_tokens.get(session_id, {}))
        return VaultMetadata(session_id=session_id, fields=fields, encrypted_items=len(fields))

    async def create_vault_lease(self, request: VaultLeaseRequest) -> VaultLeaseResponse:
        if not request.user_confirmed:
            raise PermissionError("vault lease requires explicit user confirmation")
        host = urlparse(request.target_url).hostname or ""
        if not host or request.target_url.startswith("http://"):
            raise PermissionError("vault lease requires a valid HTTPS target")
        async with self._lock:
            container = self.vault_tokens.get(request.session_id, {})
            missing = [name for name in request.fields if name not in container]
            if missing:
                raise KeyError(",".join(missing))
            lease_id = f"lease_{uuid4().hex[:12]}"
            expires = _now() + timedelta(seconds=90)
            self.vault_leases[lease_id] = (request.session_id, request.fields, expires)
        return VaultLeaseResponse(
            lease_id=lease_id, target_host=host, fields=request.fields, expires_at=expires,
            notice="租约只授权服务器端浏览器适配器在指定 HTTPS 域名使用这些字段；API 不返回明文。",
        )
