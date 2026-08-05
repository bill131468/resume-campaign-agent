const assert = require('node:assert/strict');
const auth = require('./auth-utils.js');

assert.equal(auth.isPhoneText('联系电话 / mobile phone'), true);
assert.equal(auth.isOtpText('短信验证码'), true);
assert.equal(auth.isGetCodeText('获取验证码'), true);
assert.equal(auth.isContinueText('登录 / 创建账号并继续'), true);
assert.equal(auth.isContinueText('提交申请'), false);
assert.equal(auth.isContinueText('投递简历'), false);
assert.equal(auth.isApplicationSubmitText('Submit application'), true);
assert.equal(auth.isOpenApplicationText('立即投递'), true);
assert.equal(auth.isOpenApplicationText('提交申请'), false);
assert.equal(auth.isFinalSubmitText('提交申请'), true);
assert.equal(auth.isFinalSubmitText('立即投递'), false);
assert.equal(auth.isCaptchaText('短信验证码'), false);
assert.equal(auth.isCaptchaText('请完成滑块验证'), true);
assert.equal(auth.validatePhone('138 0000 0000'), true);
assert.equal(auth.validatePhone('123'), false);
assert.equal(auth.validateOtp('246810'), true);
assert.equal(auth.validateOtp('12'), false);

console.log('auth-utils: 17 assertions passed');
