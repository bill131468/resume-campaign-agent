# Resume Campaign Agent 本地源码版

这是一份只面向本机运行的源码交付版：FastAPI / Pydantic AI 服务只监听 `127.0.0.1:18010`，Chrome / Edge 扩展也只与该本地地址通信。包内不含云端部署脚本、服务器配置、密钥、真实简历或运行数据。

## 快速启动（Windows）

1. 安装 Python 3.11 或 3.12。
2. 在本目录打开 PowerShell。
3. 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_local.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start_local.ps1
```

4. 打开 <http://127.0.0.1:18010/>。
5. 扩展安装和完整求职流程见 [本地使用手册](docs/LOCAL_USER_GUIDE.md)。

## 文档入口

- 人类使用者：[docs/LOCAL_USER_GUIDE.md](docs/LOCAL_USER_GUIDE.md)
- AI / Codex 维护者：[AI_HANDOFF.md](AI_HANDOFF.md)
- 测试：[docs/TESTING.md](docs/TESTING.md)
- 安全边界：[docs/SECURITY.md](docs/SECURITY.md)

## 当前版本

- 应用：`0.2.2`
- 浏览器扩展：`0.7.1`
- 存储：进程内存，服务停止后会话清空
- 更新：已解压扩展不会自动升级，新版需替换文件后在扩展管理页点击“重新加载”

## 重要边界

工具不绕过验证码或 CAPTCHA，不读取短信、Cookie 或密码，不会在没有逐岗位授权时静默群发。最终是否成功以企业官网回执为准。
