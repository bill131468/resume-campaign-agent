const API = "http://127.0.0.1:18010";
const $ = (selector) => document.querySelector(selector);
let currentPlan = null;
let currentTabId = null;
let currentSitePermission = null;
let authRelay = null;
let currentHandoff = null;
let currentPlanWriteAllowed = true;

function message(text, kind = "") {
  const node = $("#message");
  node.textContent = text;
  node.className = `message ${kind}`.trim();
}

function setBusy(button, busy, busyText) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? busyText : button.dataset.label;
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    if (response.status === 500) {
      throw new Error("后端服务出错了。请确认已启动服务：python -m resume_campaign_agent");
    }
    if (response.status === 422) {
      throw new Error("简历信息不完整或格式有误，请检查必填字段。");
    }
    throw new Error(detail);
  }
  return response.json();
}

async function downloadBlob(path, payload) {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    if (response.status === 500) {
      throw new Error("后端服务出错了。请确认已启动服务：python -m resume_campaign_agent");
    }
    throw new Error(detail);
  }
  return response.blob();
}

function safeFilenamePart(value, fallback) {
  return String(value || fallback).trim().replace(/[\\/:*?"<>|]+/g, "_");
}

async function exportWordResume() {
  const button = $("#export-word-button");
  const sessionId = $("#session-select").value;
  if (!sessionId) {
    message("请先选择一份简历会话。", "error");
    return null;
  }

  setBusy(button, true, "正在生成简历...");
  try {
    const session = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
    const profile = session.resume;
    const company = currentHandoff?.company || "未指定公司";
    const position = currentHandoff?.jobTitle || currentHandoff?.channelLabel || "未指定职位";

    const blob = await downloadBlob("/api/export/resume/word", { profile, company, position });
    const filename = `${safeFilenamePart(profile.full_name, "候选人")}_${safeFilenamePart(company, "公司")}_${safeFilenamePart(position, "职位")}.pdf`;

    message(`简历已生成：${filename}`, "success");
    return { blob, filename };
  } catch (error) {
    message(error.message, "error");
    throw error;
  } finally {
    setBusy(button, false, "");
  }
}

async function autoUploadResume(blob, filename) {
  if (!blob) return { success: false, error: "no blob" };

  const arrayBuffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(arrayBuffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  const base64 = btoa(binary);

  const tab = await activeTab();
  const [injection] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: async ({ blobData, blobType, fileName }) => {
      const binary = atob(blobData);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const blob = new Blob([bytes], { type: blobType });
      const file = new File([blob], fileName, { type: blobType });

      const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
      const visible = (element) => Boolean(element && element.getClientRects().length);

      const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'))
        .filter((element) => !element.disabled && !element.readOnly);

      if (!fileInputs.length) {
        return { ok: false, error: "当前页面没有找到可用的附件上传控件" };
      }

      const scoreFileInput = (element) => {
        const container = element.closest("label, .el-form-item, .ant-form-item, .form-item, [class*='upload' i], [class*='form' i]");
        const text = [
          element.accept, element.name, element.id,
          element.getAttribute("aria-label"), element.getAttribute("placeholder"),
          container?.innerText, container?.textContent
        ].map(clean).join(" ").toLowerCase();

        let score = visible(element) ? 10 : 0;
        if (text.includes("简历") || text.includes("resume")) score += 200;
        if (text.includes("自动解析") || text.includes("拖拽至此区域自动解析")) score += 100;
        if (text.includes("附件") || text.includes("上传") || text.includes("upload")) score += 30;
        if (text.includes("作品") || text.includes("作品集") || text.includes("portfolio")) score -= 100;
        if (text.includes(".doc") || text.includes("word")) score += 20;
        if (text.includes("头像") || text.includes("photo") || text.includes("image")) score -= 50;
        return score;
      };

      const targetInput = fileInputs
        .map((element) => ({ element, score: scoreFileInput(element) }))
        .sort((a, b) => b.score - a.score)[0]?.element;

      if (!targetInput) {
        return { ok: false, error: "未找到可用的简历附件上传控件" };
      }

      try {
        const transfer = new DataTransfer();
        transfer.items.add(file);
        targetInput.files = transfer.files;
        targetInput.dispatchEvent(new Event("input", { bubbles: true }));
        targetInput.dispatchEvent(new Event("change", { bubbles: true }));
        return { ok: true, filename: fileName };
      } catch (error) {
        return { ok: false, error: error.message || "浏览器拒绝设置附件文件" };
      }
    },
    args: [{ blobData: base64, blobType: "application/pdf", fileName: filename }]
  });

  const result = injection?.result;
  if (!result?.ok) {
    message(result?.error || "上传附件失败", "error");
    return { success: false, error: result?.error };
  }

  message(`已自动上传 ${result.filename} 到官网附件区，请复核。`, "success");
  return { success: true, filename: result.filename };
}

function showUploadConfirm(filename) {
  $("#upload-confirm-text").textContent = `简历已生成：${filename}。是否自动上传到官网附件区？`;
  $("#upload-confirm-bar").hidden = false;
}

function hideUploadConfirm() {
  $("#upload-confirm-bar").hidden = true;
}

async function uploadResumeAttachment() {
  const button = $("#upload-resume-button");
  setBusy(button, true, "等待选择文件...");
  try {
    const tab = await activeTab();
    if (!tab.url || !tab.url.startsWith("http")) {
      throw new Error("请先切换到招聘网站页面");
    }

    const [injection] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: async () => {
        const visible = (element) => Boolean(element && element.getClientRects().length);
        const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

        const fileInputs = Array.from(document.querySelectorAll('input[type="file"]'))
          .filter((element) => !element.disabled && !element.readOnly);

        if (!fileInputs.length) {
          return { ok: false, error: "当前页面没有找到可用的附件上传控件" };
        }

        const scoreFileInput = (element) => {
          const container = element.closest("label, .el-form-item, .ant-form-item, .form-item, [class*='upload' i], [class*='form' i]");
          const text = [
            element.accept,
            element.name,
            element.id,
            element.getAttribute("aria-label"),
            element.getAttribute("placeholder"),
            container?.innerText,
            container?.textContent
          ].map(clean).join(" ").toLowerCase();

          let score = visible(element) ? 10 : 0;
          if (text.includes("简历") || text.includes("resume")) score += 200;
          if (text.includes("自动解析") || text.includes("拖拽至此")) score += 100;
          if (text.includes("附件") || text.includes("上传") || text.includes("upload")) score += 30;
          if (text.includes(".doc") || text.includes("word") || text.includes("pdf")) score += 20;
          if (text.includes("头像") || text.includes("photo") || text.includes("image")) score -= 50;
          if (text.includes("作品") || text.includes("作品集") || text.includes("portfolio")) score -= 100;
          return score;
        };

        const targetInput = fileInputs
          .map((element) => ({ element, score: scoreFileInput(element) }))
          .sort((a, b) => b.score - a.score)[0]?.element;

        if (!targetInput) {
          return { ok: false, error: "未找到可用的简历附件上传控件" };
        }

        return await new Promise((resolve) => {
          const picker = document.createElement("input");
          picker.type = "file";
          picker.accept = ".doc,.docx,.pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf";
          picker.style.position = "fixed";
          picker.style.left = "-9999px";
          picker.style.top = "-9999px";
          document.body.appendChild(picker);

          picker.addEventListener("change", () => {
            const file = picker.files?.[0];
            picker.remove();

            if (!file) {
              resolve({ ok: false, error: "未选择文件" });
              return;
            }

            if (!/\.(doc|docx|pdf)$/i.test(file.name)) {
  resolve({ ok: false, error: "请选择简历文件（.doc、.docx 或 .pdf）" });
  return;
}

            try {
              const transfer = new DataTransfer();
              transfer.items.add(file);
              targetInput.files = transfer.files;
              targetInput.dispatchEvent(new Event("input", { bubbles: true }));
              targetInput.dispatchEvent(new Event("change", { bubbles: true }));
              resolve({ ok: true, filename: file.name });
            } catch (error) {
              resolve({ ok: false, error: error.message || "浏览器拒绝设置附件文件" });
            }
          }, { once: true });

          picker.click();
        });
      }
    });

    const result = injection?.result;
    if (!result?.ok) throw new Error(result?.error || "上传附件失败");
    message(`已把 ${result.filename} 设置到页面附件控件，请在官网页面复核。`, "success");
  } catch (error) {
    message(error.message, "error");
  } finally {
    setBusy(button, false, "");
  }
}

