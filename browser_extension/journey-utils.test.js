const assert = require('node:assert/strict');
const journey = require('./journey-utils.js');

assert.equal(journey.isClosedText('该职位已下线'), true);
assert.equal(journey.isClosedText('AI 工程师 上海'), false);
assert.equal(journey.isReceiptText('投递成功，我们已收到您的申请'), true);
assert.equal(journey.isReceiptText('提交申请'), false);
assert.equal(journey.isListingText('查看全部职位'), true);
assert.equal(journey.isListingText('公司介绍'), false);
assert.equal(journey.isJobHref('https://jobs.example.com/position/123456/detail'), true);
assert.equal(journey.isJobHref('https://jobs.example.com/about'), false);
assert.equal(journey.looksLikeApplicationUrl('https://jobs.example.com/resume/123/apply'), true);

console.log('journey-utils: 9 assertions passed');
