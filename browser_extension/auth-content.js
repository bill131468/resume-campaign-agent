(() => {
  if (globalThis.__resumeCopilotAuthV3Loaded) return;
  globalThis.__resumeCopilotAuthV3Loaded = true;

  const auth = globalThis.ResumeCopilotAuth;
  if (!auth) return;

  const visible = (element) => Boolean(element && element.getClientRects().length);

  function labelText(element) {
    const labels = element.labels ? Array.from(element.labels).map((item) => item.innerText) : [];
    const wrapping = element.closest("label")?.innerText || "";
    const ariaLabelledBy = (element.getAttribute("aria-labelledby") || "")
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => document.getElementById(id)?.innerText || "");
    return [
      ...labels,
      wrapping,
      ...ariaLabelledBy,
      element.getAttribute("aria-label"),
      element.placeholder,
      element.name,
      element.id,
      element.autocomplete
    ].filter(Boolean).join(" ");
  }

  function controlText(element) {
    return [
      element.innerText,
      element.value,
      element.getAttribute("aria-label"),
      element.title,
      element.name,
      element.id
    ].filter(Boolean).join(" ");
  }

  function unique(items, description) {
    const matches = Array.from(new Set(items.filter(visible)));
    if (matches.length !== 1) {
      throw new Error(matches.length ? `${description}存在多个候选项，已停止操作` : `未找到唯一的${description}`);
    }
    return matches[0];
  }

  function phoneCandidates() {
    return Array.from(document.querySelectorAll('input:not([type="password"]):not([type="hidden"])'))
      .filter((element) => element.type === "tel" || auth.isPhoneText(labelText(element)));
  }

  function otpCandidates() {
    return Array.from(document.querySelectorAll('input:not([type="password"]):not([type="hidden"])'))
      .filter((element) => auth.isOtpText(labelText(element)));
  }

  function buttonCandidates(predicate) {
    return Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"], [role="button"]'))
      .filter((element) => predicate(controlText(element)));
  }

  function consentCandidates() {
    return Array.from(document.querySelectorAll('input[type="checkbox"]'))
      .filter((element) => /隐私|个人信息|用户协议|privacy|consent|agreement|同意/.test(auth.normalizeText(labelText(element))));
  }

  function captchaPresent() {
    if (Array.from(document.querySelectorAll("iframe, img, [class], [id]")).some((element) => {
      const clue = [element.id, element.className, element.getAttribute?.("src"), element.getAttribute?.("title"), element.getAttribute?.("alt")].join(" ");
      return auth.isCaptchaText(clue);
    })) return true;
    return auth.isCaptchaText(document.body?.innerText || "");
  }

  function setNativeValue(element, value) {
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (!setter) throw new Error("当前输入框不支持安全写入");
    setter.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function waitUntilEnabled(element, timeoutMs = 2000) {
    if (!element.disabled && element.getAttribute("aria-disabled") !== "true") return Promise.resolve();
    return new Promise((resolve, reject) => {
      const finish = (error) => {
        observer.disconnect();
        clearTimeout(timer);
        error ? reject(error) : resolve();
      };
      const observer = new MutationObserver(() => {
        if (!element.disabled && element.getAttribute("aria-disabled") !== "true") finish();
      });
      observer.observe(element, { attributes: true, attributeFilter: ["disabled", "aria-disabled"] });
      const timer = setTimeout(() => finish(new Error("官网按钮仍未启用，请在页面手动检查")), timeoutMs);
    });
  }

  function inspect() {
    const phone = phoneCandidates().filter(visible);
    const otp = otpCandidates().filter(visible);
    const code = buttonCandidates(auth.isGetCodeText);
    const consent = consentCandidates().filter(visible);
    const next = buttonCandidates(auth.isContinueText);
    const consentElement = consent.length === 1 ? consent[0] : null;
    const policyLink = consentElement?.closest("label")?.querySelector("a[href]") || document.querySelector('a[href*="privacy"], a[href*="policy"]');
    return {
      page_url: location.href,
      title: document.title,
      phone_present: phone.length === 1,
      otp_present: otp.length === 1,
      get_code_present: code.length === 1,
      consent_present: consent.length === 1,
      consent_label: consentElement ? auth.normalizeText(labelText(consentElement)).slice(0, 160) : "",
      consent_policy_url: policyLink?.href || "",
      continue_present: next.length === 1,
      captcha_present: captchaPresent(),
      may_create_account: /未注册.*(创建|注册)|自动创建账号|create.*account/.test(auth.normalizeText(document.body?.innerText || "")),
      ambiguous: phone.length > 1 || otp.length > 1 || code.length > 1 || consent.length > 1 || next.length > 1
    };
  }

  async function requestOtp(phone) {
    if (captchaPresent()) throw new Error("页面出现人机验证，请在招聘网站中手动完成");
    if (!auth.validatePhone(phone)) throw new Error("手机号格式不正确");
    const phoneField = unique(phoneCandidates(), "手机号输入框");
    const codeButton = unique(buttonCandidates(auth.isGetCodeText), "获取验证码按钮");
    setNativeValue(phoneField, String(phone).trim());
    await waitUntilEnabled(codeButton);
    codeButton.click();
    return { triggered: true, action: "request_otp" };
  }

  async function completeAuth(otp, allowConsent) {
    if (captchaPresent()) throw new Error("页面出现人机验证，请在招聘网站中手动完成");
    if (!auth.validateOtp(otp)) throw new Error("验证码应为 4–10 位数字或字母");
    const otpField = unique(otpCandidates(), "验证码输入框");
    setNativeValue(otpField, String(otp).trim());
    const consents = consentCandidates().filter(visible);
    if (consents.length > 1) throw new Error("页面存在多个同意项，请手动处理");
    if (consents.length === 1 && !consents[0].checked) {
      if (!allowConsent) throw new Error("需要你先在副驾驶中明确授权隐私同意项");
      consents[0].click();
      if (!consents[0].checked) throw new Error("隐私同意项未能勾选，请在页面手动处理");
    }
    const continueButton = unique(buttonCandidates(auth.isContinueText), "登录或继续按钮");
    if (auth.isApplicationSubmitText(controlText(continueButton))) throw new Error("检测到投递提交按钮，已停止操作");
    await waitUntilEnabled(continueButton);
    continueButton.click();
    return { triggered: true, action: "login_or_continue" };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!String(message?.type || "").startsWith("RC_AUTH_")) return undefined;
    const operation = Promise.resolve().then(async () => {
      if (message.type === "RC_AUTH_INSPECT") return { auth: inspect() };
      if (message.type === "RC_AUTH_REQUEST_OTP") return { result: await requestOtp(message.phone) };
      if (message.type === "RC_AUTH_COMPLETE") return { result: await completeAuth(message.otp, message.allowConsent === true) };
      throw new Error("未知认证命令");
    });
    operation
      .then((payload) => sendResponse({ ok: true, ...payload }))
      .catch((error) => sendResponse({ ok: false, error: error.message || "认证接力失败" }));
    return true;
  });
})();