async function loadAgent() {
  try {
    const [health, sessions, capabilities] = await Promise.all([
      api("/api/health"), api("/api/browser/sessions"), api("/api/browser/capabilities")
    ]);
    $("#agent-dot").className = "dot online";
    $("#agent-status").textContent = "本机 Agent 已连接";
    $("#agent-detail").textContent = `${health.agent_framework} · ${capabilities.mode} · ${health.model || "规则模式"}`;
    const select = $("#session-select");
    select.innerHTML = sessions.length
      ? sessions.map((session) => `<option value="${session.id}">${escapeHtml(session.candidate_label)} · ${escapeHtml(session.target_roles[0] || "未设方向")}</option>`).join("")
      : '<option value="">暂无简历会话</option>';
    const saved = await chrome.storage.local.get("resumeCopilotSessionId");
    if (saved.resumeCopilotSessionId && sessions.some((item) => item.id === saved.resumeCopilotSessionId)) {
      select.value = saved.resumeCopilotSessionId;
    }
    updateSessionMeta(sessions);
    select.addEventListener("change", async () => {
      await chrome.storage.local.set({ resumeCopilotSessionId: select.value });
      updateSessionMeta(sessions);
    });
  } catch (error) {
    $("#agent-dot").className = "dot offline";
    $("#agent-status").textContent = "本机 Agent 未连接";
    $("#agent-detail").textContent = "请先启动 127.0.0.1:18010";
    $("#session-select").innerHTML = '<option value="">无法读取会话</option>';
    message(error.message, "error");
  }
}

