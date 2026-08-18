from datetime import date, datetime, timedelta, timezone

import pytest

from resume_campaign_agent.career_copilot import CareerCopilotService
from resume_campaign_agent.career_models import ApplicationCreateRequest

def _session(client):
    resume = {
        "full_name": "合成候选人",
        "email": "career.synthetic@example.com",
        "phone": "18800001234",
        "city": "上海",
        "professional_headline": "品牌运营应届生",
        "target_roles": ["品牌运营", "内容运营"],
        "base_locations": ["上海", "杭州"],
        "skills": ["内容策划", "Excel", "用户调研"],
        "summary": "市场营销应届生，参与校园品牌活动、问卷调研与内容策划。",
        "education": [{"school": "海湾商学院（虚构）", "degree": "本科", "major": "市场营销", "graduation_year": 2026}],
        "projects": [{
            "name": "校园新品推广（虚构）",
            "role": "项目负责人",
            "description": "组织用户调研、内容排期和线下活动。",
            "highlights": ["回收 300 份有效问卷", "协调 8 名成员完成活动"],
        }],
    }
    response = client.post("/api/sessions", json={"resume": resume, "preferred_locations": ["上海"]})
    assert response.status_code == 201
    return response.json()


JD = """岗位职责：负责品牌内容策划、用户调研和活动复盘。
任职要求：本科及以上学历，具备 Excel 数据整理能力。
有消费品校园推广经验者优先。"""


@pytest.mark.asyncio
async def test_application_timeline_survives_service_restart(tmp_path):
    service = CareerCopilotService(data_dir=tmp_path)
    created = await service.create_application(
        ApplicationCreateRequest(
            session_id="sess_persist",
            company="星河消费（虚构）",
            title="品牌运营",
            status="ready",
            job_description=JD,
        )
    )

    reloaded = CareerCopilotService(data_dir=tmp_path)
    applications = await reloaded.list_applications("sess_persist")
    assert [item.id for item in applications] == [created.id]


def test_job_dossier_version_and_fact_audit(client):
    session = _session(client)
    dossier = client.post("/api/career/job-dossier", json={
        "session_id": session["id"], "company": "星河消费（虚构）", "title": "品牌运营",
        "description": JD, "location": "上海", "url": "https://careers.example.com/brand",
    })
    assert dossier.status_code == 200
    body = dossier.json()
    assert body["requirements"]
    assert 0 <= body["match_score"] <= 100
    assert body["direct_identifiers_shared_with_model"] is False
    assert body["resume_evidence"]

    version = client.post("/api/career/resume-versions", json={
        "session_id": session["id"], "target_company": "星河消费（虚构）",
        "target_title": "品牌运营", "job_description": JD,
    })
    assert version.status_code == 201
    version_body = version.json()
    assert version_body["source_resume_mutated"] is False
    assert all(change["fact_changed"] is False for change in version_body["changes"])
    audit = client.post(
        f"/api/career/resume-versions/{version_body['id']}/audit?session_id={session['id']}"
    )
    assert audit.status_code == 200
    assert audit.json()["passed"] is True
    after = client.get(f"/api/sessions/{session['id']}").json()
    assert after["resume"] == session["resume"]


