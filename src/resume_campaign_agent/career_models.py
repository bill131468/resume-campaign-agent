from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import ResumeProfile


RequirementKind = Literal["hard", "preferred", "responsibility", "keyword"]
ApplicationStatus = Literal[
    "saved", "preparing", "ready", "applied", "assessment", "interview",
    "offer", "rejected", "withdrawn",
]


class JobRequirement(BaseModel):
    kind: RequirementKind
    text: str = Field(min_length=1, max_length=800)
    matched: bool
    evidence_paths: list[str] = Field(default_factory=list, max_length=12)
    gap_reason: str | None = Field(default=None, max_length=500)


class JobDossierRequest(BaseModel):
    session_id: str
    company: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=10, max_length=12000)
    location: str | None = Field(default=None, max_length=160)
    url: str | None = Field(default=None, max_length=2000)
    salary: str | None = Field(default=None, max_length=160)
    deadline: date | None = None


class RecruitmentRiskSignal(BaseModel):
    code: str
    severity: Literal["low", "medium", "high", "critical"]
    title: str
    evidence: str
    action: str


class JobDossierResponse(BaseModel):
    company: str
    title: str
    match_score: int = Field(ge=0, le=100)
    requirements: list[JobRequirement]
    hard_gaps: list[str]
    matched_keywords: list[str]
    missing_keywords: list[str]
    resume_evidence: list[str]
    risk_signals: list[RecruitmentRiskSignal]
    recommended_action: Literal["apply", "verify", "deprioritize", "block"]
    rationale: str
    direct_identifiers_shared_with_model: Literal[False] = False


class ResumeVersionChange(BaseModel):
    field_path: str
    before: str
    after: str
    reason: str
    evidence_paths: list[str] = Field(default_factory=list)
    fact_changed: Literal[False] = False


class ResumeVersionCreateRequest(BaseModel):
    session_id: str
    label: str | None = Field(default=None, max_length=160)
    target_company: str = Field(min_length=1, max_length=160)
    target_title: str = Field(min_length=1, max_length=160)
    job_description: str = Field(min_length=10, max_length=12000)


class ResumeVersion(BaseModel):
    id: str
    session_id: str
    label: str
    target_company: str
    target_title: str
    source_resume_hash: str
    resume: ResumeProfile
    changes: list[ResumeVersionChange]
    created_at: datetime
    status: Literal["draft", "approved"] = "draft"
    source_resume_mutated: Literal[False] = False


class VersionAuditFinding(BaseModel):
    severity: Literal["info", "warning", "critical"]
    code: str
    message: str
    field_paths: list[str] = Field(default_factory=list)


class VersionAuditResponse(BaseModel):
    version_id: str
    passed: bool
    findings: list[VersionAuditFinding]
    source_resume_mutated: Literal[False] = False


class CandidateJob(BaseModel):
    id: str | None = None
    company: str
    title: str
    description: str = ""
    location: str = ""
    url: str = ""
    salary: str | None = None
    deadline: date | None = None
    source: str = "official"
    application_minutes: int = Field(default=20, ge=1, le=600)


class JobRankingRequest(BaseModel):
    session_id: str
    jobs: list[CandidateJob] = Field(min_length=1, max_length=100)


class RankedJob(BaseModel):
    job: CandidateJob
    score: int = Field(ge=0, le=100)
    match_score: int = Field(ge=0, le=100)
    base_score: int = Field(ge=0, le=100)
    urgency_score: int = Field(ge=0, le=100)
    channel_score: int = Field(ge=0, le=100)
    reasons: list[str]
    duplicate_of: str | None = None
    invalid_reasons: list[str] = Field(default_factory=list)


class JobRankingResponse(BaseModel):
    ranked_jobs: list[RankedJob]
    duplicate_groups: list[list[str]]
    recommended_today: list[str]


class ApplicationHistoryEvent(BaseModel):
    at: datetime
    from_status: ApplicationStatus | None = None
    to_status: ApplicationStatus
    note: str = ""


class ApplicationCreateRequest(BaseModel):
    session_id: str
    company: str
    title: str
    url: str = ""
    location: str = ""
    status: ApplicationStatus = "saved"
    resume_version_id: str | None = None
    job_description: str = ""
    deadline: date | None = None
    next_action_at: datetime | None = None
    note: str = ""


class ApplicationUpdateRequest(BaseModel):
    status: ApplicationStatus
    note: str = ""
    next_action_at: datetime | None = None
    receipt_reference: str | None = Field(default=None, max_length=500)


class ApplicationRecord(BaseModel):
    id: str
    session_id: str
    company: str
    title: str
    url: str
    location: str
    status: ApplicationStatus
    resume_version_id: str | None
    job_description: str
    deadline: date | None
    next_action_at: datetime | None
    receipt_reference: str | None = None
    created_at: datetime
    updated_at: datetime
    history: list[ApplicationHistoryEvent]