function updateSessionMeta(sessions) {
  const session = sessions.find((item) => item.id === $("#session-select").value);
  $("#session-meta").textContent = session
    ? `Base：${session.base_locations.join("、") || "未设置"}；明文不写入插件存储。`
    : "请先在本机简历助手中建立一份简历。";
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("无法访问当前标签页");
  currentTabId = tab.id;
  return tab;
}

async function refreshPermissionStatus() {
  const badge = $('#permission-badge');
  const grant = $('#grant-site-button');
  const revoke = $('#revoke-site-button');
  try {
    const tab = await activeTab();
    if (!tab.url || !tab.url.startsWith("http")) {
      throw new Error("请先切换到招聘网站页面");
    }
    const state = await ResumeCopilotPermissions.inspect(chrome, tab.url, API);
    const { pattern, origin, fixed, granted } = state;
    currentSitePermission = state;
    $('#site-origin').textContent = origin;
    $('#site-dot').className = `ledger-dot ${granted ? 'granted' : ''}`;
    if (fixed) {
      badge.textContent = '本机固定授权';
      badge.className = 'badge granted';
      $('#site-access-label').textContent = '当前页：本机固定授权';
      grant.textContent = '助手服务页已经授权';
      grant.disabled = true;
      revoke.hidden = true;
    } else if (granted) {
      badge.textContent = '当前站点已授权';
      badge.className = 'badge granted';
      $('#site-access-label').textContent = '当前页：持续访问已开启';
      grant.textContent = '当前招聘网站已经授权';
      grant.disabled = true;
      revoke.hidden = false;
    } else {
      badge.textContent = '临时访问';
      badge.className = 'badge temporary';
      $('#site-access-label').textContent = '当前页：仅本次点击临时访问';
      grant.textContent = '仅授权当前招聘网站';
      grant.disabled = false;
      revoke.hidden = true;
    }
  } catch (error) {
    currentSitePermission = null;
    badge.textContent = '不可授权';
    badge.className = 'badge neutral';
    $('#site-origin').textContent = error.message;
    $('#site-access-label').textContent = '当前页：不可扫描';
    grant.disabled = true;
    revoke.hidden = true;
  }
}

async function grantCurrentSite() {
  const button = $('#grant-site-button');
  setBusy(button, true, '等待浏览器确认…');
  try {
    if (!currentSitePermission?.origin) throw new Error('当前页面不可授权');
    // permissions.request must be invoked synchronously from the user click handler.
    const permissionRequest = ResumeCopilotPermissions.request(chrome, currentSitePermission.origin);
    const { granted } = await permissionRequest;
    if (!granted) throw new Error('浏览器未授予当前站点权限');
    await refreshPermissionStatus();
    message(`已只授权 ${currentSitePermission.origin}；其他网站不受影响。`, 'success');
    if (currentHandoff) {
      setTakeoverStatus(`${currentHandoff.company} · 站点已授权，AI 继续接管`, 'granted');
      await advanceAutomatedTakeover(currentHandoff);
    }
  } catch (error) {
    message(error.message, 'error');
  } finally {
    if (!button.disabled || !currentSitePermission?.granted) setBusy(button, false, '');
  }
}

async function revokeCurrentSite() {
  if (!currentSitePermission || currentSitePermission.fixed) return;
  const removed = await ResumeCopilotPermissions.remove(chrome, currentSitePermission.pattern);
  await refreshPermissionStatus();
  message(removed ? '已撤销当前招聘网站的持续权限。' : '当前网站没有可撤销的权限。', removed ? 'success' : '');
}

async function contentMessage(type, payload = {}) {
  const tab = await activeTab();
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["auth-utils.js", "journey-utils.js", "content.js", "auth-content.js", "journey-content.js", "submit-content.js"]
    });
  } catch (error) {
    throw new Error("当前页面不允许扫描；请点击“仅授权当前招聘网站”后重试");
  }
  return chrome.tabs.sendMessage(tab.id, { type, ...payload });
}

