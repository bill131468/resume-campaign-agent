const authElements = {
  tabs: document.querySelector("#authTabs"),
  smsTab: document.querySelector("#smsTab"),
  passwordTab: document.querySelector("#passwordTab"),
  phoneForm: document.querySelector("#smsPhoneForm"),
  codeForm: document.querySelector("#smsCodeForm"),
  passwordForm: document.querySelector("#passwordLoginForm"),
  setupForm: document.querySelector("#passwordSetupForm"),
  error: document.querySelector("#authError"),
  step: document.querySelector("#stepLabel"),
  resend: document.querySelector("#resendCodeButton"),
};

let pendingPhone = "";
let resendTimer = null;

function showOnly(target, stepLabel, showTabs = true) {
  [authElements.phoneForm, authElements.codeForm, authElements.passwordForm, authElements.setupForm]
    .forEach((form) => { form.hidden = form !== target; });
  authElements.tabs.hidden = !showTabs;
  authElements.step.textContent = stepLabel;
  clearError();
}

function setMode(mode) {
  const smsMode = mode === "sms";
  authElements.smsTab.setAttribute("aria-selected", String(smsMode));
  authElements.passwordTab.setAttribute("aria-selected", String(!smsMode));
  showOnly(smsMode ? authElements.phoneForm : authElements.passwordForm, smsMode ? "手机验证" : "密码登录");
  const focusTarget = smsMode ? document.querySelector("#smsPhone") : document.querySelector("#loginPhone");
  focusTarget.focus();
}

async function authRequest(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const validationMessage = Array.isArray(payload?.detail)
      ? "请检查手机号、验证码或密码格式"
      : null;
    const error = new Error(payload?.error?.message || validationMessage || "请求失败，请稍后重试");
    error.retryAfterSeconds = payload?.error?.retryAfterSeconds;
    throw error;
  }
  return payload;
}

function validMainlandPhone(value) {
  const compact = value.replace(/[\s()-]/g, "").replace(/^\+?86/, "");
  return /^1[3-9][0-9]{9}$/.test(compact);
}

function setBusy(button, busy, busyLabel) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? busyLabel : button.dataset.label;
}

function showError(message) {
  authElements.error.textContent = message;
  authElements.error.hidden = false;
}

function clearError() {
  authElements.error.textContent = "";
  authElements.error.hidden = true;
}

function maskedPhone(phone) {
  const digits = phone.replace(/\D/g, "").slice(-11);
  return digits.length === 11 ? `${digits.slice(0, 3)} ${digits.slice(3, 7)} ${digits.slice(7)}` : phone;
}

function startResendCountdown(seconds) {
  if (resendTimer) window.clearInterval(resendTimer);
  let remaining = Number(seconds) || 60;
  authElements.resend.disabled = true;
  authElements.resend.textContent = `${remaining} 秒后重发`;
  resendTimer = window.setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      window.clearInterval(resendTimer);
      resendTimer = null;
      authElements.resend.disabled = false;
      authElements.resend.textContent = "重新发送";
      return;
    }
    authElements.resend.textContent = `${remaining} 秒后重发`;
  }, 1000);
}

async function requestCode() {
  const button = document.querySelector("#sendCodeButton");
  const phone = document.querySelector("#smsPhone").value.trim();
  if (!validMainlandPhone(phone)) {
    showError("请输入有效的中国大陆手机号");
    return;
  }
  setBusy(button, true, "正在发送...");
  clearError();
  try {
    const result = await authRequest("/api/auth/sms/request", { phone });
    pendingPhone = phone;
    document.querySelector("#verifiedPhone").textContent = maskedPhone(phone);
    showOnly(authElements.codeForm, "输入验证码");
    startResendCountdown(result.retryAfterSeconds);
    document.querySelector("#smsCode").focus();
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false, "");
  }
}

async function verifyCode() {
  const button = document.querySelector("#verifyCodeButton");
  const code = document.querySelector("#smsCode").value.trim();
  if (!/^[0-9]{6}$/.test(code)) {
    showError("请输入 6 位数字验证码");
    return;
  }
  setBusy(button, true, "正在核验...");
  clearError();
  try {
    const result = await authRequest("/api/auth/sms/verify", { phone: pendingPhone, code });
    if (result.status === "password_required") {
      document.querySelector("#setupUsername").value = pendingPhone;
      showOnly(authElements.setupForm, "创建密码", false);
      document.querySelector("#newPassword").focus();
      return;
    }
    window.location.assign("/");
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false, "");
  }
}

async function resendCode() {
  clearError();
  try {
    const result = await authRequest("/api/auth/sms/request", { phone: pendingPhone });
    startResendCountdown(result.retryAfterSeconds);
  } catch (error) {
    showError(error.message);
    if (error.retryAfterSeconds) startResendCountdown(error.retryAfterSeconds);
  }
}

async function loginWithPassword() {
  const button = document.querySelector("#passwordLoginButton");
  const phone = document.querySelector("#loginPhone").value.trim();
  const password = document.querySelector("#loginPassword").value;
  if (!validMainlandPhone(phone) || !password) {
    showError("请输入有效的手机号和登录密码");
    return;
  }
  setBusy(button, true, "正在登录...");
  clearError();
  try {
    await authRequest("/api/auth/password/login", { phone, password });
    window.location.assign("/");
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false, "");
  }
}

async function setupPassword() {
  const button = document.querySelector("#setupPasswordButton");
  const password = document.querySelector("#newPassword").value;
  const passwordConfirmation = document.querySelector("#confirmPassword").value;
  if (password !== passwordConfirmation) {
    showError("两次输入的密码不一致");
    return;
  }
  setBusy(button, true, "正在创建...");
  clearError();
  try {
    await authRequest("/api/auth/password/setup", {
      password,
      password_confirmation: passwordConfirmation,
    });
    window.location.assign("/");
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(button, false, "");
  }
}

authElements.smsTab.addEventListener("click", () => setMode("sms"));
authElements.passwordTab.addEventListener("click", () => setMode("password"));
document.querySelector("#useSmsButton").addEventListener("click", () => setMode("sms"));
document.querySelector("#changePhoneButton").addEventListener("click", () => setMode("sms"));
authElements.resend.addEventListener("click", resendCode);
authElements.phoneForm.addEventListener("submit", (event) => { event.preventDefault(); requestCode(); });
authElements.codeForm.addEventListener("submit", (event) => { event.preventDefault(); verifyCode(); });
authElements.passwordForm.addEventListener("submit", (event) => { event.preventDefault(); loginWithPassword(); });
authElements.setupForm.addEventListener("submit", (event) => { event.preventDefault(); setupPassword(); });
document.querySelector("#showLoginPassword").addEventListener("change", (event) => {
  document.querySelector("#loginPassword").type = event.target.checked ? "text" : "password";
});
document.querySelector("#showSetupPassword").addEventListener("change", (event) => {
  const type = event.target.checked ? "text" : "password";
  document.querySelector("#newPassword").type = type;
  document.querySelector("#confirmPassword").type = type;
});
