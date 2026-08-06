# 本地使用手册（给人看）

## 1. 你得到了什么

这个本地工作台包含简历完善、简历审核、岗位匹配、中国企业线索、官网投递入口、一岗一简历、投递看板、面试准备和浏览器副驾驶。页面和 API 运行在你自己的电脑上。

它不是无人监管的“后台群发器”。每个岗位都需要你确认；验证码和 CAPTCHA 需要人工接力；企业官网回执才是成功依据。

## 2. 环境要求

- Windows 10/11：Python 3.11 或 3.12，Chrome / Edge 116+。
- Linux/macOS：Python 3.11+。浏览器扩展建议在桌面版 Chrome / Edge 中使用。
- Node.js 20+ 只用于扩展自动化测试，普通使用不强制。
- 至少 1 GB 可用磁盘空间用于 Python 虚拟环境和依赖。

## 3. Windows 安装

解压 ZIP 后，在根目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local.ps1
```

脚本会创建 `.venv`、安装项目与测试依赖，并执行一轮基础验证。它不会创建云服务，也不会写入 API Key。

## 4. Linux/macOS 安装

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
python -m pytest -q
```

## 5. LLM 配置（可选）

不配置 LLM 也能使用确定性简历校验、内置企业目录、投递预检和大部分 Career OS 功能。自然语言 Agent 和部分 AI 排序需要 OpenAI 兼容接口。

在 Codex 环境中，优先让 `llm-api-config` 把已加密的本机配置注入项目。不要把 API Key 粘贴进对话、源码、Issue 或截图。项目识别以下环境变量名：

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`

本地配置文件名为 `.env.local`，已被 Git 忽略。不要将它放入交付 ZIP。

## 6. 启动和停止

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1
```

Linux/macOS：

```bash
. .venv/bin/activate
APP_ENV=production ENABLE_TEST_FIXTURES=false AGENT_HOST=127.0.0.1 AGENT_PORT=18010 \
  python -m resume_campaign_agent
```

启动后访问：

- 工作台：<http://127.0.0.1:18010/>
- 健康检查：<http://127.0.0.1:18010/api/health>
- API 文档：<http://127.0.0.1:18010/docs>

在服务窗口按 `Ctrl+C` 停止。当前会话保存在内存中，停止后会清空。

## 7. 安装浏览器扩展

1. Chrome 打开 `chrome://extensions`，Edge 打开 `edge://extensions`。
2. 开启“开发者模式”。
3. 点击“加载已解压的扩展程序”，选择 `browser_extension` 目录。
4. 确认版本为 `0.7.1`，然后固定“简历投递副驾驶”。
5. 回到工作台并刷新页面。

已解压扩展没有自动升级。替换源码后，需在扩展管理页点击“重新加载”。

## 8. 一轮正式使用

1. 填写自己的真实简历事实，不使用虚构经历。
2. 运行简历审核，核对完整度、时间、数字和联系方式。
3. 填写目标方向、专业和 Base 城市，运行企业搜索。
4. 只选择已核验的官方招聘入口，点击“AI 核岗 · 接管官网”。
5. 首次进入某个企业站点时，在扩展侧边栏点击“仅授权当前招聘网站”。
6. 核对简历版本和字段预检清单；验证码由你手工填写。
7. 如有附件、人工声明、CAPTCHA 或缺失字段，先在官网处理，不要强行提交。
8. 逐岗位确认最终提交，并保存企业官网回执。

## 9. 检查本地安装

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify_local.ps1
```

预期 Python 测试、扩展单元测试和 JavaScript 语法检查全部通过。如果未安装 Node.js，脚本会明确提示跳过扩展测试。

## 10. 常见问题

- `This function must be called during a user gesture`：使用了 0.7.0 或更早扩展。替换为 0.7.1 并重新加载。
- 页面打不开：确认服务窗口没有关闭，并检查 `/api/health`。
- `llm_configured=false`：不是启动失败，只是 LLM 功能将降级。
- 扩展显示 Agent 离线：确认端口为 `18010`，且使用的是包内 `browser_extension`。
- 重启后简历消失：当前版本默认使用内存存储，这是已知限制。

## 11. 卸载和清理

- 在 Chrome / Edge 扩展管理页删除扩展，即可撤销全部站点权限。
- 删除 `.env.local` 可移除项目本地 LLM 配置。
- 删除 `.venv` 可移除 Python 依赖；源码和文档不受影响。
