(() => {
  if (globalThis.__resumeCopilotJourneyV5Loaded) return;
  globalThis.__resumeCopilotJourneyV5Loaded = true;

  const auth = globalThis.ResumeCopilotAuth;
  const journey = globalThis.ResumeCopilotJourney;
  if (!auth || !journey) return;

  const visible = (element) => Boolean(element && element.getClientRects().length);
  const textOf = (element) => journey.clean([
    element?.innerText,
    element?.textContent,
    element?.getAttribute?.("aria-label"),
    element?.title
  ].filter(Boolean).join(" ")).slice(0, 600);
  const sameOrigin = (url) => {
    try { return new URL(url, location.href).origin === location.origin; } catch (_) { return false; }
  };

  function clickableElements() {
    return Array.from(document.querySelectorAll('a[href], button, [role="button"]')).filter(visible).slice(0, 1000);
  }

  function unique(items, description) {
    const matches = Array.from(new Set(items.filter(visible)));
    if (matches.length !== 1) {
      throw new Error(matches.length ? `${description}存在多个候选项，AI 已停止` : `未找到唯一的${description}`);
    }
    return matches[0];
  }

  function listingCandidates() {
    return clickableElements().filter((element) => journey.isListingText(textOf(element)));
  }

  function jobCandidates() {
    const seen = new Set();
    const result = [];
    for (const element of document.querySelectorAll('a[href]')) {
      if (!visible(element)) continue;
      const url = new URL(element.href, location.href).href;
      const title = textOf(element);
      if (!sameOrigin(url) || !journey.isJobHref(url) || title.length < 2 || journey.isClosedText(title)) continue;
      const key = `${url}|${title}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const container = element.closest('article, li, [class*="job" i], [class*="position" i], [class*="vacancy" i]');
      result.push({
        index: result.length,
        title: title.slice(0, 500),
        url,
        metadata: textOf(container || element.parentElement || element).slice(0, 1500)
      });
      if (result.length >= 80) break;
    }
    return result;
  }

  function openApplicationCandidates() {
    return clickableElements().filter((element) => auth.isOpenApplicationText(textOf(element)));
  }

  function ordinaryVisibleFields() {
    return Array.from(document.querySelectorAll('input, textarea, select')).filter((element) => {
      const type = String(element.type || "").toLowerCase();
      return visible(element) && !["hidden", "submit", "button", "password"].includes(type);
    });
  }

  function receiptPresent(bodyText) {
    if (/\/(success|receipt|confirmation)(\/|\?|#|$)/i.test(location.href)) return true;
    const evidence = Array.from(document.querySelectorAll('h1, h2, h3, [role="status"], [role="alert"], [class*="success" i], [class*="result" i]'))
      .filter(visible)
      .slice(0, 100)
      .some((element) => journey.isReceiptText(textOf(element)));
    return evidence || (bodyText.length < 1200 && journey.isReceiptText(bodyText));
  }

  function inspect() {
    const bodyText = journey.clean(document.body?.innerText || "").slice(0, 50000);
    const jobs = jobCandidates();
    const applicationButtons = openApplicationCandidates();
    const finalButtons = clickableElements().filter((element) => auth.isFinalSubmitText(textOf(element)));
    const fields = ordinaryVisibleFields();
    let stage = "unknown";
    if (receiptPresent(bodyText)) stage = "receipt";
    else if (journey.isClosedText(bodyText)) stage = "offline";
    else if ((journey.looksLikeApplicationUrl(location.href) && fields.length > 0) || (fields.length > 1 && finalButtons.length > 0)) stage = "application_form";
    else if (applicationButtons.length > 0) stage = "job_detail";
    else if (jobs.length > 0) stage = "job_listing";
    else if (listingCandidates().length > 0) stage = "career_home";
    return {
      stage,
      page_url: location.href,
      title: document.title,
      job_candidates: jobs,
      listing_button_count: listingCandidates().length,
      open_application_button_count: applicationButtons.length,
      final_submit_button_count: finalButtons.length,
      visible_field_count: fields.length
    };
  }

  function openListing() {
    const element = unique(listingCandidates(), "职位列表入口");
    element.click();
    return { triggered: true, action: "open_listing", page_url: location.href };
  }

  function openJob(index, expectedUrl) {
    const candidates = jobCandidates();
    const candidate = candidates.find((item) => item.index === Number(index));
    if (!candidate) throw new Error("AI 选择的岗位已经不在当前页面");
    if (expectedUrl && new URL(expectedUrl, location.href).href !== candidate.url) throw new Error("岗位链接已变化，AI 已停止");
    const anchors = Array.from(document.querySelectorAll('a[href]')).filter((element) => visible(element) && new URL(element.href, location.href).href === candidate.url);
    unique(anchors, "目标岗位链接").click();
    return { triggered: true, action: "open_job", title: candidate.title, url: candidate.url };
  }

  function openApplication() {
    const element = unique(openApplicationCandidates(), "申请入口");
    element.click();
    return { triggered: true, action: "open_application", page_url: location.href };
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    try {
      if (message?.type === "RC_INSPECT_JOURNEY") sendResponse({ ok: true, journey: inspect() });
      else if (message?.type === "RC_OPEN_LISTING") sendResponse({ ok: true, result: openListing() });
      else if (message?.type === "RC_OPEN_JOB") sendResponse({ ok: true, result: openJob(message.index, message.url) });
      else if (message?.type === "RC_OPEN_APPLICATION") sendResponse({ ok: true, result: openApplication() });
      else return undefined;
    } catch (error) {
      sendResponse({ ok: false, error: error.message || "页面识别失败" });
    }
    return false;
  });
})();