def test_job_ranking_detects_duplicates_expiry_and_unofficial_channels(client):
    session = _session(client)
    response = client.post("/api/career/jobs/rank", json={
        "session_id": session["id"],
        "jobs": [
            {"id": "j1", "company": "星河消费", "title": "品牌运营", "description": JD, "location": "上海", "url": "https://careers.example.com/1", "source": "official", "deadline": (date.today() + timedelta(days=2)).isoformat()},
            {"id": "j2", "company": "星河消费", "title": "品牌运营", "description": JD, "location": "上海", "url": "https://third.example.net/2", "source": "转载"},
            {"id": "j3", "company": "远方品牌", "title": "内容运营", "description": JD, "location": "北京", "url": "https://careers.example.com/3", "source": "official", "deadline": (date.today() - timedelta(days=1)).isoformat()},
        ],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["duplicate_groups"] == [["j1", "j2"]]
    assert body["recommended_today"] == ["j1"]
    assert any(item["invalid_reasons"] for item in body["ranked_jobs"] if item["job"]["id"] == "j3")


def test_application_timeline_reminders_and_funnel(client):
    session = _session(client)
    application = client.post("/api/career/applications", json={
        "session_id": session["id"], "company": "星河消费（虚构）", "title": "品牌运营",
        "url": "https://careers.example.com/brand", "location": "上海", "status": "ready",
        "job_description": JD, "deadline": (date.today() + timedelta(days=2)).isoformat(),
        "next_action_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat(),
    })
    assert application.status_code == 201
    app = application.json()
    updated = client.patch(
        f"/api/career/applications/{app['id']}?session_id={session['id']}",
        json={"status": "applied", "note": "合成测试回执", "receipt_reference": "synthetic-receipt"},
    )
    assert updated.status_code == 200
    assert len(updated.json()["history"]) == 2
    reminders = client.get(f"/api/career/reminders?session_id={session['id']}")
    assert reminders.status_code == 200
    funnel = client.get(f"/api/career/funnel?session_id={session['id']}")
    assert funnel.status_code == 200
    assert funnel.json()["total"] == 1


def test_portal_preflight_and_recovery_checkpoint(client):
    session = _session(client)
    app = client.post("/api/career/applications", json={
        "session_id": session["id"], "company": "星河消费", "title": "品牌运营",
        "url": "https://example.mokahr.com/apply", "status": "preparing",
    }).json()
    blocked = client.post("/api/career/portal-preflight", json={
        "session_id": session["id"], "application_id": app["id"],
        "url": "https://example.mokahr.com/apply",
        "detected_fields": ["name", "email", "phone", "identity_number", "resume"],
        "available_attachments": [], "user_confirmed": False,
    })
    assert blocked.status_code == 200
    body = blocked.json()
    assert body["adapter"]["id"] == "moka"
    assert body["can_submit"] is False
    assert "identity_number" in body["blocked_sensitive_fields"]
    assert body["attachment_checks"]

    checkpoint = client.post("/api/career/checkpoints", json={
        "session_id": session["id"], "application_id": app["id"],
        "url": "https://example.mokahr.com/apply", "completed_fields": ["name", "email"],
        "pending_fields": ["resume"], "step": "profile",
    })
    assert checkpoint.status_code == 201
    latest = client.get(f"/api/career/checkpoints/latest?session_id={session['id']}&application_id={app['id']}")
    assert latest.status_code == 200
    assert latest.json()["pending_fields"] == ["resume"]


def test_interview_risk_evidence_and_encrypted_vault(client):
    session = _session(client)
    kit = client.post("/api/career/interview-kit", json={
        "session_id": session["id"], "company": "星河消费（虚构）", "title": "品牌运营", "job_description": JD,
    })
    assert kit.status_code == 200
    assert kit.json()["resume_questions"]
    assert kit.json()["invented_facts"] is False

    simulation = client.post("/api/career/interview-simulate", json={
        "session_id": session["id"], "question": "介绍一次项目经历",
        "answer": "背景是校园新品推广，我负责用户调研和活动协调，最后回收 999 份问卷。",
    })
    assert simulation.status_code == 200
    assert simulation.json()["consistency_score"] < 100

    risk = client.post("/api/career/risk-check", json={
        "company": "未知公司", "title": "高薪兼职", "description": "无需面试，先交报名费并办理培训贷",
        "url": "http://example.invalid/apply",
    })
    assert risk.status_code == 200
    assert risk.json()["risk_level"] == "critical"

    evidence = client.post("/api/career/evidence", json={
        "session_id": session["id"], "category": "project", "label": "问卷统计表（合成）",
        "source_reference": "local://synthetic-survey.xlsx", "facts": ["有效问卷 300 份"], "verified_by_user": True,
    })
    assert evidence.status_code == 201
    assert client.get(f"/api/career/evidence?session_id={session['id']}").json()[0]["verified_by_user"] is True

    secret_value = "SYNTHETIC-ID-ONLY"
    vault = client.post("/api/career/vault", json={
        "session_id": session["id"], "values": {"identity_number": secret_value},
    })
    assert vault.status_code == 200
    vault_body = vault.json()
    assert vault_body["fields"] == ["identity_number"]
    assert vault_body["plaintext_returned"] is False
    assert secret_value not in vault.text
    denied = client.post("/api/career/vault/lease", json={
        "session_id": session["id"], "fields": ["identity_number"],
        "target_url": "https://careers.example.com/apply", "user_confirmed": False,
    })
    assert denied.status_code == 403
    lease = client.post("/api/career/vault/lease", json={
        "session_id": session["id"], "fields": ["identity_number"],
        "target_url": "https://careers.example.com/apply", "user_confirmed": True,
    })
    assert lease.status_code == 200
    assert lease.json()["plaintext_returned"] is False
    assert secret_value not in lease.text
