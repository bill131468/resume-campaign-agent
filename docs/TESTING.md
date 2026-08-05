# 测试手册

## 目标与原则

测试必须证明功能正确，也必须证明副作用闸门在失败条件下保持关闭。默认只使用 `tests/fixtures/` 中的合成数据和本机浏览器 fixtures。真实招聘官网只允许进行合成档案安全预演：可以核验页面，不得发送验证码、填写资料或提交申请。

## 测试环境矩阵

| 层级 | 必需环境 | 是否联网 | 是否允许外部副作用 |
|---|---|---|---|
| Python 单元/API | Python 3.11/3.12 | 否 | 否 |
| 扩展工具单元 | Node.js 20+ | 否 | 否 |
| 静态与发布检查 | Python、Node、Git | 否 | 否 |
| 本机浏览器旅程 | Chrome/Edge 116+、本机服务 | 否 | 仅本机 fixture 写入 |
| 职位源冒烟 | 本机服务 | 是 | 只读 HTTP |
| 官网安全预演 | 扩展、真实企业公开页 | 是 | 只读；认证/填表边界停止 |

## 1. Python 自动化

Windows：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Linux/macOS：

```bash
python -m pytest -q
```

测试覆盖：

- 健康契约和 `dry_run` 边界；
- 简历缺失项与补丁写入；
- 资历门槛和合成批次隔离；
- 中国企业目录、Base/专业感知和官方入口状态；
- 六维简历审核、去标识化与不编造数字；
- JD、岗位版本、事实审计、排序去重、看板、提醒、面试、风险和保险箱；
- 浏览器字段敏感项阻断、同源职位选择、扩展权限、合成官网预演与能力契约；
- 后台 `dispatch` 永久 `403`。

如需查看单项：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_browser_assistant.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_api.py::test_dispatch_is_always_refused -q
```

## 2. 浏览器扩展单元与语法

```powershell
node --test browser_extension/auth-utils.test.js browser_extension/journey-utils.test.js browser_extension/permission-utils.test.js
node --check browser_extension/service-worker.js
node --check browser_extension/panel.js
node --check browser_extension/content.js
node --check browser_extension/auth-content.js
node --check browser_extension/journey-content.js
node --check browser_extension/submit-content.js
node --check src/resume_campaign_agent/static/app.js
```

预期所有命令退出码为 `0`。

## 3. API 冒烟

启动服务后：

```powershell
$healthResponse = Invoke-RestMethod http://127.0.0.1:18010/api/health
$healthResponse.ok
$healthResponse.delivery_mode
```

预期依次为 `True` 和 `dry_run`。随后验证后台发送闸门：

```powershell
try {
  Invoke-WebRequest -Method Post `
    -Uri http://127.0.0.1:18010/api/campaigns/dispatch `
    -ContentType application/json `
    -Body '{"session_id":"synthetic-test","confirmation":true}'
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

预期为 `403`。若得到 `2xx`，立即停止发布。

## 4. 本机浏览器完整旅程

准备：启动服务、加载 `browser_extension`，打开工作台并保留合成档案。

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1 | 打开 `/browser-fixture` | 识别为企业招聘首页 |
| 2 | 启动 AI 接管 | 进入本机职位列表并选择同源岗位 |
| 3 | 进入详情/申请 | 只选择资历与 Base 兼容岗位 |
| 4 | 进入本机登录 fixture | 出现验证码接力 UI，不访问真实短信服务 |
| 5 | 输入 fixture 测试码 | 进入本机申请表 |
| 6 | 扫描字段 | 密码、验证码、证件、人口统计、文件字段被阻断 |
| 7 | 填写计划 | 只写空白安全字段，不覆盖已有值 |
| 8 | 确认本机提交 | 只进入本机回执 fixture |
| 9 | 回执识别 | 只有明确回执文本才标记成功 |

用 DevTools 检查 Console 无未捕获异常；刷新页面后旧字段计划应因签名变化而失效。

## 5. 真实官网安全预演

此测试验证入口正确性，不验证投递成功。

1. 确认工作台档案带有明确的合成标记。
2. 选择公开企业官方招聘入口并授权当前单域名。
3. 允许扩展识别首页、职位列表、职位详情和申请入口。
4. 一旦到达登录/验证码页，预期显示安全预演停止提示；手机号字段必须为空，不能请求验证码。
5. 若直接到达申请表，允许只读字段分析；填入按钮应禁用，所有字段保持原状。
6. 页面不得出现由扩展触发的提交请求或成功声明。

若任何真实字段被写入、验证码被请求或按钮被点击，立即撤销站点权限，记录为 P0 安全回归。

## 6. 负向测试清单

- 缺少必填简历字段：允许搜索，不生成申请草稿。
- 初级候选人遇到 Senior/Lead 岗位：不生成草稿。
- 跨域职位链接或非 HTTPS 渠道：标记风险，不自动导航提交。
- 页面有 CAPTCHA：停止并要求用户手动处理，不能尝试绕过。
- 页面要求附件：停止，不自动上传。
- 页面有未确认协议/声明：停止。
- 最终提交按钮为 0 个或多于 1 个：停止。
- 预检后 DOM 字段签名变化：拒绝旧计划。
- 合成档案：官网认证、写入和提交全部拒绝。
- 服务端 dispatch 即使 `confirmation=true`：仍返回 `403`。

## 7. 公共发布检查

```powershell
python scripts/check_public_release.py
git status --short
```

脚本检查必需文档、许可证、被跟踪的敏感文件名、常见令牌/私钥形态、本机绝对路径和非示例公网地址。发布前还应人工检查：

```powershell
git diff --cached --stat
git diff --cached -- . ':(exclude)LICENSE'
```

不得提交 `.env.local`、私钥、真实简历、服务器地址、验证码、Cookie、原始网络日志或未脱敏证据。

## 8. 发布验收

发布 Gate 必须同时满足：

1. Python 测试全部通过且无跳过的安全测试；
2. 扩展单元测试与所有 JavaScript 语法检查通过；
3. 公共发布检查通过；
4. OpenAPI 和 README 启动命令可复现；
5. 本机完整浏览器 fixture 通过；
6. 合成官网安全预演在认证/填表边界停止；
7. 没有真实外部申请、短信或验证码副作用；
8. 启用 GitHub Actions 后 CI 绿色。仓库提供 `docs/examples/github-actions-ci.yml`，维护者可将其复制到 `.github/workflows/ci.yml`。

测试失败、超时或受站点阻断时应记录为失败、未知或阻塞，不得改写成通过。
