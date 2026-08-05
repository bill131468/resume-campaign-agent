const assert = require('node:assert/strict');
const permissions = require('./permission-utils.js');

const calls = [];
const chromeMock = {
  permissions: {
    contains: async (request) => { calls.push(['contains', request]); return false; },
    request: async (request) => { calls.push(['request', request]); return true; },
    remove: async (request) => { calls.push(['remove', request]); return true; }
  }
};

(async () => {
  assert.equal(permissions.sitePattern('https://jobs.example.cn/apply?id=7'), 'https://jobs.example.cn/*');
  assert.throws(() => permissions.sitePattern('chrome://extensions'), /不是可授权/);
  const state = await permissions.inspect(chromeMock, 'https://jobs.example.cn/a', 'http://127.0.0.1:18010');
  assert.deepEqual(state, {
    pattern: 'https://jobs.example.cn/*', origin: 'https://jobs.example.cn', fixed: false, granted: false
  });
  const requested = await permissions.request(chromeMock, 'https://jobs.example.cn/another/path');
  assert.deepEqual(requested, { pattern: 'https://jobs.example.cn/*', granted: true });
  assert.equal(await permissions.remove(chromeMock, requested.pattern), true);
  assert.deepEqual(calls[1], ['request', { origins: ['https://jobs.example.cn/*'] }]);
  assert.deepEqual(calls[2], ['remove', { origins: ['https://jobs.example.cn/*'] }]);
  console.log('permission-utils: 7 assertions passed');
})().catch((error) => { console.error(error); process.exit(1); });
