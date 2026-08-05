def field(index, label, *, input_type="text", name="", tag="input", options=None):
    return {
        "index": index,
        "signature": f"{tag}|{input_type}|{name}||{label}",
        "tag": tag,
        "input_type": input_type,
        "name": name,
        "element_id": "",
        "label": label,
        "placeholder": "",
        "autocomplete": "",
        "required": False,
        "max_length": None,
        "options": options or [],
    }


def test_browser_plan_maps_safe_fields_and_blocks_sensitive_controls(client, complete_resume):
    session = client.post("/api/sessions", json={"resume": complete_resume}).json()
    fields = [
        field(0, "候选人姓名", name="candidate_name"),
        field(1, "电子邮箱", input_type="email", name="contact_email"),
        field(2, "手机号码", input_type="tel", name="mobile"),
        field(3, "现居城市", tag="select", input_type="select", name="current_city"),
        field(4, "专业技能", tag="textarea", input_type="textarea", name="skills"),
        field(5, "登录密码", input_type="password", name="account_password"),
        field(6, "短信验证码", name="sms_otp"),
        field(7, "身份证号码", name="identity_document"),
        field(8, "我同意隐私政策", input_type="checkbox", name="privacy_consent"),
        field(9, "提交申请", input_type="submit", name="submit"),
    ]
    response = client.post(
        "/api/browser/analyze",
        json={
            "session_id": session["id"],
            "page": {"url": "https://careers.example.com/apply", "title": "申请", "fields": fields},
            "use_ai": False,
        },
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["delivery_mode"] == "dry_run"
    assert plan["submit_enabled"] is False
    assert {item["resume_field"] for item in plan["actions"]} >= {
        "full_name", "email", "phone", "city", "skills"
    }
    assert all("value" in item and item["value"] for item in plan["actions"])
    skipped = {item["field_index"]: item for item in plan["skipped"]}
    assert {5, 6, 7, 8, 9}.issubset(skipped)
    assert skipped[6]["safety_category"] == "protected"
    assert skipped[7]["safety_category"] == "protected"


def test_browser_plan_reports_resume_gaps_instead_of_inventing_values(client):
    session = client.post("/api/sessions", json={"resume": {"full_name": "测试候选人"}}).json()
    response = client.post(
        "/api/browser/analyze",
        json={
            "session_id": session["id"],
            "page": {
                "url": "https://careers.example.com/apply",
                "title": "申请",
                "fields": [field(0, "电子邮箱", input_type="email", name="email")],
            },
            "use_ai": False,
        },
    )
    plan = response.json()
    assert plan["actions"] == []
    assert plan["skipped"][0]["safety_category"] == "missing_resume_value"
    assert "email" in plan["skipped"][0]["reason"]


def test_browser_job_ranking_selects_same_origin_live_matching_role(client, complete_resume):
    session = client.post(
        "/api/sessions",
        json={"resume": complete_resume, "preferred_locations": ["上海"]},
    ).json()
    response = client.post(
        "/api/browser/rank-jobs",
        json={
            "session_id": session["id"],
            "page_url": "https://jobs.example.cn/positions",
            "candidates": [
                {
                    "index": 0,
                    "title": "AI Engineer",
                    "url": "https://jobs.example.cn/position/10001/detail",
                    "metadata": "上海 Python FastAPI LLM",
                },
                {
                    "index": 1,
                    "title": "Senior AI Engineer",
                    "url": "https://jobs.example.cn/position/10002/detail",
                    "metadata": "上海 Python 8年以上经验",
                },
                {
                    "index": 2,
                    "title": "AI Engineer",
                    "url": "https://evil.example/position/10003/detail",
                    "metadata": "上海 Python",
                },
                {
                    "index": 3,
                    "title": "AI Engineer（职位已下线）",
                    "url": "https://jobs.example.cn/position/10004/detail",
                    "metadata": "上海 Python",
                },
            ],
        },
    )
    assert response.status_code == 200
    selection = response.json()
    assert selection["selected_index"] == 0
    assert selection["selected_url"] == "https://jobs.example.cn/position/10001/detail"
    assert selection["ai_used"] is False
    assert 1 in selection["rejected_indexes"]


def test_browser_session_picker_and_mock_form_are_available(client, complete_resume):
    created = client.post("/api/sessions", json={"resume": complete_resume}).json()
    sessions = client.get("/api/browser/sessions")
    assert sessions.status_code == 200
    assert sessions.json()[0]["id"] == created["id"]
    mock = client.get("/browser-test")
    assert mock.status_code == 200
    assert "安全演练" in mock.text
    assert "短信验证码" in mock.text
    assert "disabled" in mock.text
    auth_mock = client.get("/browser-auth-test")
    assert auth_mock.status_code == 200
    assert "演练验证码：246810" in auth_mock.text
    assert "没有发送短信" in auth_mock.text
    auth_complete = client.get("/browser-auth-complete")
    assert auth_complete.status_code == 200
    assert "认证接力已完成" in auth_complete.text
    assert 'id="submit-application"' in auth_complete.text
    receipt = client.get("/browser-submission-receipt")
    assert receipt.status_code == 200
    assert "MOCK-RC-20260804-001" in receipt.text
    assert "查看全部职位" in client.get("/browser-fixture").text
    assert "Senior AI Engineer" in client.get("/browser-fixture/jobs").text
    assert "立即投递" in client.get("/browser-fixture/position/10001/detail").text


def test_extension_manifest_has_gated_submit_and_no_broad_fixed_host_permission():
    import json
    from pathlib import Path

    manifest_path = Path(__file__).resolve().parents[1] / "browser_extension" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["host_permissions"] == ["http://127.0.0.1:18010/*"]
    assert "<all_urls>" not in manifest.get("host_permissions", [])
    assert manifest["optional_host_permissions"] == ["http://*/*", "https://*/*"]
    assert not {"debugger", "cookies", "history", "downloads"}.intersection(
        manifest["permissions"]
    )
    assert manifest["content_scripts"][0]["matches"] == ["http://127.0.0.1:18010/*"]
    assert manifest["content_scripts"][0]["js"] == ["bridge.js"]
    content = (manifest_path.parent / "content.js").read_text(encoding="utf-8")
    assert ".submit(" not in content
    assert "RC_APPLY_PLAN" in content
    assert "RC_HIGHLIGHT_PLAN" in content
    panel = (manifest_path.parent / "panel.js").read_text(encoding="utf-8")
    assert "ResumeCopilotPermissions.request(chrome" in panel
    assert "ResumeCopilotPermissions.remove(chrome" in panel
    assert 'files: ["auth-utils.js", "journey-utils.js", "content.js", "auth-content.js", "journey-content.js", "submit-content.js"]' in panel
    auth_content = (manifest_path.parent / "auth-content.js").read_text(encoding="utf-8")
    assert ".submit(" not in auth_content
    assert "RC_AUTH_REQUEST_OTP" in auth_content
    assert "RC_AUTH_COMPLETE" in auth_content
    assert "isApplicationSubmitText" in auth_content
    assert "chrome.storage" not in auth_content
    submit_content = (manifest_path.parent / "submit-content.js").read_text(encoding="utf-8")
    assert ".submit(" not in submit_content
    assert "RC_SUBMIT_APPLICATION" in submit_content
    assert "authorization.length < 8" in submit_content
    assert "state.blockers.length" in submit_content
    assert "isFinalSubmitText" in submit_content
    assert "isApplicationSubmitText" not in submit_content
    journey_content = (manifest_path.parent / "journey-content.js").read_text(encoding="utf-8")
    assert ".submit(" not in journey_content
    assert "RC_INSPECT_JOURNEY" in journey_content
    assert "RC_OPEN_JOB" in journey_content
    assert "isOpenApplicationText" in journey_content
    bridge = (manifest_path.parent / "bridge.js").read_text(encoding="utf-8")
    assert "RC_AI_TAKEOVER_REQUEST" in bridge
    assert "phone" not in bridge.casefold()
    assert "otp" not in bridge.casefold()
    worker = (manifest_path.parent / "service-worker.js").read_text(encoding="utf-8")
    assert "chrome.permissions.request" in worker
    assert "chrome.storage.session" in worker
    assert "simulationOnly: payload?.simulationOnly === true" in worker
    assert "phone" not in worker.casefold()
    assert "otp" not in worker.casefold()


def test_synthetic_resume_can_inspect_official_portal_but_cannot_transmit_or_submit():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "src" / "resume_campaign_agent" / "static" / "app.js").read_text(encoding="utf-8")
    panel = (root / "browser_extension" / "panel.js").read_text(encoding="utf-8")
    submit = (root / "browser_extension" / "submit-content.js").read_text(encoding="utf-8")

    assert "simulationOnly=isSyntheticResume(resume)" in app
    assert "当前是合成档案。请先换成真实简历" not in app
    assert "if (handoff.simulationOnly)" in panel
    assert "finishSimulationAtBoundary" in panel
    assert "renderPlan(plan, { allowFill: false })" in panel
    assert "if (!currentPlanWriteAllowed)" in panel
    assert 'if (simulationOnly) throw new Error("合成档案官网预演禁止最终提交")' in submit


def test_browser_capabilities_are_constrained_and_fail_closed(client):
    response = client.get("/api/browser/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "constrained_computer_use"
    assert body["permission_strategy"] == "active_tab_plus_optional_single_origin"
    assert body["model_receives_resume_values"] is False
    assert body["final_submit_enabled"] is True
    assert {command["name"] for command in body["commands"]} == {
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
    }
    assert "submit_without_per_application_authorization" in body["denied_capabilities"]
    assert "claim_submission_success_without_official_receipt" in body["denied_capabilities"]
    assert "intercept_sms_or_notifications" in body["denied_capabilities"]
    assert "solve_or_bypass_captcha" in body["denied_capabilities"]
    assert "access_cookies_or_history" in body["denied_capabilities"]
