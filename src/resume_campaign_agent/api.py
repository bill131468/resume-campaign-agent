from __future__ import annotations

import platform
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import AgentDependencies, build_agent, compact_session_context
from .campaign import CampaignService, missing_resume_fields
from .browser_assistant import BrowserAssistant
from .career_copilot import CareerCopilotService
from .career_models import (
    ApplicationCreateRequest,
    ApplicationRecord,
    ApplicationUpdateRequest,
    EvidenceItem,
    EvidenceItemCreate,
    FunnelAnalytics,
    InterviewKitRequest,
    InterviewKitResponse,
    InterviewSimulationRequest,
    InterviewSimulationResponse,
    JobDossierRequest,
    JobDossierResponse,
    JobRankingRequest,
    JobRankingResponse,
    PortalAdapter,
    PortalPreflightRequest,
    PortalPreflightResponse,
    RecoveryCheckpoint,
    RecoveryCheckpointCreate,
    RecruitmentRiskRequest,
    RecruitmentRiskResponse,
    Reminder,
    ResumeVersion,
    ResumeVersionCreateRequest,
    VaultLeaseRequest,
    VaultLeaseResponse,
    VaultMetadata,
    VaultPutRequest,
    VersionAuditResponse,
)
from .config import Settings
from .discovery import EnterpriseDiscoveryService
from .jobs import ArbeitnowJobProvider, JobProviderError
from .models import (
    AgentRunRequest,
    AgentRunResponse,
    BatchCandidateResult,
    BatchPreviewRequest,
    BatchPreviewResponse,
    BrowserAnalyzeRequest,
    BrowserControlCommand,
    BrowserControlContract,
    BrowserFillPlan,
    BrowserJobRankRequest,
    BrowserJobSelection,
    BrowserSessionSummary,
    CampaignPreview,
    CreateSessionRequest,
    DispatchAttempt,
    EnterpriseIntent,
    EnterpriseDiscoveryRequest,
    EnterpriseDiscoveryResponse,
    HealthResponse,
    JobPosting,
    JobSearchQuery,
    PreviewRequest,
    PortalTemplate,
    ResumeOptimizationRequest,
    ResumeOptimizationResponse,
    ResumePatch,
    ResumeReviewRequest,
    ResumeReviewResponse,
    SessionState,
    public_model_dict,
)
from .store import InMemorySessionStore, SessionNotFoundError
from .portal_templates import get_portal_template, list_portal_templates
from .resume_review import ResumeReviewService


