from resume_campaign_agent.models import ResumeProfile
from resume_campaign_agent.resume_review import _deidentified_resume


def test_resume_review_returns_six_generic_dimensions_without_mutating(client, complete_resume):
    created = client.post("/api/sessions", json={"resume": complete_resume}).json()
    response = client.post(
        "/api/resume/review",
        json={
            "session_id": created["id"],
            "target_role": "AI Engineer",
            "target_job_description": "Python FastAPI LLM 服务开发",
            "use_ai": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["overall_score"] <= 100
    assert {item["key"] for item in body["dimensions"]} == {
        "completeness", "relevance", "evidence", "credibility", "clarity", "readability"
    }
    assert body["direct_identifiers_shared_with_model"] is False
    assert body["source_resume_mutated"] is False
    after = client.get(f"/api/sessions/{created['id']}").json()
    assert after["resume"] == created["resume"]


def test_resume_review_surfaces_missing_evidence_questions(client):
    created = client.post(
        "/api/sessions", json={"resume": {"target_roles": ["市场营销"]}}
    ).json()
    body = client.post(
        "/api/resume/review",
        json={"session_id": created["id"], "use_ai": False},
    ).json()
    assert body["grade"] in {"C", "D"}
    assert any(item["severity"] == "critical" for item in body["findings"])
    assert body["evidence_questions"]


def test_resume_optimization_is_suggestion_only_and_does_not_invent_numbers(client, complete_resume):
    resume = {
        **complete_resume,
        "professional_headline": "AI 应用开发工程师",
        "work_experience": [
            {
                "company": "示例研究院",
                "title": "开发实习生",
                "start_date": "2025-01-01",
                "end_date": "2025-06-30",
                "responsibilities": "参与智能体服务开发和接口联调。",
                "highlights": ["完成接口联调并整理文档"],
            }
        ],
    }
    created = client.post("/api/sessions", json={"resume": resume}).json()
    response = client.post(
        "/api/resume/optimize",
        json={"session_id": created["id"], "target_role": "AI Engineer", "use_ai": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["suggestions"]
    assert all(item["requires_user_confirmation"] for item in body["suggestions"])
    assert all(item["invented_facts"] is False for item in body["suggestions"])
    assert body["source_resume_mutated"] is False
    after = client.get(f"/api/sessions/{created['id']}").json()
    assert after["resume"] == created["resume"]


def test_deidentified_review_context_removes_direct_identifiers():
    resume = ResumeProfile(
        full_name="张三",
        preferred_name="小张",
        email="zhangsan@example.com",
        phone="13800000000",
        wechat="zhangsan_wechat",
        expected_salary="20k",
        work_authorization="某许可编号",
        target_roles=["产品经理"],
        additional_information="联系邮箱 hidden@example.com，手机号 13912345678，微信号: hidden_wechat",
    )
    safe = _deidentified_resume(resume)
    assert not {
        "full_name", "preferred_name", "email", "phone", "wechat",
        "expected_salary", "work_authorization",
    }.intersection(safe)
    assert safe["target_roles"] == ["产品经理"]
    serialized = str(safe)
    assert "hidden@example.com" not in serialized
    assert "13912345678" not in serialized
    assert "hidden_wechat" not in serialized