function authDialogMessage(text, kind = "") {
  const node = $("#auth-dialog-message");
  node.textContent = text;
  node.className = `message ${kind}`.trim();
}

function clearAuthSensitive() {
  $("#auth-otp").value = "";
  $("#auth-otp").disabled = true;
  $("#auth-consent-approval").checked = false;
  $("#auth-submit-approval").checked = false;
  authRelay = null;
}

function setAuthStep(step) {
  ["phone", "code", "continue"].forEach((name) => {
    $(`#auth-step-${name}`).classList.toggle("active", name === step);
  });
}

function refreshAuthButton() {
  if (!authRelay) return;
  const otpReady = !authRelay.requiresOtp || /^[0-9a-zA-Z]{4,10}$/.test($("#auth-otp").value.trim());
  const consentReady = !authRelay.inspection.consent_present || $("#auth-consent-approval").checked;
  const submitReady = !authRelay.handoff || $("#auth-submit-approval").checked;
  $("#complete-auth-button").disabled = !(authRelay.codeRequested && otpReady && consentReady && submitReady);
}

function setTakeoverStatus(text, kind = "neutral") {
  $("#takeover-status").textContent = text;
  const badge = $("#takeover-badge");
  badge.textContent = kind === "granted" ? "AI 接管中" : kind === "error" ? "已停止" : "请先打开副驾驶";
  badge.className = `badge ${kind === "granted" ? "granted" : kind === "error" ? "temporary" : "neutral"}`;
}

async function finishSimulationAtBoundary(handoff, tab, statusText) {
  await chrome.runtime.sendMessage({ type: "RC_FINISH_AI_TAKEOVER", tabId: tab.id });
  currentHandoff = null;
  setTakeoverStatus(statusText, "granted");
  message(`${statusText} 未向企业发送验证码、简历字段或投递请求。`, "success");
}

function waitForTabComplete(tabId, timeoutMs = 15000) {
  return chrome.tabs.get(tabId).then((tab) => {
    if (tab.status === "complete") return tab;
    return new Promise((resolve, reject) => {
      const finish = (error, readyTab) => {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timer);
        error ? reject(error) : resolve(readyTab);
      };
      const listener = (updatedId, changeInfo, updatedTab) => {
        if (updatedId === tabId && changeInfo.status === "complete") finish(null, updatedTab);
      };
      chrome.tabs.onUpdated.addListener(listener);
      const timer = setTimeout(() => finish(new Error("招聘官网加载超时")), timeoutMs);
    });
  });
}

function configureHandoffDialog(handoff, inspection, requiresOtp) {
  $("#auth-origin").textContent = `${handoff.company} · ${new URL(handoff.url).origin}`;
  $("#auth-account-warning").hidden = !inspection.may_create_account;
  $("#auth-otp-stage").hidden = !requiresOtp;
  $("#auth-consent-row").hidden = !inspection.consent_present;
  $("#auth-submit-row").hidden = false;
  $("#auth-submit-copy").textContent = `我确认由 AI 为“${handoff.company} / ${handoff.jobTitle || handoff.channelLabel || "已核验岗位"}”填写申请表，并在没有缺失字段、附件、人工声明或人机验证时点击最终提交。`;
  const policyLink = $("#auth-policy-link");
  if (inspection.consent_policy_url) {
    policyLink.href = inspection.consent_policy_url;
    policyLink.hidden = false;
  } else {
    policyLink.hidden = true;
    policyLink.removeAttribute("href");
  }
  $("#auth-otp").disabled = !requiresOtp;
  $("#complete-auth-button").dataset.label = requiresOtp ? "验证码登录并授权 AI 投递" : "授权 AI 填表并提交";
  $("#complete-auth-button").textContent = $("#complete-auth-button").dataset.label;
  $("#complete-auth-button").disabled = true;
  setAuthStep(requiresOtp ? "code" : "phone");
  authDialogMessage(
    requiresOtp
      ? "手机号已从本轮简历自动填入官网并触发验证码。收到短信后，请在这里填写。"
      : "当前官网没有登录验证码页。请确认本岗位后，由 AI 继续填表并尝试提交。",
    requiresOtp ? "success" : ""
  );
  if (!$("#auth-dialog").open) $("#auth-dialog").showModal();
  requiresOtp ? $("#auth-otp").focus() : $("#auth-submit-approval").focus();
}

async function analyzePageForSession(sessionId) {
  const scanned = await contentMessage("RC_SCAN_FORM");
  if (!scanned?.ok) throw new Error("官网表单扫描失败");
  const plan = await api("/api/browser/analyze", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, page: scanned.page, use_ai: true })
  });
  return { scanned, plan };
}

