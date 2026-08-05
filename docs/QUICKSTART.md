# 快速开始

本手册用于在本机完成一次不产生外部投递副作用的合成数据体验。默认端口为 `18010`，默认存储为进程内存。

## 1. 环境要求

- Python 3.11 或 3.12
- pip 23+
- Chrome/Edge 116+（仅浏览器副驾驶需要）
- Node.js 20+（仅扩展单元测试需要）

## 2. 安装

Windows PowerShell：

```powershell
git clone https://github.com/redmaplewww/resume-campaign-agent.git
cd resume-campaign-agent
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

Linux/macOS：

```bash
git clone https://github.com/redmaplewww/resume-campaign-agent.git
cd resume-campaign-agent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

## 3. 可选的 LLM 配置

不配置 LLM 也能使用确定性简历校验、内置企业目录、投递预检和大部分 Career OS 功能。自然语言 Agent 需要 OpenAI 兼容接口。

```powershell
Copy-Item .env.example .env.local
```

只在 `.env.local` 中填写：

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-model-name
LLM_API_KEY=your-local-secret
```

`.env.local` 不得提交、截图或粘贴到 Issue。服务不会在健康接口返回密钥。

## 4. 启动与健康检查

```powershell
.\.venv\Scripts\python.exe -m resume_campaign_agent
```

另开终端：

```powershell
Invoke-RestMethod http://127.0.0.1:18010/api/health
```

预期：`ok=true`、`agent_framework=pydantic-ai`、`delivery_mode=dry_run`。`llm_configured=false` 不是启动失败，只代表自然语言 Agent 不可用。

## 5. 第一次安全演练

1. 打开 <http://127.0.0.1:18010/>。
2. 保留页面内明确标记的合成档案。
3. 运行简历审核，确认出现六维报告。
4. 按目标方向和 Base 搜索企业，检查每个入口是否标记为官网或待核验渠道。
5. 打开 <http://127.0.0.1:18010/browser-fixture>，完成首页→职位列表→详情→登录→申请表→回执的本机链路。
6. 不要在真实招聘官网发送验证码或提交合成档案。

## 6. 安装浏览器扩展

1. Chrome 打开 `chrome://extensions`，Edge 打开 `edge://extensions`。
2. 开启开发者模式，选择“加载已解压的扩展程序”。
3. 选择仓库内的 `browser_extension` 目录。
4. 固定“简历投递副驾驶”，刷新工作台页面。
5. 首次进入某个招聘官网时，只批准当前单一域名权限。

详细的验证码接力、字段范围和提交条件见 [浏览器扩展说明](../BROWSER_EXTENSION.md)。

## 7. 停止与清理

在运行服务的终端按 `Ctrl+C`。内存会话随进程退出清空。删除 `.env.local` 可移除本地 LLM 配置；卸载扩展可撤销其全部权限。

下一步可阅读 [架构说明](ARCHITECTURE.md)、[API 手册](API.md) 和 [测试手册](TESTING.md)。
