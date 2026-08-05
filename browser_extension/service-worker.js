const LOCAL_ORIGINS = new Set(["http://127.0.0.1:18010"]);

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

chrome.runtime.onStartup.addListener(async () => {
  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});

function handoffKey(tabId) {
  return "resumeTakeover:" + String(tabId);
}

function sanitizeHandoff(payload) {
  const target = new URL(String(payload?.url || ""));
  if (!["http:", "https:"].includes(target.protocol)) throw new Error("官网地址不是可访问的 HTTP(S) 页面");
  const sessionId = String(payload?.sessionId || "").slice(0, 200);
  const company = String(payload?.company || "").trim().slice(0, 120);
  if (!sessionId || !company) throw new Error("投递任务缺少简历会话或企业名称");
  return {
    sessionId,
    company,
    channelLabel: String(payload?.channelLabel || "").trim().slice(0, 160),
    url: target.href,
    targetRoles: Array.isArray(payload?.targetRoles) ? payload.targetRoles.slice(0, 5).map((item) => String(item).slice(0, 120)) : [],
    bases: Array.isArray(payload?.bases) ? payload.bases.slice(0, 8).map((item) => String(item).slice(0, 80)) : [],
    simulationOnly: payload?.simulationOnly === true,
    createdAt: new Date().toISOString()
  };
}

async function requestTargetPermission(url) {
  const target = new URL(url);
  if (LOCAL_ORIGINS.has(target.origin)) return true;
  const pattern = target.origin + "/*";
  if (await chrome.permissions.contains({ origins: [pattern] })) return true;
  return chrome.permissions.request({ origins: [pattern] });
}

async function startTakeover(message, sender) {
  const senderOrigin = sender.tab?.url ? new URL(sender.tab.url).origin : "";
  if (!LOCAL_ORIGINS.has(senderOrigin)) throw new Error("只能从本机投递作战夹发起 AI 接管");
  const handoff = sanitizeHandoff(message.payload);
  handoff.takeoverId = String(message.requestId || "").slice(0, 120);
  if (!(await requestTargetPermission(handoff.url))) throw new Error("未获得该招聘官网的单站点权限");
  const tab = await chrome.tabs.create({ url: handoff.url, active: true });
  handoff.tabId = tab.id;
  await chrome.storage.session.set({ [handoffKey(tab.id)]: handoff });
  await chrome.sidePanel.setOptions({ tabId: tab.id, path: "panel.html", enabled: true });
  try {
    await chrome.sidePanel.open({ tabId: tab.id });
  } catch (_) {
    // Some browser versions require the user to click the extension icon.
  }
  return { tabId: tab.id };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "RC_START_AI_TAKEOVER") {
    startTakeover(message, sender)
      .then((result) => sendResponse({ ok: true, ...result }))
      .catch((error) => sendResponse({ ok: false, error: error.message || "AI 接管失败" }));
    return true;
  }
  if (message?.type === "RC_GET_AI_TAKEOVER") {
    const tabId = Number(message.tabId);
    chrome.storage.session.get(handoffKey(tabId))
      .then((result) => sendResponse({ ok: true, handoff: result[handoffKey(tabId)] || null }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  if (message?.type === "RC_FINISH_AI_TAKEOVER") {
    chrome.storage.session.remove(handoffKey(Number(message.tabId)))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true;
  }
  return undefined;
});