async function advanceAutomatedTakeover(handoff, depth = 0, finalAuthorized = false) {
  if (depth > 10) throw new Error("官网页面跳转超过安全上限，AI 已停止");
  const tab = await activeTab();
  if (tab.id !== handoff.tabId) throw new Error("AI 接管标签页已变化");
  await waitForTabComplete(tab.id);
  setTakeoverStatus(`正在核验 ${handoff.company} 的官网页面…`, "granted");
  const response = await contentMessage("RC_AUTH_INSPECT");
  if (!response?.ok) throw new Error(response?.error || "无法识别官网登录状态");
  const inspection = response.auth;
  if (inspection.captcha_present) throw new Error("官网出现人机验证，请在页面手动完成后重新发起");
  if (inspection.ambiguous) throw new Error("官网登录控件不唯一，AI 已停止");
  const isOtpAuth = inspection.otp_present || inspection.get_code_present;
  if (isOtpAuth) {
    if (handoff.simulationOnly) {
      return finishSimulationAtBoundary(handoff, tab, "官网预演已到登录 / 验证码页，合成档案安全停止");
    }
    if (!inspection.phone_present || !inspection.otp_present || !inspection.get_code_present || !inspection.continue_present) {
      throw new Error("官网认证控件不完整，AI 已停止");
    }
    const { plan } = await analyzePageForSession(handoff.sessionId);
    const phoneAction = plan.actions.find((action) => action.resume_field === "phone");
    if (!phoneAction?.value) throw new Error("本轮简历缺少可用手机号");
    const request = await chrome.tabs.sendMessage(tab.id, { type: "RC_AUTH_REQUEST_OTP", phone: phoneAction.value });
    phoneAction.value = "";
    if (!request?.ok) throw new Error(request?.error || "官网未接受验证码请求");
    authRelay = { tabId: tab.id, pageUrl: inspection.page_url, inspection, codeRequested: true, requiresOtp: true, handoff };
    configureHandoffDialog(handoff, inspection, true);
    return;
  }

  const journeyResponse = await contentMessage("RC_INSPECT_JOURNEY");
  if (!journeyResponse?.ok) throw new Error(journeyResponse?.error || "无法识别当前招聘页面");
  const state = journeyResponse.journey;
  if (state.stage === "offline") throw new Error("官网明确显示岗位已下线或停止招聘，AI 已停止");
  if (state.stage === "receipt") {
    await chrome.runtime.sendMessage({ type: "RC_FINISH_AI_TAKEOVER", tabId: tab.id });
    currentHandoff = null;
    setTakeoverStatus(`${handoff.company} 官网已显示投递成功回执`, "granted");
    message("官网成功回执已核验。", "success");
    return;
  }
  if (state.stage === "career_home") {
    setTakeoverStatus(`正在进入 ${handoff.company} 的官方职位列表…`, "granted");
    await triggerJourneyAction(tab, "RC_OPEN_LISTING");
    return advanceAutomatedTakeover(handoff, depth + 1, finalAuthorized);
  }
  if (state.stage === "job_listing") {
    setTakeoverStatus(`正在从 ${state.job_candidates.length} 个官网岗位中匹配简历…`, "granted");
    const selection = await api("/api/browser/rank-jobs", {
      method: "POST",
      body: JSON.stringify({ session_id: handoff.sessionId, page_url: state.page_url, candidates: state.job_candidates })
    });
    if (selection.selected_index === null || selection.selected_index === undefined || !selection.selected_url) {
      throw new Error(selection.rationale || "官网当前没有与简历足够匹配的在招岗位");
    }
    handoff.jobTitle = selection.selected_title || "官网在招岗位";
    handoff.jobUrl = selection.selected_url;
    setTakeoverStatus(`已核验在招岗位：${handoff.jobTitle}；正在打开详情…`, "granted");
    await triggerJourneyAction(tab, "RC_OPEN_JOB", { index: selection.selected_index, url: selection.selected_url });
    return advanceAutomatedTakeover(handoff, depth + 1, finalAuthorized);
  }
  if (state.stage === "job_detail") {
    if (!handoff.jobTitle) handoff.jobTitle = state.title || "官网岗位详情";
    setTakeoverStatus(`岗位详情在线，正在进入正式申请页…`, "granted");
    await triggerJourneyAction(tab, "RC_OPEN_APPLICATION");
    return advanceAutomatedTakeover(handoff, depth + 1, finalAuthorized);
  }
  if (state.stage === "application_form") {
    if (handoff.simulationOnly) {
      const { plan } = await analyzePageForSession(handoff.sessionId);
      renderPlan(plan, { allowFill: false });
      return finishSimulationAtBoundary(handoff, tab, "官网预演已到正式申请页并完成字段预检，合成档案安全停止");
    }
    if (finalAuthorized) return runAutonomousApplication(handoff);
    authRelay = {
      tabId: tab.id,
      pageUrl: state.page_url,
      inspection: { ...inspection, consent_present: false },
      codeRequested: true,
      requiresOtp: false,
      handoff
    };
    configureHandoffDialog(handoff, authRelay.inspection, false);
    return;
  }
  throw new Error(`无法确认当前页是职位列表、岗位详情或申请表，AI 已停止：${state.title || state.page_url}`);
}

