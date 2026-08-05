# 参与贡献

感谢参与 Resume Campaign Agent。项目涉及个人信息和真实招聘网站副作用，安全回归与功能回归同等重要。

## 开发流程

1. Fork 仓库，从 `main` 创建短分支。
2. 使用 Python 3.11/3.12 安装 `.[test]`。
3. 修改代码时同步补测试和相关文档。
4. 运行 [测试手册](docs/TESTING.md) 中的 Python、扩展和公共发布检查。
5. 提交 Pull Request，写清数据来源、权限变化、外部副作用和验证证据。

提交消息推荐使用简洁的 Conventional Commits 风格，例如 `feat: add portal adapter`、`fix: stop synthetic OTP requests`、`docs: expand deployment guide`。

## 安全要求

- 只使用合成简历和 `.invalid` 邮箱进行开发、截图和测试。
- 不提交 `.env.local`、密钥、真实简历、验证码、Cookie、服务器地址或原始抓包。
- 不实现 CAPTCHA 绕过、短信拦截、Cookie/历史读取、隐藏后台群发或无逐岗位授权提交。
- 新增扩展权限必须解释最小必要性，并补权限测试。
- 新增职位源必须说明授权方式、服务条款和数据保留策略。
- LLM 输出不能直接成为浏览器动作；必须经过结构化校验和确定性安全规则。

## 代码风格

- Python 使用类型标注、Pydantic 模型和明确错误语义。
- 外部 I/O 使用超时，失败状态不得伪装为成功。
- JavaScript 保持无构建依赖的 Manifest V3 结构；不要使用动态远程代码。
- UI 文案要区分“计划”“已触发”和“官网已确认成功”。

## Pull Request 检查

- [ ] Python 测试通过。
- [ ] 扩展单元和 JS 语法检查通过。
- [ ] `python scripts/check_public_release.py` 通过。
- [ ] 新功能有测试、用户文档和安全边界说明。
- [ ] 没有真实外部投递副作用。
- [ ] 没有新增秘密、个人数据或不必要权限。

漏洞请不要开公开 Issue，按 [安全政策](SECURITY.md) 私下报告。