class Reminder(BaseModel):
    id: str
    application_id: str
    due_at: datetime
    kind: Literal["deadline", "follow_up", "assessment", "interview"]
    title: str
    overdue: bool


class PortalAdapter(BaseModel):
    id: str
    name: str
    host_patterns: list[str]
    capabilities: list[str]
    human_steps: list[str]


class PortalPreflightRequest(BaseModel):
    session_id: str
    application_id: str | None = None
    url: str
    detected_fields: list[str] = Field(default_factory=list, max_length=200)
    available_attachments: list[str] = Field(default_factory=list, max_length=30)
    user_confirmed: bool = False


class PortalPreflightResponse(BaseModel):
    adapter: PortalAdapter
    ready: bool
    missing_required_fields: list[str]
    blocked_sensitive_fields: list[str]
    attachment_checks: list[str]
    checklist: list[str]
    user_confirmation_required: Literal[True] = True
    can_submit: bool
    notice: str


class RecoveryCheckpointCreate(BaseModel):
    session_id: str
    application_id: str
    url: str
    completed_fields: list[str] = Field(default_factory=list, max_length=200)
    pending_fields: list[str] = Field(default_factory=list, max_length=200)
    step: str = Field(default="form", max_length=160)


class RecoveryCheckpoint(BaseModel):
    id: str
    session_id: str
    application_id: str
    url: str
    completed_fields: list[str]
    pending_fields: list[str]
    step: str
    created_at: datetime
    expires_at: datetime


class InterviewKitRequest(BaseModel):
    session_id: str
    company: str
    title: str
    job_description: str = Field(min_length=10, max_length=12000)


class InterviewQuestion(BaseModel):
    question: str
    why_asked: str
    evidence_paths: list[str]
    answer_framework: str


class InterviewKitResponse(BaseModel):
    company: str
    title: str
    self_intro_outline: list[str]
    resume_questions: list[InterviewQuestion]
    star_prompts: list[str]
    questions_to_ask: list[str]
    risk_warnings: list[str]
    invented_facts: Literal[False] = False


class InterviewSimulationRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=2, max_length=1000)
    answer: str = Field(min_length=2, max_length=8000)


class InterviewSimulationResponse(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    structure_score: int = Field(ge=0, le=100)
    evidence_score: int = Field(ge=0, le=100)
    consistency_score: int = Field(ge=0, le=100)
    strengths: list[str]
    improvements: list[str]
    follow_up_question: str


class FunnelStage(BaseModel):
    status: ApplicationStatus
    count: int
    conversion_from_previous: float | None = None


class FunnelAnalytics(BaseModel):
    total: int
    stages: list[FunnelStage]
    response_rate: float
    interview_rate: float
    offer_rate: float
    recommendations: list[str]


class RecruitmentRiskRequest(BaseModel):
    company: str
    title: str
    description: str = ""
    url: str = ""
    contact_message: str = ""


class RecruitmentRiskResponse(BaseModel):
    risk_level: Literal["low", "medium", "high", "critical"]
    score: int = Field(ge=0, le=100)
    signals: list[RecruitmentRiskSignal]
    recommended_action: str


class EvidenceItemCreate(BaseModel):
    session_id: str
    category: Literal["education", "certificate", "project", "work", "award", "portfolio", "other"]
    label: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(default="", max_length=1000)
    checksum: str | None = Field(default=None, max_length=128)
    facts: list[str] = Field(default_factory=list, max_length=50)
    verified_by_user: bool = False


class EvidenceItem(BaseModel):
    id: str
    session_id: str
    category: str
    label: str
    source_reference: str
    checksum: str | None
    facts: list[str]
    verified_by_user: bool
    created_at: datetime


class VaultPutRequest(BaseModel):
    session_id: str
    values: dict[str, str] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_fields(self):
        allowed = {
            "identity_number", "home_address", "household_location", "emergency_contact",
            "emergency_phone", "student_id", "birth_date", "family_information",
        }
        unknown = set(self.values) - allowed
        if unknown:
            raise ValueError(f"unsupported vault fields: {', '.join(sorted(unknown))}")
        if any(not value.strip() for value in self.values.values()):
            raise ValueError("vault values cannot be empty")
        return self


class VaultMetadata(BaseModel):
    session_id: str
    fields: list[str]
    encrypted_items: int
    ephemeral_key: Literal[True] = True
    plaintext_returned: Literal[False] = False


class VaultLeaseRequest(BaseModel):
    session_id: str
    fields: list[str] = Field(min_length=1, max_length=20)
    target_url: str
    user_confirmed: bool


class VaultLeaseResponse(BaseModel):
    lease_id: str
    target_host: str
    fields: list[str]
    expires_at: datetime
    plaintext_returned: Literal[False] = False
    notice: str