async function triggerJourneyAction(tab, type, payload = {}) {
  const initialUrl = tab.url;
  const response = await chrome.tabs.sendMessage(tab.id, { type, ...payload });
  if (!response?.ok) throw new Error(response?.error || "官网页面操作失败");
  await new Promise((resolve) => setTimeout(resolve, 1000));
  const current = await chrome.tabs.get(tab.id);
  if (current.status !== "complete") await waitForTabComplete(tab.id);
  else if (current.url === initialUrl) await new Promise((resolve) => setTimeout(resolve, 700));
}

async function consumePendingTakeover() {
  try {
    const tab = await activeTab();
    const response = await chrome.runtime.sendMessage({ type: "RC_GET_AI_TAKEOVER", tabId: tab.id });
    if (!response?.ok || !response.handoff) return;
    currentHandoff = response.handoff;
    const select = $("#session-select");
    if (Array.from(select.options).some((option) => option.value === currentHandoff.sessionId)) {
      select.value = currentHandoff.sessionId;
      await chrome.storage.local.set({ resumeCopilotSessionId: currentHandoff.sessionId });
    } else {
      throw new Error("AI 投递任务对应的简历会话已失效");
    }
    if (!currentSitePermission?.fixed && !currentSitePermission?.granted) {
      setTakeoverStatus(`${currentHandoff.company} · 等待当前站点授权`);
      message("请点击“仅授权当前招聘网站”；授权后 AI 会继续当前投递任务。", "");
      return;
    }
    if (currentHandoff.simulationOnly) {
      setTakeoverStatus(`${currentHandoff.company} · 合成档案官网安全预演`, "granted");
      message("只核验岗位并前往登录页或申请页；不会发送验证码、填入字段或最终提交。", "success");
    }
    await advanceAutomatedTakeover(currentHandoff);
  } catch (error) {
    setTakeoverStatus(error.message, "error");
    message(error.message, "error");
  }
}

async function runAutonomousApplication(handoff) {
  if (handoff.simulationOnly) throw new Error("合成档案只允许官网预演，禁止填表和最终提交");
  setTakeoverStatus(`AI 正在填写 ${handoff.company} 的申请表…`, "granted");
  const { plan } = await analyzePageForSession(handoff.sessionId);
  renderPlan(plan);
  const tab = await activeTab();
  if (tab.id !== handoff.tabId) throw new Error("投递标签页已变化");
    const fillResponse = await chrome.tabs.sendMessage(tab.id, { type: "RC_APPLY_PLAN", actions: plan.actions });
  if (!fillResponse?.ok) throw new Error("官网拒绝 AI 填表");

  // ─── 自动导出 Word 并上传附件 ───
  try {
    const { filled } = fillResponse.result;
    if (filled.length > 0) {
      const result = await exportWordResume();
      if (result) {
        const { blob, filename } = result;
        const uploadResult = await autoUploadResume(blob, filename);
        if (!uploadResult.success) {
          message("简历已生成，但自动上传未完成，请手动上传。", "");
        }
      }
    }
  } catch (error) {
    message(`自动导出/上传跳过：${error.message}`, "");
  }

  const inspection = await chrome.tabs.sendMessage(tab.id, { type: "RC_INSPECT_SUBMISSION" });
  if (!inspection?.ok) throw new Error("无法执行投递前检查");
  const state = inspection.submission;
  if (state.captcha_present) throw new Error("官网出现人机验证，AI 已停止");
  if (state.blockers.length) {
    const labels = state.blockers.slice(0, 4).map((item) => item.label).join("、");
    throw new Error(`仍需人工补齐：${labels}`);
  }
  if (state.submit_button_count !== 1 || !state.submit_button_enabled) {
    throw new Error("当前页不是可直接提交的申请表，或官网投递按钮尚未启用");
  }
  const submitted = await chrome.tabs.sendMessage(tab.id, {
    type: "RC_SUBMIT_APPLICATION",
    authorization: handoff.takeoverId,
    simulationOnly: handoff.simulationOnly === true
  });
  if (!submitted?.ok) throw new Error(submitted?.error || "官网拒绝最终投递");
  await chrome.runtime.sendMessage({ type: "RC_FINISH_AI_TAKEOVER", tabId: tab.id });
  currentHandoff = null;
  setAuthStep("continue");
  await new Promise((resolve) => setTimeout(resolve, 1200));
  const current = await chrome.tabs.get(tab.id);
  if (current.status !== "complete") await waitForTabComplete(tab.id);
  const receipt = await contentMessage("RC_INSPECT_JOURNEY");
  if (receipt?.ok && receipt.journey.stage === "receipt") {
    setTakeoverStatus(`${handoff.company} 官网已显示投递成功回执`, "granted");
    message("官网成功回执已核验。", "success");
  } else {
    setTakeoverStatus(`已点击 ${handoff.company} 官网最终提交；回执尚未确认`, "granted");
    message("已触发官网最终提交，但尚未检测到成功回执，请以官网结果为准。", "");
  }
}

