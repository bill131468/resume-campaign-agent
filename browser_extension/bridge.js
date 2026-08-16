(() => {
  if (globalThis.__resumeCopilotBridgeV4Loaded) return;
  globalThis.__resumeCopilotBridgeV4Loaded = true;
  const allowedOrigins = new Set(["http://127.0.0.1:18010"]);

  window.addEventListener("message", (event) => {
    const data = event.data;
    if (
      event.source !== window ||
      !allowedOrigins.has(event.origin) ||
      data?.source !== "resume-campaign-app" ||
      data?.type !== "RC_AI_TAKEOVER_REQUEST"
    ) return;

    let retries = 0;
    const maxRetries = 3;

    const trySend = () => {
      chrome.runtime.sendMessage(
        { type: "RC_START_AI_TAKEOVER", requestId: data.requestId, payload: data.payload },
        (response) => {
          const error = chrome.runtime.lastError?.message;
          if (error && retries < maxRetries) {
            retries++;
            setTimeout(trySend, 500);
            return;
          }
          window.postMessage({
            source: "resume-campaign-extension",
            type: "RC_AI_TAKEOVER_ACK",
            requestId: data.requestId,
            ok: Boolean(response?.ok) && !error,
            error: error || response?.error || ""
          }, event.origin);
        }
      );
    };

    trySend();
  });
})();