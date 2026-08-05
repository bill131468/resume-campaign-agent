(function initPermissionUtils(root) {
  function sitePattern(url) {
    const parsed = new URL(url);
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      throw new Error('当前页面不是可授权的招聘网站');
    }
    return `${parsed.origin}/*`;
  }

  async function inspect(chromeApi, url, apiOrigin) {
    const pattern = sitePattern(url);
    const origin = new URL(url).origin;
    const fixed = origin === apiOrigin;
    const granted = await chromeApi.permissions.contains({ origins: [pattern] });
    return { pattern, origin, fixed, granted };
  }

  async function request(chromeApi, url) {
    const pattern = sitePattern(url);
    const granted = await chromeApi.permissions.request({ origins: [pattern] });
    return { pattern, granted };
  }

  async function remove(chromeApi, pattern) {
    return chromeApi.permissions.remove({ origins: [pattern] });
  }

  const api = { inspect, remove, request, sitePattern };
  root.ResumeCopilotPermissions = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