function waitForNavigation(tabId, initialUrl, timeoutMs = 15000) {
  return new Promise((resolve) => {
    let finished = false;
    const done = (result) => {
      if (finished) return;
      finished = true;
      chrome.tabs.onUpdated.removeListener(listener);
      clearTimeout(timer);
      resolve(result);
    };
    const listener = (updatedId, changeInfo, tab) => {
      if (updatedId !== tabId) return;
      if (changeInfo.url && changeInfo.url !== initialUrl) done({ navigated: true, tab });
      else if (changeInfo.status === "complete" && tab.url !== initialUrl) done({ navigated: true, tab });
    };
    chrome.tabs.onUpdated.addListener(listener);
    const timer = setTimeout(() => done({ navigated: false }), timeoutMs);
  });
}

async function completeAuth() {
  const button = $("#complete-auth-button");
  const otp = $("#auth-otp").value.trim();
  const allowConsent = $("#auth-consent-approval").checked;
  const allowSubmit = $("#auth-submit-approval").checked;
  const relay = authRelay;
  if (!relay?.handoff || !allowSubmit) return authDialogMessage("请先确认本企业、本渠道的 AI 最终投递授权。", "error");
  if (relay.handoff.simulationOnly) return authDialogMessage("合成档案只允许官网预演，不能登录、填表或提交。", "error");
  setBusy(button, true, relay.requiresOtp ? "正在登录并等待跳转…" : "正在填表与投递…");
  try {
    const tab = await activeTab();
    if (tab.id !== relay.tabId || tab.url !== relay.pageUrl) throw new Error("认证标签页已变化，请关闭后重新开始");
    if (relay.requiresOtp) {
      const navigation = waitForNavigation(tab.id, tab.url);
      const response = await chrome.tabs.sendMessage(tab.id, { type: "RC_AUTH_COMPLETE", otp, allowConsent });
      $("#auth-otp").value = "";
      if (!response?.ok) throw new Error(response?.error || "招聘网站未接受登录请求");
      setAuthStep("continue");
      authDialogMessage("已触发登录，正在等待招聘网站进入下一页…", "success");
      const result = await navigation;
      if (!result.navigated) {
        authDialogMessage("页面尚未跳转。请查看官网是否提示验证码错误或需要手工操作。", "error");
        return;
      }
      await waitForTabComplete(tab.id);
    }
    $("#auth-dialog").close();
    clearAuthSensitive();
    message("授权已确认；AI 正在扫描、填写并检查最终投递条件。", "success");
    await refreshPermissionStatus();
    await advanceAutomatedTakeover(relay.handoff, 0, true);
  } catch (error) {
    authDialogMessage(error.message, "error");
    setTakeoverStatus(error.message, "error");
    message(error.message, "error");
  } finally {
    setBusy(button, false, "");
    refreshAuthButton();
  }
}

function renderPlan(plan, { allowFill = true } = {}) {
  currentPlan = plan;
  currentPlanWriteAllowed = allowFill;
  $("#plan-section").hidden = false;
  $("#fill-count").textContent = plan.actions.length;
  $("#skip-count").textContent = plan.skipped.length;
  $("#ai-badge").textContent = plan.ai_mapping_used ? "AI + 规则" : "安全规则";
  $("#action-list").innerHTML = plan.actions.length
    ? plan.actions.map((action) => `<div class="action"><div><strong>${escapeHtml(action.rationale)}</strong><br><code>${escapeHtml(action.resume_field)}</code></div><span class="preview">${escapeHtml(action.masked_preview)}</span></div>`).join("")
    : '<p class="hint">没有可安全自动填写的字段。</p>';
  $("#skip-list").innerHTML = plan.skipped.length
    ? plan.skipped.map((item) => `<div class="skip"><strong>${escapeHtml(item.label)}</strong><br>${escapeHtml(item.reason)}</div>`).join("")
    : '<p class="hint">无跳过项。</p>';
  $("#fill-button").disabled = !allowFill || plan.actions.length === 0;
  $("#fill-button").textContent = allowFill ? "填入当前页的空白字段" : "合成官网预演不填入字段";
  $("#highlight-button").disabled = plan.actions.length === 0;
}