def create_app(
    *,
    settings: Settings | None = None,
    store: InMemorySessionStore | None = None,
    job_provider=None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or InMemorySessionStore()
    provider = job_provider or ArbeitnowJobProvider(
        settings.job_api_url, settings.request_timeout_seconds
    )
    campaign_service = CampaignService(provider)
    discovery_service = EnterpriseDiscoveryService(settings)
    browser_assistant = BrowserAssistant(settings)
    resume_review_service = ResumeReviewService(settings)
    career_copilot = CareerCopilotService()

    app = FastAPI(
        title="Resume Campaign Agent",
        version="0.2.0",
        description="Pydantic AI resume completion and job-campaign preview API",
    )
    app.state.settings = settings
    app.state.store = store
    app.state.campaign_service = campaign_service
    app.state.discovery_service = discovery_service
    app.state.browser_assistant = browser_assistant
    app.state.resume_review_service = resume_review_service
    app.state.career_copilot = career_copilot
    app.state.agent = None
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            r"^(chrome-extension://[a-p]{32}|"
            r"https?://(127\.0\.0\.1|localhost)(:\d+)?)$"
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found_handler(_, exc: SessionNotFoundError):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=404, content={"detail": f"session not found: {exc.args[0]}"})

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            ok=True,
            runtime=f"Python {platform.python_version()}",
            agent_framework="pydantic-ai",
            delivery_mode="dry_run",
            llm_configured=settings.llm_configured,
            model=settings.llm_model if settings.llm_configured else None,
            enterprise_search="agent-reach-exa+official-catalog",
            portal_templates=len(list_portal_templates()),
        )

    @app.get("/api/templates", response_model=list[PortalTemplate])
    async def portal_templates() -> list[PortalTemplate]:
        return list_portal_templates()

    @app.get("/api/templates/{template_id}", response_model=PortalTemplate)
    async def portal_template(template_id: str) -> PortalTemplate:
        template = get_portal_template(template_id)
        if template is None:
            raise HTTPException(status_code=404, detail="portal template not found")
        return template

    @app.post("/api/sessions", response_model=SessionState, status_code=201)
    async def create_session(request: CreateSessionRequest) -> SessionState:
        return await store.create(request)

    @app.get("/api/sessions/{session_id}", response_model=SessionState)
    async def get_session(session_id: str) -> SessionState:
        return await store.get(session_id)

    @app.patch("/api/sessions/{session_id}/resume", response_model=SessionState)
    async def update_resume(session_id: str, patch: ResumePatch) -> SessionState:
        return await store.update_resume(session_id, patch)

    @app.post("/api/resume/review", response_model=ResumeReviewResponse)
    async def review_resume(request: ResumeReviewRequest) -> ResumeReviewResponse:
        session = await store.get(request.session_id)
        return await resume_review_service.review(request, session)

    @app.post("/api/resume/optimize", response_model=ResumeOptimizationResponse)
    async def optimize_resume(
        request: ResumeOptimizationRequest,
    ) -> ResumeOptimizationResponse:
        session = await store.get(request.session_id)
        return await resume_review_service.optimize(request, session)

    @app.post("/api/career/job-dossier", response_model=JobDossierResponse)
    async def career_job_dossier(request: JobDossierRequest) -> JobDossierResponse:
        session = await store.get(request.session_id)
        return career_copilot.job_dossier(request, session)

    @app.post("/api/career/resume-versions", response_model=ResumeVersion, status_code=201)
    async def create_resume_version(request: ResumeVersionCreateRequest) -> ResumeVersion:
        session = await store.get(request.session_id)
        return await career_copilot.create_version(request, session)

    @app.get("/api/career/resume-versions", response_model=list[ResumeVersion])
    async def list_resume_versions(session_id: str = Query(min_length=4)) -> list[ResumeVersion]:
        await store.get(session_id)
        return await career_copilot.list_versions(session_id)

    @app.post("/api/career/resume-versions/{version_id}/audit", response_model=VersionAuditResponse)
    async def audit_resume_version(version_id: str, session_id: str = Query(min_length=4)) -> VersionAuditResponse:
        session = await store.get(session_id)
        try:
            return await career_copilot.audit_version(version_id, session)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="resume version not found") from exc

    @app.post("/api/career/jobs/rank", response_model=JobRankingResponse)
    async def rank_career_jobs(request: JobRankingRequest) -> JobRankingResponse:
        session = await store.get(request.session_id)
        return career_copilot.rank_jobs(request, session)

    @app.post("/api/career/applications", response_model=ApplicationRecord, status_code=201)
    async def create_application(request: ApplicationCreateRequest) -> ApplicationRecord:
        await store.get(request.session_id)
        return await career_copilot.create_application(request)

    @app.get("/api/career/applications", response_model=list[ApplicationRecord])
    async def list_applications(session_id: str = Query(min_length=4)) -> list[ApplicationRecord]:
        await store.get(session_id)
        return await career_copilot.list_applications(session_id)

    @app.patch("/api/career/applications/{application_id}", response_model=ApplicationRecord)
    async def update_application(
        application_id: str,
        request: ApplicationUpdateRequest,
        session_id: str = Query(min_length=4),
    ) -> ApplicationRecord:
        await store.get(session_id)
        try:
            return await career_copilot.update_application(application_id, request, session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="application not found") from exc

    @app.get("/api/career/reminders", response_model=list[Reminder])
    async def career_reminders(session_id: str = Query(min_length=4)) -> list[Reminder]:
        await store.get(session_id)
        return await career_copilot.reminders(session_id)

    @app.get("/api/career/portal-adapters", response_model=list[PortalAdapter])
    async def career_portal_adapters() -> list[PortalAdapter]:
        return career_copilot.portal_adapters()

    @app.post("/api/career/portal-preflight", response_model=PortalPreflightResponse)
    async def career_portal_preflight(request: PortalPreflightRequest) -> PortalPreflightResponse:
        session = await store.get(request.session_id)
        return career_copilot.portal_preflight(request, session)

    @app.post("/api/career/checkpoints", response_model=RecoveryCheckpoint, status_code=201)
    async def create_recovery_checkpoint(request: RecoveryCheckpointCreate) -> RecoveryCheckpoint:
        await store.get(request.session_id)
        return await career_copilot.save_checkpoint(request)

    @app.get("/api/career/checkpoints/latest", response_model=RecoveryCheckpoint | None)
    async def latest_recovery_checkpoint(
        session_id: str = Query(min_length=4), application_id: str = Query(min_length=4)
    ) -> RecoveryCheckpoint | None:
        await store.get(session_id)
        return await career_copilot.latest_checkpoint(application_id, session_id)

    @app.post("/api/career/interview-kit", response_model=InterviewKitResponse)
    async def career_interview_kit(request: InterviewKitRequest) -> InterviewKitResponse:
        session = await store.get(request.session_id)
        return career_copilot.interview_kit(request, session)

    @app.post("/api/career/interview-simulate", response_model=InterviewSimulationResponse)
    async def career_interview_simulate(request: InterviewSimulationRequest) -> InterviewSimulationResponse:
        session = await store.get(request.session_id)
        return career_copilot.simulate_interview(request, session)

    @app.get("/api/career/funnel", response_model=FunnelAnalytics)
    async def career_funnel(session_id: str = Query(min_length=4)) -> FunnelAnalytics:
        await store.get(session_id)
        return await career_copilot.funnel(session_id)

    @app.post("/api/career/risk-check", response_model=RecruitmentRiskResponse)
    async def career_risk_check(request: RecruitmentRiskRequest) -> RecruitmentRiskResponse:
        return career_copilot.recruitment_risk(request)

    @app.post("/api/career/evidence", response_model=EvidenceItem, status_code=201)
    async def add_career_evidence(request: EvidenceItemCreate) -> EvidenceItem:
        await store.get(request.session_id)
        return await career_copilot.add_evidence(request)

    @app.get("/api/career/evidence", response_model=list[EvidenceItem])
    async def list_career_evidence(session_id: str = Query(min_length=4)) -> list[EvidenceItem]:
        await store.get(session_id)
        return await career_copilot.list_evidence(session_id)

    @app.post("/api/career/vault", response_model=VaultMetadata)
    async def put_career_vault(request: VaultPutRequest) -> VaultMetadata:
        await store.get(request.session_id)
        return await career_copilot.put_vault(request)

    @app.get("/api/career/vault", response_model=VaultMetadata)
    async def career_vault_metadata(session_id: str = Query(min_length=4)) -> VaultMetadata:
        await store.get(session_id)
        return await career_copilot.vault_metadata(session_id)

    @app.post("/api/career/vault/lease", response_model=VaultLeaseResponse)
    async def create_career_vault_lease(request: VaultLeaseRequest) -> VaultLeaseResponse:
        await store.get(request.session_id)
        try:
            return await career_copilot.create_vault_lease(request)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=f"vault field unavailable: {exc.args[0]}") from exc

    @app.get("/api/browser/sessions", response_model=list[BrowserSessionSummary])
    async def browser_sessions() -> list[BrowserSessionSummary]:
        sessions = await store.list()
        return [
            BrowserSessionSummary(
                id=session.id,
                candidate_label=session.resume.full_name or "未命名候选人",
                target_roles=session.resume.target_roles,
                base_locations=(
                    session.resume.base_locations or session.preferred_locations
                ),
                updated_at=session.updated_at,
            )
            for session in sessions
        ]

    @app.get("/api/browser/capabilities", response_model=BrowserControlContract)
    async def browser_capabilities() -> BrowserControlContract:
        return BrowserControlContract(
            commands=[
                BrowserControlCommand(
                    name="scan_form", effect="read_only", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="analyze_fields", effect="read_only", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="highlight_targets", effect="visual_only", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="fill_empty", effect="local_write", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="inspect_auth", effect="read_only", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="request_otp", effect="external_auth", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="complete_auth", effect="external_auth", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="inspect_journey", effect="read_only", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="select_live_job", effect="local_write", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="open_application", effect="local_write", requires_user_gesture=True
                ),
                BrowserControlCommand(
                    name="submit_application", effect="external_submission", requires_user_gesture=True
                ),
            ],
            denied_capabilities=[
                "read_passwords",
                "intercept_sms_or_notifications",
                "solve_or_bypass_captcha",
                "fill_identity_or_demographic_fields",
                "upload_files",
                "submit_without_per_application_authorization",
                "claim_submission_success_without_official_receipt",
                "access_cookies_or_history",
            ],
            final_submit_enabled=True,
            notice=(
                "受限 Computer Use：普通填表只在用户触发后扫描、映射、标记和填写空白安全字段；"
                "逐企业确认后，手机号从当前简历会话直接送入目标页并触发获取验证码，验证码仅由用户在侧栏输入。"
                "用户逐岗位授权后可点击唯一的官网投递按钮；人机验证、缺失必填字段、附件或人工声明会阻止提交。"
            ),
        )

    @app.post("/api/browser/analyze", response_model=BrowserFillPlan)
    async def analyze_browser_form(request: BrowserAnalyzeRequest) -> BrowserFillPlan:
        session = await store.get(request.session_id)
        return await browser_assistant.analyze(request, session)

    @app.post("/api/browser/rank-jobs", response_model=BrowserJobSelection)
    async def rank_browser_jobs(request: BrowserJobRankRequest) -> BrowserJobSelection:
        session = await store.get(request.session_id)
        return await browser_assistant.rank_jobs(request, session)

    @app.get("/api/jobs/search", response_model=list[JobPosting])
    async def search_jobs(
        direction: str = Query(min_length=2, max_length=120),
        limit: int = Query(default=10, ge=1, le=25),
    ) -> list[JobPosting]:
        try:
            return await provider.search(JobSearchQuery(direction=direction, limit=limit))
        except JobProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/campaigns/preview", response_model=CampaignPreview)
    async def preview_campaign(request: PreviewRequest) -> CampaignPreview:
        session = await store.get(request.session_id)
        try:
            return await campaign_service.preview(session, request.limit)
        except JobProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/campaigns/dispatch", status_code=status.HTTP_403_FORBIDDEN)
    async def dispatch_campaign(_: DispatchAttempt):
        raise HTTPException(
            status_code=403,
            detail="Delivery is disabled by design. Review dry-run drafts and apply manually.",
        )

    @app.post("/api/batch/preview", response_model=BatchPreviewResponse)
    async def preview_batch(request: BatchPreviewRequest) -> BatchPreviewResponse:
        results: list[BatchCandidateResult] = []
        total_jobs = 0
        total_drafts = 0
        try:
            for case in request.cases:
                session = await store.create(
                    CreateSessionRequest(
                        resume=case.resume,
                        preferred_locations=case.preferred_locations,
                        remote_preference=case.remote_preference,
                    )
                )
                preview = await campaign_service.preview(session, request.limit_per_case)
                enterprises: list[EnterpriseIntent] = []
                seen_companies: set[str] = set()
                for draft in preview.application_drafts:
                    company_key = draft.company.casefold().strip()
                    if company_key in seen_companies:
                        continue
                    seen_companies.add(company_key)
                    enterprises.append(
                        EnterpriseIntent(
                            company=draft.company,
                            job_title=draft.job_title,
                            destination=draft.destination,
                            job_url=draft.job_url,
                            matched_skills=draft.matched_skills,
                        )
                    )
                total_jobs += len(preview.jobs)
                total_drafts += len(preview.application_drafts)
                results.append(
                    BatchCandidateResult(
                        label=case.label,
                        session_id=session.id,
                        status=preview.status,
                        missing_fields=preview.missing_fields,
                        job_count=len(preview.jobs),
                        draft_count=len(preview.application_drafts),
                        recommended_destinations=preview.recommended_destinations,
                        intended_enterprises=enterprises,
                    )
                )
        except JobProviderError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return BatchPreviewResponse(
            results=results,
            total_jobs=total_jobs,
            total_drafts=total_drafts,
            notice="批量测试仅使用明确标记的合成简历；所有企业意向均为待复核草稿，未发送。",
        )

    @app.post(
        "/api/discovery/enterprises", response_model=EnterpriseDiscoveryResponse
    )
    async def discover_enterprises(
        request: EnterpriseDiscoveryRequest,
    ) -> EnterpriseDiscoveryResponse:
        session = await store.get(request.session_id)
        return await discovery_service.discover(request, session)

    @app.post("/api/agent/run", response_model=AgentRunResponse)
    async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
        session = await store.get(request.session_id)
        if not settings.llm_configured:
            raise HTTPException(
                status_code=503,
                detail="LLM is not configured. Use the llm-api-config skill locally.",
            )
        if app.state.agent is None:
            app.state.agent = build_agent(settings)
        context = compact_session_context(
            {
                "resume": public_model_dict(session.resume),
                "missing_fields": [item.field for item in missing_resume_fields(session.resume)],
                "preferred_locations": session.preferred_locations,
                "remote_preference": session.remote_preference,
            }
        )
        prompt = f"当前会话上下文：{context}\n用户消息：{request.message}"
        deps = AgentDependencies(
            session_id=request.session_id,
            store=store,
            campaign_service=campaign_service,
        )
        try:
            result = await app.state.agent.run(prompt, deps=deps)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"LLM execution failed: {type(exc).__name__}",
            ) from exc
        current = await store.get(request.session_id)
        canonical_missing = missing_resume_fields(current.resume)
        reply = result.output.model_copy(
            update={"missing_fields": [item.field for item in canonical_missing]}
        )
        return AgentRunResponse(
            session_id=request.session_id,
            reply=reply,
            resume=current.resume,
            missing_fields=canonical_missing,
            model_used=settings.llm_model or "unknown",
        )

    static_dir = Path(__file__).resolve().parent / "static"

    @app.get("/browser-test", include_in_schema=False)
    async def browser_test_form() -> FileResponse:
        return FileResponse(static_dir / "browser-test.html", media_type="text/html")

    @app.get("/browser-auth-test", include_in_schema=False)
    async def browser_auth_test_form() -> FileResponse:
        return FileResponse(static_dir / "browser-auth-test.html", media_type="text/html")

    @app.get("/browser-fixture", include_in_schema=False)
    async def browser_career_home() -> FileResponse:
        return FileResponse(static_dir / "browser-career-home.html", media_type="text/html")

    @app.get("/browser-fixture/jobs", include_in_schema=False)
    async def browser_job_list() -> FileResponse:
        return FileResponse(static_dir / "browser-job-list.html", media_type="text/html")

    @app.get("/browser-fixture/position/{position_id}/detail", include_in_schema=False)
    async def browser_job_detail(position_id: str) -> FileResponse:
        return FileResponse(static_dir / "browser-job-detail.html", media_type="text/html")

    @app.get("/browser-auth-complete", include_in_schema=False)
    async def browser_auth_complete_form() -> FileResponse:
        return FileResponse(static_dir / "browser-auth-complete.html", media_type="text/html")

    @app.get("/browser-submission-receipt", include_in_schema=False)
    async def browser_submission_receipt() -> FileResponse:
        return FileResponse(static_dir / "browser-submission-receipt.html", media_type="text/html")

    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return app


app = create_app()
