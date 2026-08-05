(function (root, factory) {
  const api = factory();
  root.ResumeCopilotJourney = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  const folded = (value) => clean(value).toLowerCase();

  function isClosedText(value) {
    return /职位已下线|岗位已下线|职位已关闭|招聘已结束|停止招聘|暂无此职位|job closed|position closed|no longer accepting|not available/.test(folded(value));
  }

  function isReceiptText(value) {
    return /投递成功|申请成功|提交成功|申请已提交|申请已进入|简历已投递|已收到(你的|您的)?申请|application (was )?received|application submitted|thank you for applying/.test(folded(value));
  }

  function isListingText(value) {
    return /^(全部)?职位(搜索|列表)?$|^招聘职位$|^热招职位$|^搜索职位$|^查看(全部)?职位$|^工作机会$|^加入我们$|^jobs?$|^open positions$|^view (all )?jobs$|^career opportunities$/.test(folded(value));
  }

  function isJobHref(value) {
    const text = folded(value);
    return /\/(job|jobs|position|positions|vacancy|opening)(\/|\?|$)/.test(text)
      || /\/(detail|apply)\/(\d{4,}|[a-z0-9_-]{8,})(\/|\?|$)/.test(text)
      || /[?&](job_?id|position_?id|jobid|positionid)=/.test(text);
  }

  function looksLikeApplicationUrl(value) {
    return /\/(apply|application|resume)(\/|\?|$)|[?&](apply|application)=/.test(folded(value));
  }

  return { clean, folded, isClosedText, isReceiptText, isListingText, isJobHref, looksLikeApplicationUrl };
});