async function scan() {
  const button = $("#scan-button");
  const sessionId = $("#session-select").value;
  if (!sessionId) return message("请先在简历助手中建立并选择简历。", "error");
  setBusy(button, true, "正在扫描与映射…");
  message("只读取字段结构，不读取页面中已填写的内容。", "");
  try {
    const scanned = await contentMessage("RC_SCAN_FORM");
    if (!scanned?.ok) throw new Error("页面扫描失败");
    const plan = await api("/api/browser/analyze", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, page: scanned.page, use_ai: $("#use-ai").checked })
    });
    renderPlan(plan);
    message(`已检查 ${scanned.page.fields.length} 个字段；请先复核预检单。`, "success");
  } catch (error) {
    message(error.message, "error");
  } finally {
    setBusy(button, false, "");
  }
}

async function fill() {
  const button = $("#fill-button");
  if (!currentPlanWriteAllowed) return message("合成官网预演只显示字段预检，不会把虚构资料写入企业页面。", "error");
  if (!currentPlan) return;
  setBusy(button, true, "正在填入…");
  try {
    const tab = await activeTab();
    if (tab.id !== currentTabId) throw new Error("当前标签页已变化，请重新扫描");
    const response = await chrome.tabs.sendMessage(tab.id, { type: "RC_APPLY_PLAN", actions: currentPlan.actions });
    if (!response?.ok) throw new Error("页面拒绝填入");
    const { filled, skipped } = response.result;
        message(`已填入 ${filled.length} 项，现场跳过 ${skipped.length} 项。请人工复核；没有提交。`, "success");
    if (filled.length > 0) {
      const result = await exportWordResume();
      if (result) {
        const { blob, filename } = result;
        showUploadConfirm(filename);
        window.__pendingResumeUpload = { blob, filename };
        return;
      }
    }
  } catch (error) {
    message(error.message, "error");
  } finally {
    setBusy(button, false, "");
  }
}

async function highlight() {
  const button = $('#highlight-button');
  if (!currentPlan) return;
  setBusy(button, true, '正在标记…');
  try {
    const tab = await activeTab();
    if (tab.id !== currentTabId) throw new Error('当前标签页已变化，请重新扫描');
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: 'RC_HIGHLIGHT_PLAN', actions: currentPlan.actions
    });
    if (!response?.ok) throw new Error('页面拒绝标记');
    message(`已标记 ${response.result.highlighted.length} 个待填字段；尚未写入任何内容。`, 'success');
  } catch (error) {
    message(error.message, 'error');
  } finally {
    setBusy(button, false, '');
  }
}

$("#scan-button").addEventListener("click", scan);
$("#fill-button").addEventListener("click", fill);
$("#highlight-button").addEventListener("click", highlight);
$("#grant-site-button").addEventListener("click", grantCurrentSite);
$("#revoke-site-button").addEventListener("click", revokeCurrentSite);
$("#complete-auth-button").addEventListener("click", completeAuth);
$("#auth-otp").addEventListener("input", refreshAuthButton);
$("#auth-consent-approval").addEventListener("change", refreshAuthButton);
$("#auth-submit-approval").addEventListener("change", refreshAuthButton);
$("#auth-dialog").addEventListener("close", clearAuthSensitive);
$("#export-word-button").addEventListener("click", async () => {
  const result = await exportWordResume();
  if (result) {
    const { blob, filename } = result;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
    message(`已下载 ${filename}`, "success");
  }
});
$("#upload-resume-button").addEventListener("click", uploadResumeAttachment);
$("#upload-confirm-yes").addEventListener("click", async () => {
  hideUploadConfirm();
  const pending = window.__pendingResumeUpload;
  if (pending) {
    await autoUploadResume(pending.blob, pending.filename);
    window.__pendingResumeUpload = null;
  }
});
$("#upload-confirm-no").addEventListener("click", () => {
  hideUploadConfirm();
  message("已跳过上传简历附件；请在官网页面人工复核。", "");
});
(async () => {
  await Promise.allSettled([loadAgent(), refreshPermissionStatus()]);
  await consumePendingTakeover();
})();
