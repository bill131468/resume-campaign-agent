# 本地源码交接手册（给 AI / Codex 看）

## Handoff contract

```yaml
project: resume-campaign-agent
delivery: local-source
application_version: 0.2.2
extension_version: 0.7.1
runtime_boundary: 127.0.0.1:18010
deployment_authority: none
external_submission_authority: per-application user confirmation only
storage: in-memory
test_fixtures_default: false
llm: optional, environment-only
primary_human_doc: docs/LOCAL_USER_GUIDE.md
```

## 1. 当前交付目标

维护一个可在单机启动的 Pydantic AI + FastAPI 求职工作台。本交付包不授权任何云端部署、DNS、隧道、服务器、应用商店发布或外部提交操作。若用户后续需要这些操作，必须以新的明确指令授权。

## 2. 不可破坏的约束

1. 服务默认绑定 `127.0.0.1`，不得因为“方便”改为 `0.0.0.0`。
2. `APP_ENV=production` 且 `ENABLE_TEST_FIXTURES=false` 是正常本地使用基线。
3. `POST /api/campaigns/dispatch` 必须继续拒绝后台静默群发。
4. 不编造简历事实；一岗一简历只能重排或生成待用户确认的表达。
5. 姓名、手机号、邮箱、验证码、保险箱明文不得发送给 LLM。
6. 不读取短信、Cookie、密码、浏览历史；不绕过 CAPTCHA 或站点风控。
7. 最终提交必须绑定当前岗位的明确用户授权，并以企业官网回执核验结果。
8. 已解压扩展没有自动升级；不得宣称已具备商店级自动更新。

## 3. 代码地图

| 路径 | 职责 |
|---|---|
| `src/resume_campaign_agent/api.py` | FastAPI 应用、路由、健康契约和测试 fixture 隔离 |
| `src/resume_campaign_agent/agent.py` | Pydantic AI Agent 和工具注册 |
| `src/resume_campaign_agent/config.py` | 环境变量和 `.env.local` 读取 |
| `src/resume_campaign_agent/campaign.py` | 简历补全、企业搜索和投递草稿 |
| `src/resume_campaign_agent/career_copilot.py` | JD、版本、看板、面试、风险和证据库 |
| `src/resume_campaign_agent/browser_assistant.py` | 招聘页字段映射与安全跳过 |
| `src/resume_campaign_agent/static/` | 本地单页工作台 |
| `browser_extension/` | Manifest V3 侧边栏、单站点授权、填表与提交闸门 |
| `tests/` | Python API/不变量测试和合成 fixture |

## 4. 首次接手顺序

1. 阅读本文档、`LOCAL_README.md` 或包内 `README.md`、`docs/LOCAL_USER_GUIDE.md` 和 `docs/SECURITY.md`。
2. 检查 `git status --short`；不覆盖用户现有改动。
3. 确认 Python 3.11+，运行 `scripts/setup_local.ps1` 或按手册建立 `.venv`。
4. 如需 LLM，使用 `llm-api-config` 安全注入；不读取、打印或复制 `.env.local`。
5. 运行 `scripts/verify_local.ps1`。
6. 仅在本机启动并检查 `/api/health`：`deployment_mode=production`、`test_fixtures_enabled=false`。

## 5. 扩展权限交接

0.7.1 修复了首次站点授权的 user-gesture 错误。正确时序是：

```text
工作台点击接管
  -> service worker 只检查权限并打开目标页
  -> 侧边栏显示等待授权
  -> 用户在侧边栏直接点击“仅授权当前招聘网站”
  -> chrome.permissions.request 在该 click handler 内立即调用
  -> 授权成功后继续原接管任务
```

不要把 `chrome.permissions.request()` 放回 service worker 消息链或任何延迟回调中。

## 6. 验收命令

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_local.ps1
```

等价手动命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test browser_extension/auth-utils.test.js browser_extension/journey-utils.test.js browser_extension/permission-utils.test.js
node --check browser_extension/service-worker.js
node --check browser_extension/panel.js
node --check browser_extension/content.js
node --check browser_extension/auth-content.js
node --check browser_extension/journey-content.js
node --check browser_extension/submit-content.js
node --check src/resume_campaign_agent/static/app.js
```

最小运行验收：

- `/api/health` 返回 `ok=true`。
- `deployment_mode=production`。
- `test_fixtures_enabled=false`。
- `/browser-fixture` 返回 `404`。
- 扩展 `manifest.json` 只固定授权 `http://127.0.0.1:18010/*`。
- service worker 不含 `chrome.permissions.request`；权限请求只出现在侧边栏的直接点击路径。

## 7. 已知限制

- 会话、看板和证据库默认为进程内存，重启即丢失。
- 扩展是已解压开发版，没有自动升级。
- 企业官网 DOM 会变化，没有可验证的唯一提交按钮时必须 fail closed。
- 岗位搜索可受外部公开数据源可用性影响；入口必须再核验官方性和在招状态。
- 本地包不含云端认证、稳定域名、持久数据库或扩展商店发布。

## 8. 变更协议

- 修改应用版本时同步 `pyproject.toml`、`src/resume_campaign_agent/__init__.py` 和 `api.py`。
- 修改扩展时同步 `browser_extension/manifest.json`、`BROWSER_EXTENSION.md` 和用户手册。
- 修改 LLM 接入时必须使用 `llm-api-config`，代码只读环境变量。
- 修改外部副作用路径时，先增加负向测试，再修改实现。
- 未通过完整验收时，不得声称“可正式投递”或“已成功提交”。
