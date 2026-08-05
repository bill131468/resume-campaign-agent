def test_health_exposes_dry_run_boundary(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["agent_framework"] == "pydantic-ai"
    assert body["delivery_mode"] == "dry_run"
    assert body["deployment_mode"] == "test"
    assert body["test_fixtures_enabled"] is True
    assert body["browser_submission_enabled"] is False


def test_production_mode_starts_empty_and_hides_all_browser_fixtures(production_client):
    health = production_client.get("/api/health").json()
    assert health["deployment_mode"] == "production"
    assert health["delivery_mode"] == "per_application_authorized"
    assert health["test_fixtures_enabled"] is False
    assert health["server_dispatch_enabled"] is False
    assert health["browser_submission_enabled"] is True

    home = production_client.get("/")
    assert home.status_code == 200
    assert "正式投递模式" in home.text
    assert "REAL PROFILE" in home.text
    assert "合成测试档案" not in home.text
    assert "loadDemoButton" not in home.text
    assert "星河消费（虚构）" not in home.text

    app_script = production_client.get("/app.js")
    assert app_script.status_code == 200
    assert "syntheticCase" not in app_script.text
    assert "fillResume(syntheticCase)" not in app_script.text

    for path in (
        "/browser-test",
        "/browser-auth-test",
        "/browser-fixture",
        "/browser-fixture/jobs",
        "/browser-auth-complete",
        "/browser-submission-receipt",
        "/browser-submission-receipt.html",
    ):
        assert production_client.get(path).status_code == 404


def test_missing_resume_blocks_application_drafts(client):
    created = client.post(
        "/api/sessions",
        json={"resume": {"target_roles": ["AI Engineer"]}},
    ).json()
    response = client.post(
        "/api/campaigns/preview",
        json={"session_id": created["id"], "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_input"
    assert body["delivery_mode"] == "dry_run"
    assert body["jobs"]
    assert body["application_drafts"] == []
    assert "email" in {item["field"] for item in body["missing_fields"]}


def test_complete_resume_creates_review_only_drafts(client, complete_resume):
    created = client.post(
        "/api/sessions",
        json={
            "resume": complete_resume,
            "preferred_locations": ["Berlin"],
            "remote_preference": "preferred",
        },
    ).json()
    response = client.post(
        "/api/campaigns/preview",
        json={"session_id": created["id"], "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready_for_review"
    assert len(body["application_drafts"]) == 2
    assert all(draft["status"] == "draft" for draft in body["application_drafts"])
    assert all(draft["send_enabled"] is False for draft in body["application_drafts"])
    assert body["recommended_destinations"][0]["destination"] == "Berlin, Germany"


def test_dispatch_is_always_refused(client, complete_resume):
    created = client.post("/api/sessions", json={"resume": complete_resume}).json()
    response = client.post(
        "/api/campaigns/dispatch",
        json={"session_id": created["id"], "application_ids": ["job_1"], "confirmation": True},
    )
    assert response.status_code == 403
    assert "disabled by design" in response.json()["detail"]


def test_patch_writes_user_fields_into_template(client):
    created = client.post("/api/sessions", json={}).json()
    response = client.patch(
        f"/api/sessions/{created['id']}/resume",
        json={"full_name": "李雷", "skills": ["Python", "SQL", "Docker"]},
    )
    assert response.status_code == 200
    assert response.json()["resume"]["full_name"] == "李雷"
    assert response.json()["resume"]["skills"] == ["Python", "SQL", "Docker"]


def test_entry_level_resume_never_drafts_obvious_senior_role(client, complete_resume):
    created = client.post("/api/sessions", json={"resume": complete_resume}).json()
    body = client.post(
        "/api/campaigns/preview",
        json={"session_id": created["id"], "limit": 5},
    ).json()
    titles = {draft["job_title"] for draft in body["application_drafts"]}
    assert all("senior" not in title.casefold() for title in titles)
    assert all("director" not in title.casefold() for title in titles)


def test_seniority_gate_is_fail_closed_for_entry_level_candidates():
    assert is_seniority_compatible("Python Engineer", 0) is True
    assert is_seniority_compatible("Senior Python Engineer", 0) is False
    assert is_seniority_compatible("Staff AI Engineer", 1.5) is False
    assert is_seniority_compatible("Director of Engineering", 4) is False
    assert is_seniority_compatible("Senior Python Engineer", 6) is True


def test_batch_preview_separates_complete_and_incomplete_resumes(client, complete_resume):
    response = client.post(
        "/api/batch/preview",
        json={
            "synthetic_fixture": True,
            "limit_per_case": 5,
            "cases": [
                {"label": "完整样本", "resume": complete_resume},
                {
                    "label": "缺字段样本",
                    "resume": {"target_roles": ["AI Engineer"], "skills": ["Python"]},
                },
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_mode"] == "dry_run"
    assert body["synthetic_fixture"] is True
    assert body["all_send_disabled"] is True
    assert body["results"][0]["status"] == "ready_for_review"
    assert body["results"][0]["draft_count"] == 2
    assert body["results"][1]["status"] == "needs_input"
    assert body["results"][1]["draft_count"] == 0
    assert all(
        enterprise["send_enabled"] is False
        for enterprise in body["results"][0]["intended_enterprises"]
    )


def test_frontend_is_served_with_ai_takeover_language(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "投递作战夹" in response.text
    assert "逐岗位确认后投递" in response.text
    assert "AI 投递队列" in response.text
    assert "简历审核与优化台" in response.text
    assert "不会自动覆盖原简历" in response.text
    assert "求职驾驶舱" in response.text
    assert "事实证据库与敏感信息保险箱" in response.text
    assert client.get("/styles.css").status_code == 200
    app = client.get("/app.js")
    assert app.status_code == 200
    assert 'requestJson("/api/resume/review"' in app.text
    assert 'requestJson("/api/resume/optimize"' in app.text
    assert 'requestJson("/api/career/job-dossier"' in app.text
    assert 'requestJson("/api/career/portal-preflight"' in app.text


def test_boc_template_separates_sensitive_portal_fields(client):
    response = client.get("/api/templates/boc-campus-2026-reference")
    assert response.status_code == 200
    body = response.json()
    assert body["organization"] == "中国银行"
    assert len(body["fields"]) > 50
    sensitive = [field for field in body["fields"] if field["sensitive"]]
    assert sensitive
    protected = {"identity_document", "family_members", "home_address"}
    assert all(
        field["storage_policy"] != "master_resume"
        for field in sensitive
        if field["field"] in protected
    )
    assert any("最多申请 4 个岗位" in rule for rule in body["application_rules"])


class FakeEnterpriseWebProvider:
    async def search(self, query, num_results=8):
        return [
            WebSearchHit(
                title="上海证券交易所招聘信息",
                url="https://www.sse.com.cn/aboutus/recruitment/sse/",
                highlights="上海 金融业务 研究 法律 财务 信息技术 校园招聘",
                query=query,
            )
        ]


async def test_enterprise_discovery_is_base_and_profession_aware():
    settings = Settings(
        llm_provider="openai-compatible",
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
        job_api_url="https://example.invalid",
        request_timeout_seconds=1,
    )
    service = EnterpriseDiscoveryService(settings, FakeEnterpriseWebProvider())
    session = SessionState(
        id="fixture",
        resume=ResumeProfile(
            city="上海",
            target_roles=["法律合规"],
            target_industries=["金融"],
            base_locations=["上海"],
            education=[
                {
                    "school": "示例大学",
                    "degree": "本科",
                    "major": "法学",
                    "graduation_year": 2026,
                }
            ],
        ),
    )
    response = await service.discover(
        EnterpriseDiscoveryRequest(
            session_id="fixture",
            base_locations=["上海"],
            professional_directions=["法律合规"],
            industries=["金融"],
            limit=12,
            ai_ranking=False,
        ),
        session,
    )
    assert response.query_plan
    assert all("上海" in query for query in response.query_plan)
    assert response.enterprises
    assert response.enterprises[0].application_channels
    sse = next(lead for lead in response.enterprises if lead.company == "上海证券交易所")
    assert sse.application_channels
    assert sse.application_readiness in {"direct_official", "official_hub"}
    assert any(channel.official_evidence_url for channel in sse.application_channels)
    assert response.official_entry_count > 0
    assert all(lead.send_enabled is False for lead in response.enterprises)
    assert "software engineer" not in " ".join(response.query_plan).casefold()


def test_official_entry_catalog_distinguishes_hub_from_closed_seasonal_portal():
    from resume_campaign_agent.china_catalog import CHINA_ENTERPRISE_CATALOG, application_channels_for

    boc = next(entry for entry in CHINA_ENTERPRISE_CATALOG if entry.name == "中国银行")
    channels = application_channels_for(boc)
    assert any(channel.availability == "entry_hub" for channel in channels)
    assert any(channel.availability == "seasonal_closed" for channel in channels)
    assert all(channel.url.startswith("https://") for channel in channels)
from resume_campaign_agent.campaign import is_seniority_compatible
from resume_campaign_agent.config import Settings
from resume_campaign_agent.discovery import EnterpriseDiscoveryService, WebSearchHit
from resume_campaign_agent.models import EnterpriseDiscoveryRequest, ResumeProfile, SessionState
