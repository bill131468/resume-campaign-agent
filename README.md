# Resume Campaign Agent / 简历海投辅助器

一个基于 Pydantic AI + FastAPI + Chrome/Edge Manifest V3 的开源求职工作台。它帮助用户完善结构化简历、审核与优化表达、按方向和 Base 搜索企业岗位、准备岗位版本与申请草稿，并在用户逐岗位授权后由浏览器扩展协助进入官方投递流程。

当前为 Alpha。生产模式默认关闭全部测试 fixture、使用空白真实档案，并允许浏览器在逐岗位授权后执行正式投递。默认存储为 JSON 文件持久化，没有多用户账号体系，不要在无额外认证时把真实简历服务直接暴露给不受信任的公网用户。

## 能做什么

- **通用简历模板**：覆盖基本信息、教育、工作、项目、技能、证书、语言、求职偏好与招聘门户字段。
- **简历审核与优化**：完整性、匹配度、成果证据、可信度、表达与结构六维报告；建议不会自动写回，也不得编造经历或数字。
- **岗位与企业发现**：结合方向、专业、Base 和资历搜索岗位，优先保留官方渠道并解释匹配依据。
- **求职驾驶舱**：JD 解析、一岗一简历、事实审计、岗位排序、渠道去重、进度看板、提醒、面试包、模拟面试、漏斗与风险检查。
- **浏览器副驾驶**：单站点按需授权，核验职位、进入申请页、映射空白安全字段、人工接力验证码，并在逐岗位确认且安全检查通过后触发唯一提交按钮。
- **简历文件导出**：自动生成 PDF 简历，内存直传附件，自动定位正确上传区域。
- **数据持久化**：会话和简历保存到本地 JSON 文件，刷新页面或重启后端不丢失。
- **生产/测试隔离**：正式启动不含合成默认值或演练入口；只有显式设置 `ENABLE_TEST_FIXTURES=true` 才开放本机 fixture。
- **服务端硬闸门**：`POST /api/campaigns/dispatch` 永远返回 403；不存在后台静默群发。


## 安全模型


```
flowchart LR
    U["用户与本机浏览器"] -->|"填写简历 / 逐岗位确认"| A["FastAPI + Pydantic AI"]
    A -->|"只读搜索 / 草稿"| J["公开职位源与官方目录"]
    A -->|"字段结构与安全映射"| E["浏览器扩展"]
    E -->|"单域名临时权限"| C["企业招聘官网"]
    C -->|"验证码与最终确认由用户接力"| U
    A -.->|"固定拒绝"| D["后台批量发送"]
```

### 硬性边界

- 不绕过 CAPTCHA、登录风控或站点访问控制。
- 不读取短信、Cookie、密码、浏览历史或剪贴板，不自动上传附件。
- 不把手机号、邮箱、姓名、验证码或保险箱明文发送给 LLM。
- 不覆盖网页已有值；缺失必填字段、附件、人工声明、CAPTCHA 或歧义提交按钮都会停止流程。
- "已点击"不等于"投递成功"，只有企业官网回执才可确认成功。

完整威胁模型和数据处理说明见 **安全与隐私手册**。

## 五分钟启动

**要求**：Python 3.11+；使用浏览器扩展时需要 Chrome/Edge 116+；运行扩展单元测试需要 Node.js 20+。

### Windows

```bash
git clone https://github.com/bill131468/resume-campaign-agent.git
cd resume-campaign-agent
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pip install playwright htmldocx
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m resume_campaign_agent
```

### Linux/macOS

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pip install playwright htmldocx
python -m playwright install chromium
python -m resume_campaign_agent
```

### 打开

- 工作台：http://127.0.0.1:18010/
- OpenAPI：http://127.0.0.1:18010/docs
- 测试 fixture（仅显式启用时）：http://127.0.0.1:18010/browser-fixture

LLM 是可选项。没有模型配置时，确定性规则、内置企业目录和大部分工作台仍可使用；自然语言 Agent 与部分 AI 排序会安全降级。复制 `.env.example` 为 `.env.local` 后只在本机填写配置，`.env.local` 已被 Git 忽略。

## 浏览器扩展安装

1. Chrome 打开 `chrome://extensions/`
2. 开启"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择本项目中的 `browser_extension/` 文件夹

## 使用流程

1. 工作台填写简历（有完整度提示）
2. AI 搜索企业
3. 点击"AI核岗"
4. 招聘网站自动打开
5. 用户登录并选择岗位
6. 点击浏览器右上角扩展图标打开副驾驶
7. 扫描 → 自动填表
8. 自动生成 PDF → 自动上传
9. 用户输验证码
10. 确认提交

## 测试

```bash
.\.venv\Scripts\python.exe -m pytest -q
node --test browser_extension/auth-utils.test.js browser_extension/journey-utils.test.js browser_extension/permission-utils.test.js
python scripts/check_public_release.py
```

详细的环境矩阵、API 冒烟、隔离 fixture 旅程、失败用例和发布回归步骤见 **测试手册**。正式环境必须保持 `ENABLE_TEST_FIXTURES=false`。

## 文档

| 文档 | 内容 |
|------|------|
| 快速开始 | 安装、配置、首次合成测试 |
| 本地使用手册 | 本地源码包安装、扩展、求职流程和故障处理 |
| AI 交接手册 | 后续 AI / Codex 的边界、代码地图、验收命令和变更协议 |
| 架构说明 | 组件、数据流、Pydantic AI 工具与副作用闸门 |
| API 手册 | 端点分组、调用示例与错误语义 |
| 测试手册 | 自动化、浏览器旅程、负向测试、发布验收 |
| 安全与隐私 | 数据分类、权限、部署边界与威胁模型 |
| 故障排查 | LLM、岗位源、扩展权限、验证码与部署问题 |
| 浏览器扩展 | 安装、权限、认证接力和提交条件 |
| 服务器部署 | Docker、SSH 隧道、反向代理与更新 |
| 参与贡献 | 开发流程、提交规范和 PR 检查 |
| GitHub Actions CI 模板 | Python 3.11/3.12 与浏览器扩展持续集成 |

## 项目结构

```
src/resume_campaign_agent/  FastAPI、Pydantic 模型、Agent 与静态前端
browser_extension/          Chrome/Edge Manifest V3 浏览器副驾驶
tests/                      Python 自动化与合成 fixtures
docs/                       用户、开发、测试和安全手册
deploy/                     systemd、Nginx 与临时隧道示例
scripts/                    发布包与公共仓库检查脚本
data/                       JSON 会话持久化（Git 忽略）
```

## 参与与许可证

欢迎提交 Issue 和 Pull Request。请先阅读 `CONTRIBUTING.md` 与 `SECURITY.md`。项目采用 Apache License 2.0。

本项目是求职辅助工具，不隶属于任何招聘平台或企业。使用者应遵守目标网站条款、隐私规则和适用法律，并对投递内容及最终操作负责。
