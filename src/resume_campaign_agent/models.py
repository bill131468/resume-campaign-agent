from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator


class Education(BaseModel):
    school: str = Field(min_length=2, max_length=120)
    degree: str = Field(min_length=2, max_length=80)
    major: str = Field(min_length=2, max_length=100)
    graduation_year: int = Field(ge=1950, le=2100)
    college: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    education_type: str | None = Field(default=None, max_length=80)
    minor: str | None = Field(default=None, max_length=100)
    gpa: float | None = Field(default=None, ge=0, le=100)
    gpa_scale: float | None = Field(default=None, gt=0, le=100)
    rank: str | None = Field(default=None, max_length=60)
    student_id: str | None = Field(default=None, max_length=60)
    core_courses: list[str] = Field(default_factory=list, max_length=20)
    thesis: str | None = Field(default=None, max_length=300)


class WorkExperience(BaseModel):
    company: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=120)
    start_date: date
    end_date: date | None = None
    highlights: list[str] = Field(default_factory=list, max_length=8)
    experience_type: str = Field(default="full_time", max_length=40)
    department: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    responsibilities: str | None = Field(default=None, max_length=1000)
    leaving_reason: str | None = Field(default=None, max_length=300)


class ProjectExperience(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    role: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    description: str = Field(min_length=10, max_length=1500)
    highlights: list[str] = Field(default_factory=list, max_length=8)
    skills: list[str] = Field(default_factory=list, max_length=20)
    url: HttpUrl | None = None


class CampusExperience(BaseModel):
    organization: str = Field(min_length=2, max_length=160)
    role: str = Field(min_length=2, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    description: str = Field(min_length=10, max_length=1000)


class CertificateRecord(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    issuer: str | None = Field(default=None, max_length=160)
    obtained_at: date | None = None
    score: str | None = Field(default=None, max_length=80)
    credential_id: str | None = Field(default=None, max_length=100)


class AwardRecord(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    issuer: str | None = Field(default=None, max_length=160)
    awarded_at: date | None = None
    description: str | None = Field(default=None, max_length=500)


class LanguageRecord(BaseModel):
    language: str = Field(min_length=1, max_length=80)
    proficiency: str = Field(min_length=1, max_length=80)
    test_name: str | None = Field(default=None, max_length=80)
    score: str | None = Field(default=None, max_length=80)


class ResumeProfile(BaseModel):
    full_name: str | None = Field(default=None, max_length=80)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    city: str | None = Field(default=None, max_length=100)
    target_roles: list[str] = Field(default_factory=list, max_length=8)
    years_experience: float = Field(default=0, ge=0, le=60)
    skills: list[str] = Field(default_factory=list, max_length=30)
    summary: str | None = Field(default=None, max_length=1200)
    education: list[Education] = Field(default_factory=list, max_length=5)
    work_experience: list[WorkExperience] = Field(default_factory=list, max_length=12)
    portfolio_url: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    languages: list[str] = Field(default_factory=list, max_length=12)
    preferred_name: str | None = Field(default=None, max_length=80)
    wechat: str | None = Field(default=None, max_length=80)
    professional_headline: str | None = Field(default=None, max_length=160)
    job_seeking_status: str | None = Field(default=None, max_length=80)
    target_industries: list[str] = Field(default_factory=list, max_length=12)
    target_employer_types: list[str] = Field(default_factory=list, max_length=12)
    employment_types: list[str] = Field(default_factory=list, max_length=8)
    base_locations: list[str] = Field(default_factory=list, max_length=12)
    available_date: date | None = None
    expected_salary: str | None = Field(default=None, max_length=100)
    relocation_preference: str | None = Field(default=None, max_length=100)
    work_authorization: str | None = Field(default=None, max_length=160)
    projects: list[ProjectExperience] = Field(default_factory=list, max_length=12)
    campus_experience: list[CampusExperience] = Field(default_factory=list, max_length=12)
    certificates: list[CertificateRecord] = Field(default_factory=list, max_length=20)
    awards: list[AwardRecord] = Field(default_factory=list, max_length=20)
    language_details: list[LanguageRecord] = Field(default_factory=list, max_length=12)
    volunteer_experience: list[CampusExperience] = Field(default_factory=list, max_length=12)
    publications: list[str] = Field(default_factory=list, max_length=20)
    patents: list[str] = Field(default_factory=list, max_length=20)
    professional_memberships: list[str] = Field(default_factory=list, max_length=20)
    hobbies: list[str] = Field(default_factory=list, max_length=20)
    self_evaluation: str | None = Field(default=None, max_length=1200)
    additional_information: str | None = Field(default=None, max_length=1200)

    @field_validator(
        "target_roles",
        "skills",
        "languages",
        "target_industries",
        "target_employer_types",
        "employment_types",
        "base_locations",
        "publications",
        "patents",
        "professional_memberships",
        "hobbies",
    )
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for raw in values:
            value = raw.strip()
            if value and value.casefold() not in seen:
                seen.add(value.casefold())
                unique.append(value)
        return unique


class ResumePatch(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    city: str | None = None
    target_roles: list[str] | None = None
    years_experience: float | None = Field(default=None, ge=0, le=60)
    skills: list[str] | None = None
    summary: str | None = None
    education: list[Education] | None = None
    work_experience: list[WorkExperience] | None = None
    portfolio_url: HttpUrl | None = None
    linkedin_url: HttpUrl | None = None
    languages: list[str] | None = None
    preferred_name: str | None = None
    wechat: str | None = None
    professional_headline: str | None = None
    job_seeking_status: str | None = None
    target_industries: list[str] | None = None
    target_employer_types: list[str] | None = None
    employment_types: list[str] | None = None
    base_locations: list[str] | None = None
    available_date: date | None = None
    expected_salary: str | None = None
    relocation_preference: str | None = None
    work_authorization: str | None = None
    projects: list[ProjectExperience] | None = None
    campus_experience: list[CampusExperience] | None = None
    certificates: list[CertificateRecord] | None = None
    awards: list[AwardRecord] | None = None
    language_details: list[LanguageRecord] | None = None
    volunteer_experience: list[CampusExperience] | None = None
    publications: list[str] | None = None
    patents: list[str] | None = None
    professional_memberships: list[str] | None = None
    hobbies: list[str] | None = None
    self_evaluation: str | None = None
    additional_information: str | None = None


class ResumeReviewRequest(BaseModel):
    session_id: str = Field(min_length=4, max_length=200)
    target_role: str | None = Field(default=None, max_length=160)
    target_job_description: str | None = Field(default=None, max_length=8000)
    use_ai: bool = True


class ResumeReviewDimension(BaseModel):
    key: Literal[
        "completeness", "relevance", "evidence", "credibility", "clarity", "readability"
    ]
    label: str
    score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=2, max_length=500)


class ResumeReviewFinding(BaseModel):
    id: str = Field(min_length=3, max_length=120)
    field_path: str = Field(min_length=1, max_length=200)
    severity: Literal["critical", "warning", "suggestion"]
    title: str = Field(min_length=2, max_length=160)
    observation: str = Field(min_length=2, max_length=800)
    recommendation: str = Field(min_length=2, max_length=800)
    question_to_user: str | None = Field(default=None, max_length=500)


class ResumeReviewResponse(BaseModel):
    session_id: str
    overall_score: int = Field(ge=0, le=100)
    grade: Literal["A", "B", "C", "D"]
    target_role: str | None = None
    dimensions: list[ResumeReviewDimension] = Field(min_length=6, max_length=6)
    findings: list[ResumeReviewFinding] = Field(default_factory=list, max_length=30)
    strengths: list[str] = Field(default_factory=list, max_length=12)
    evidence_questions: list[str] = Field(default_factory=list, max_length=12)
    ai_used: bool = False
    direct_identifiers_shared_with_model: Literal[False] = False
    source_resume_mutated: Literal[False] = False
    notice: str


class ResumeOptimizationRequest(BaseModel):
    session_id: str = Field(min_length=4, max_length=200)
    target_role: str | None = Field(default=None, max_length=160)
    target_job_description: str | None = Field(default=None, max_length=8000)
    max_suggestions: int = Field(default=10, ge=1, le=20)
    use_ai: bool = True


class ResumeOptimizationSuggestion(BaseModel):
    id: str = Field(min_length=3, max_length=120)
    field_path: str = Field(min_length=1, max_length=200)
    change_type: Literal["clarify", "compress", "structure", "target", "grammar", "evidence_prompt"]
    original_text: str = Field(default="", max_length=3000)
    suggested_text: str = Field(min_length=2, max_length=3000)
    rationale: str = Field(min_length=2, max_length=600)
    evidence_basis: list[str] = Field(default_factory=list, max_length=12)
    requires_user_confirmation: Literal[True] = True
    invented_facts: Literal[False] = False


class ResumeOptimizationResponse(BaseModel):
    session_id: str
    target_role: str | None = None
    suggestions: list[ResumeOptimizationSuggestion] = Field(default_factory=list, max_length=20)
    priority_order: list[str] = Field(default_factory=list, max_length=20)
    ai_used: bool = False
    direct_identifiers_shared_with_model: Literal[False] = False
    source_resume_mutated: Literal[False] = False
    notice: str


class MissingField(BaseModel):
    field: str
    label: str
    reason: str
    prompt: str


class JobSearchQuery(BaseModel):
    direction: str = Field(min_length=2, max_length=120)
    preferred_locations: list[str] = Field(default_factory=list, max_length=10)
    remote_preference: Literal["required", "preferred", "onsite", "any"] = "any"
    limit: int = Field(default=15, ge=1, le=50)


class JobPosting(BaseModel):
    id: str
    title: str
    company: str
    location: str
    remote: bool
    url: HttpUrl
    tags: list[str] = Field(default_factory=list)
    description_excerpt: str = ""
    posted_at: datetime | None = None
    source: str


class DestinationRecommendation(BaseModel):
    destination: str
    score: float = Field(ge=0, le=100)
    matched_jobs: int = Field(ge=0)
    rationale: str
    sample_companies: list[str] = Field(default_factory=list)


class ApplicationDraft(BaseModel):
    job_id: str
    job_title: str
    company: str
    destination: str
    job_url: HttpUrl
    resume_snapshot: ResumeProfile
    cover_note: str
    matched_skills: list[str]
    status: Literal["draft"] = "draft"
    send_enabled: Literal[False] = False


class CampaignPreview(BaseModel):
    session_id: str
    status: Literal["needs_input", "ready_for_review"]
    delivery_mode: Literal["dry_run"] = "dry_run"
    missing_fields: list[MissingField]
    jobs: list[JobPosting]
    recommended_destinations: list[DestinationRecommendation]
    application_drafts: list[ApplicationDraft]
    notice: str


class AgentReply(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    missing_fields: list[str] = Field(default_factory=list)
    updated_fields: list[str] = Field(default_factory=list)
    next_action: Literal["collect_resume", "search_jobs", "review_drafts", "done"]


class SessionState(BaseModel):
    id: str
    resume: ResumeProfile = Field(default_factory=ResumeProfile)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: Literal["required", "preferred", "onsite", "any"] = "any"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateSessionRequest(BaseModel):
    resume: ResumeProfile = Field(default_factory=ResumeProfile)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: Literal["required", "preferred", "onsite", "any"] = "any"


class PreviewRequest(BaseModel):
    session_id: str
    limit: int = Field(default=10, ge=1, le=25)


class AgentRunRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=4000)


class AgentRunResponse(BaseModel):
    session_id: str
    reply: AgentReply
    resume: ResumeProfile
    missing_fields: list[MissingField]
    model_used: str


class HealthResponse(BaseModel):
    ok: bool
    runtime: str
    agent_framework: str
    delivery_mode: Literal["dry_run"]
    llm_configured: bool
    model: str | None = None
    enterprise_search: str | None = None
    portal_templates: int = 0


class DispatchAttempt(BaseModel):
    session_id: str
    application_ids: list[str] = Field(default_factory=list)
    confirmation: bool = False


class BatchResumeCase(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    resume: ResumeProfile
    preferred_locations: list[str] = Field(default_factory=list, max_length=10)
    remote_preference: Literal["required", "preferred", "onsite", "any"] = "any"


class BatchPreviewRequest(BaseModel):
    cases: list[BatchResumeCase] = Field(min_length=1, max_length=10)
    limit_per_case: int = Field(default=8, ge=1, le=15)
    synthetic_fixture: Literal[True]


class EnterpriseIntent(BaseModel):
    company: str
    job_title: str
    destination: str
    job_url: HttpUrl
    matched_skills: list[str] = Field(default_factory=list)
    status: Literal["draft_ready"] = "draft_ready"
    send_enabled: Literal[False] = False


class BatchCandidateResult(BaseModel):
    label: str
    session_id: str
    status: Literal["needs_input", "ready_for_review"]
    missing_fields: list[MissingField]
    job_count: int = Field(ge=0)
    draft_count: int = Field(ge=0)
    recommended_destinations: list[DestinationRecommendation]
    intended_enterprises: list[EnterpriseIntent]


class BatchPreviewResponse(BaseModel):
    delivery_mode: Literal["dry_run"] = "dry_run"
    synthetic_fixture: Literal[True] = True
    results: list[BatchCandidateResult]
    total_jobs: int = Field(ge=0)
    total_drafts: int = Field(ge=0)
    all_send_disabled: Literal[True] = True
    notice: str


class PortalFieldRequirement(BaseModel):
    field: str
    label: str
    section: str
    required: bool
    sensitive: bool = False
    storage_policy: Literal["master_resume", "portal_only", "prepare_only"]
    notes: str = ""


class PortalTemplate(BaseModel):
    id: str
    name: str
    organization: str
    evidence_level: Literal["official", "official_plus_application_guide"]
    source_urls: list[HttpUrl]
    fields: list[PortalFieldRequirement]
    application_rules: list[str] = Field(default_factory=list)
    privacy_notice: str


class EnterpriseDiscoveryRequest(BaseModel):
    session_id: str
    base_locations: list[str] = Field(default_factory=list, max_length=12)
    professional_directions: list[str] = Field(default_factory=list, max_length=12)
    industries: list[str] = Field(default_factory=list, max_length=12)
    employer_types: list[str] = Field(default_factory=list, max_length=12)
    company_keywords: list[str] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=20, ge=1, le=40)
    ai_ranking: bool = True


class ApplicationChannel(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    url: HttpUrl
    channel_type: Literal[
        "official_career_home",
        "campus_portal",
        "social_portal",
        "internship_portal",
        "official_announcement",
        "designated_application_system",
        "official_wechat",
    ]
    official_evidence_url: HttpUrl | None = None
    availability: Literal["openings_live", "entry_hub", "seasonal_closed", "check_required"]
    login_required: bool = False
    supports_job_search: bool = True
    notes: str = Field(default="", max_length=500)
    verified_on: date | None = None


class EnterpriseLead(BaseModel):
    id: str
    company: str
    source_title: str
    source_url: HttpUrl
    bases: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    recommended_roles: list[str] = Field(default_factory=list)
    source_kind: Literal["official_catalog", "exa_web"]
    source_authority: Literal["official_known", "likely_official", "unverified"]
    score: float = Field(ge=0, le=100)
    rationale: str
    application_channels: list[ApplicationChannel] = Field(default_factory=list, max_length=8)
    application_readiness: Literal[
        "direct_official", "official_hub", "needs_channel_verification"
    ] = "needs_channel_verification"
    channel_notice: str = ""
    status: Literal["research_ready"] = "research_ready"
    send_enabled: Literal[False] = False


class EnterpriseDiscoveryResponse(BaseModel):
    session_id: str
    delivery_mode: Literal["dry_run"] = "dry_run"
    search_engine: str
    ai_ranking_used: bool
    query_plan: list[str]
    source_count: int = Field(ge=0)
    official_source_count: int = Field(ge=0)
    official_entry_count: int = Field(ge=0)
    live_or_hub_entry_count: int = Field(ge=0)
    enterprises: list[EnterpriseLead]
    warnings: list[str] = Field(default_factory=list)
    notice: str


class BrowserSessionSummary(BaseModel):
    id: str
    candidate_label: str
    target_roles: list[str] = Field(default_factory=list)
    base_locations: list[str] = Field(default_factory=list)
    updated_at: datetime


class BrowserFormOption(BaseModel):
    value: str = Field(default="", max_length=300)
    label: str = Field(default="", max_length=300)


class BrowserFormField(BaseModel):
    index: int = Field(ge=0, le=500)
    signature: str = Field(min_length=1, max_length=800)
    tag: Literal["input", "textarea", "select"]
    input_type: str = Field(default="text", max_length=40)
    name: str = Field(default="", max_length=200)
    element_id: str = Field(default="", max_length=200)
    label: str = Field(default="", max_length=500)
    placeholder: str = Field(default="", max_length=500)
    autocomplete: str = Field(default="", max_length=100)
    required: bool = False
    max_length: int | None = Field(default=None, ge=-1, le=100000)
    options: list[BrowserFormOption] = Field(default_factory=list, max_length=200)


class BrowserPageSnapshot(BaseModel):
    url: HttpUrl
    title: str = Field(default="", max_length=500)
    fields: list[BrowserFormField] = Field(default_factory=list, max_length=500)


class BrowserAnalyzeRequest(BaseModel):
    session_id: str
    page: BrowserPageSnapshot
    use_ai: bool = True


class BrowserJobCandidate(BaseModel):
    index: int = Field(ge=0, le=200)
    title: str = Field(min_length=2, max_length=500)
    url: HttpUrl
    metadata: str = Field(default="", max_length=1500)


class BrowserJobRankRequest(BaseModel):
    session_id: str
    page_url: HttpUrl
    candidates: list[BrowserJobCandidate] = Field(min_length=1, max_length=80)


class BrowserJobSelection(BaseModel):
    selected_index: int | None = Field(default=None, ge=0, le=200)
    selected_url: HttpUrl | None = None
    selected_title: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    rationale: str
    ai_used: bool = False
    rejected_indexes: list[int] = Field(default_factory=list, max_length=80)


class BrowserFillAction(BaseModel):
    field_index: int = Field(ge=0)
    field_signature: str
    resume_field: str
    value: str
    masked_preview: str
    confidence: float = Field(ge=0, le=1)
    rationale: str


class BrowserSkippedField(BaseModel):
    field_index: int = Field(ge=0)
    label: str
    reason: str
    safety_category: Literal[
        "protected", "unsupported", "missing_resume_value", "unmapped"
    ]


class BrowserFillPlan(BaseModel):
    session_id: str
    page_url: HttpUrl
    delivery_mode: Literal["dry_run"] = "dry_run"
    actions: list[BrowserFillAction]
    skipped: list[BrowserSkippedField]
    ai_mapping_used: bool = False
    submit_enabled: Literal[False] = False
    notice: str


class BrowserControlCommand(BaseModel):
    name: Literal[
        "scan_form",
        "analyze_fields",
        "highlight_targets",
        "fill_empty",
        "inspect_auth",
        "request_otp",
        "complete_auth",
        "inspect_journey",
        "select_live_job",
        "open_application",
        "submit_application",
    ]
    effect: Literal["read_only", "visual_only", "local_write", "external_auth", "external_submission"]
    requires_user_gesture: bool


class BrowserControlContract(BaseModel):
    mode: Literal["constrained_computer_use"] = "constrained_computer_use"
    commands: list[BrowserControlCommand]
    denied_capabilities: list[str]
    permission_strategy: Literal["active_tab_plus_optional_single_origin"] = (
        "active_tab_plus_optional_single_origin"
    )
    model_receives_resume_values: Literal[False] = False
    final_submit_enabled: bool = False
    notice: str


def public_model_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True)
