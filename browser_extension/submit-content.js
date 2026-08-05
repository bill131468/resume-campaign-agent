(() => {
  if (globalThis.__resumeCopilotSubmitV5Loaded) return;
  globalThis.__resumeCopilotSubmitV5Loaded = true;

  const auth = globalThis.ResumeCopilotAuth;
  if (!auth) return;
  const visible = (element) => Boolean(element && element.getClientRects().length);

  function labelText(element) {
    const direct = Array.from(element.labels || []).map((label) => label.innerText).join(" ");
    return [
      direct,
      element.closest("label")?.innerText,
      element.getAttribute("aria-label"),
      element.placeholder,
      element.name,
      element.id
    ].filter(Boolean).join(" ").replace(/\s+/g, " ").trim().slice(0, 180);
  }

  function controlText(element) {
    return [element.innerText, element.value, element.getAttribute("aria-label"), element.title, element.name, element.id]
      .filter(Boolean).join(" ");
  }

  function captchaPresent() {
    const clues = Array.from(document.querySelectorAll("iframe, img, [class], [id]")).slice(0, 500);
    if (clues.some((element) => auth.isCaptchaText([
      element.id,
      element.className,
      element.getAttribute?.("src"),
      element.getAttribute?.("title"),
      element.getAttribute?.("alt")
    ].join(" ")))) return true;
    return auth.isCaptchaText(document.body?.innerText || "");
  }

  function valueMissing(element) {
    if (element.type === "checkbox" || element.type === "radio") return !element.checked;
    return !String(element.value || "").trim();
  }

  function blockers() {
    const result = [];
    const controls = Array.from(document.querySelectorAll("input, textarea, select")).slice(0, 500);
    for (const element of controls) {
      if (!visible(element) || element.disabled || ["hidden", "submit", "button"].includes(element.type)) continue;
      if (element.type === "file") {
        result.push({ label: labelText(element) || "附件上传", reason: "需要人工选择本机文件" });
        continue;
      }
      const consent = element.type === "checkbox" && /同意|声明|隐私|协议|consent|agreement/.test(auth.normalizeText(labelText(element)));
      if ((element.required || element.getAttribute("aria-required") === "true" || consent) && valueMissing(element)) {
        result.push({ label: labelText(element) || "必填字段", reason: consent ? "同意/声明项需要人工处理" : "必填字段仍为空" });
      }
    }
    return result.slice(0, 30);
  }

  function submitCandidates() {
    return Array.from(document.querySelectorAll('button, input[type="submit"], [role="button"]'))
      .filter(visible)
      .filter((element) => auth.isFinalSubmitText(controlText(element)));
  }

  function inspectSubmit() {
    const missing = blockers();
    const candidates = submitCandidates();
    return {
      page_url: location.href,
      captcha_present: captchaPresent(),
      blockers: missing,
      submit_button_count: candidates.length,
      submit_button_enabled: candidates.length === 1 && !candidates[0].disabled && candidates[0].getAttribute("aria-disabled") !== "true"
    };
  }

  function submitApplication(authorization, simulationOnly = false) {
    if (simulationOnly) throw new Error("合成档案官网预演禁止最终提交");
    if (typeof authorization !== "string" || authorization.length < 8) throw new Error("缺少逐岗位提交授权");
    const state = inspectSubmit();
    if (state.captcha_present) throw new Error("页面出现人机验证，AI 已停止");
    if (state.blockers.length) throw new Error("页面仍有必填或人工声明项，AI 已停止");
    const visibleFields = Array.from(document.querySelectorAll("input, textarea, select"))
      .filter((element) => visible(element) && !["hidden", "submit", "button", "password"].includes(String(element.type || "").toLowerCase()));
    if (!visibleFields.length) throw new Error("当前页没有可核验的申请表字段，AI 已停止");
    const candidates = submitCandidates();
    if (candidates.length !== 1) throw new Error(candidates.length ? "页面存在多个投递按钮，AI 已停止" : "未找到唯一的投递按钮");
    const button = candidates[0];
    if (button.disabled || button.getAttribute("aria-disabled") === "true") throw new Error("官网投递按钮尚未启用");
    button.click();
    return { triggered: true, action: "submit_application", page_url: location.href };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === "RC_INSPECT_SUBMISSION") {
      sendResponse({ ok: true, submission: inspectSubmit() });
      return false;
    }
    if (message?.type === "RC_SUBMIT_APPLICATION") {
      try {
        sendResponse({ ok: true, result: submitApplication(message.authorization, message.simulationOnly === true) });
      } catch (error) {
        sendResponse({ ok: false, error: error.message || "投递失败", submission: inspectSubmit() });
      }
      return false;
    }
    return undefined;
  });
})();
