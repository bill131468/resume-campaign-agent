# API 手册

服务启动后，交互式 OpenAPI 位于 <http://127.0.0.1:18010/docs>，机器可读规范位于 `/openapi.json`。本页只描述稳定的功能分组；Pydantic 请求/响应字段以当前 OpenAPI 为准。

## 基本约定

- 默认地址：`http://127.0.0.1:18010`
- 内容类型：`application/json`
- 会话 ID 由 `POST /api/sessions` 返回。
- `404` 表示会话或资源不存在；`422` 表示 Pydantic 校验失败；`503` 表示外部职位源或可选 LLM 不可用。
- `POST /api/campaigns/dispatch` 固定返回 `403`，不是配置错误。

## 端点分组

| 分组 | 主要端点 | 用途 |
|---|---|---|
| 健康与模板 | `GET /api/health`、`GET /api/templates` | 运行状态和招聘门户字段模板 |
| 会话与简历 | `POST /api/sessions`、`GET /api/sessions/{id}`、`PATCH /api/sessions/{id}/resume` | 事实母版和求职偏好 |
| 审核与优化 | `POST /api/resume/review`、`POST /api/resume/optimize` | 六维审核和建议稿 |
| 岗位发现 | `GET /api/jobs/search`、`POST /api/discovery/enterprises` | 公开职位和官方企业入口 |
| 投递预览 | `POST /api/campaigns/preview`、`POST /api/batch/preview` | 不可发送的申请草稿与合成批次 |
| Career OS | `/api/career/*` | JD、版本、排序、看板、提醒、面试、风险、证据和保险箱 |
| 浏览器副驾驶 | `/api/browser/*` | 会话选择、能力契约、字段分析和岗位选择 |
| 自然语言 Agent | `POST /api/agent/run` | Pydantic AI 对话式编排，需要 LLM 配置 |

## 最小会话示例

```bash
curl -sS -X POST http://127.0.0.1:18010/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{
    "resume": {
      "full_name": "测试候选人",
      "email": "candidate@example.invalid",
      "phone": "13800000000",
      "current_city": "上海",
      "professional_summary": "仅用于本机合成测试",
      "target_roles": ["数据分析"],
      "base_locations": ["上海"]
    },
    "preferred_locations": ["上海"],
    "remote_preference": "hybrid"
  }'
```

响应中的 `id` 用于后续请求。示例域名 `.invalid` 和号码均为合成测试值，不得用于真实官网。

## 补全简历

```bash
curl -sS -X PATCH http://127.0.0.1:18010/api/sessions/SESSION_ID/resume \
  -H 'Content-Type: application/json' \
  -d '{"skills":["Python","SQL"]}'
```

系统以服务器端 `missing_resume_fields` 为最终必填判断，模型返回的缺失项不能覆盖该结果。

## 岗位和草稿预览

```bash
curl -sS -X POST http://127.0.0.1:18010/api/campaigns/preview \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_ID","limit":5}'
```

只有简历必填项完整时才生成草稿。所有草稿的发送能力保持关闭；用户需复核事实、地点、岗位状态和渠道官方性。

## 浏览器能力契约

`GET /api/browser/capabilities` 返回允许动作、拒绝动作以及是否存在受控最终提交能力。客户端应以服务返回的契约为准，并继续执行本地 fail-closed 检查。禁止能力包括读取密码、拦截短信、绕过 CAPTCHA、填写身份/人口统计字段、自动上传附件、无单岗位授权提交以及在无官网回执时声称成功。

## 保险箱

`POST /api/career/vault` 保存加密值，列表接口只返回元数据；`POST /api/career/vault/lease` 需要明确用途和授权。当前加密状态仍与内存进程生命周期绑定，不等同于生产密钥管理。

## CORS

默认只接受同源页面、`127.0.0.1`/`localhost` 和 Chrome 扩展来源。若修改 CORS，请同时实现身份认证、CSRF 防护、来源审计和回归测试，不要直接改成任意来源。
