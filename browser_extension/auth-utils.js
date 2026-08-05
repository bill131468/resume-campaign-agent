(function (root, factory) {
  const api = factory();
  root.ResumeCopilotAuth = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  function isPhoneText(value) {
    return /手机号|手机号码|联系电话|移动电话|mobile|phone|tel/.test(normalizeText(value));
  }

  function isOtpText(value) {
    return /短信验证码|手机验证码|动态码|一次性密码|one.?time|verification.?code|otp|sms.?code/.test(normalizeText(value));
  }

  function isGetCodeText(value) {
    return /获取验证码|发送验证码|发送短信|获取短信|send.?code|get.?code|request.?code/.test(normalizeText(value));
  }

  function isOpenApplicationText(value) {
    return /^(立即)?投递(简历|该职位|该岗位)?$|^(立即)?申请(职位|岗位|该职位|该岗位)?$|^apply( now)?$|^apply to this job$/.test(normalizeText(value));
  }

  function isFinalSubmitText(value) {
    return /提交申请|确认提交|确认投递|提交简历|确认申请|submit.?application|send.?application/.test(normalizeText(value));
  }

  function isApplicationSubmitText(value) {
    return isOpenApplicationText(value) || isFinalSubmitText(value);
  }

  function isContinueText(value) {
    const text = normalizeText(value);
    if (isApplicationSubmitText(text) || isGetCodeText(text)) return false;
    return /登录|登入|创建账号|注册并登录|继续|下一步|sign.?in|log.?in|continue|next/.test(text);
  }

  function isCaptchaText(value) {
    return /图形验证码|图片验证码|人机验证|安全验证|滑块验证|拼图验证|captcha|recaptcha|hcaptcha/.test(normalizeText(value));
  }

  function validatePhone(value) {
    const text = String(value || "").trim();
    if (!/^\+?[0-9][0-9\s-]{5,19}$/.test(text)) return false;
    const digits = text.replace(/\D/g, "");
    return digits.length >= 6 && digits.length <= 15;
  }

  function validateOtp(value) {
    return /^[0-9a-zA-Z]{4,10}$/.test(String(value || "").trim());
  }

  return {
    normalizeText,
    isPhoneText,
    isOtpText,
    isGetCodeText,
    isOpenApplicationText,
    isFinalSubmitText,
    isApplicationSubmitText,
    isContinueText,
    isCaptchaText,
    validatePhone,
    validateOtp
  };
});
