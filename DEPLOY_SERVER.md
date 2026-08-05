# 服务器部署手册

## 部署结论先行

当前版本默认无账号认证和多租户隔离。推荐把服务只绑定到服务器 `127.0.0.1`，由单个用户通过 SSH 隧道访问。只有完成认证、授权、持久化、密钥管理、限流和数据删除机制后，才能考虑公开互联网部署真实简历服务。

Codex 只参与开发，不是运行时依赖。服务器需要 Python 或 Docker；浏览器扩展必须安装在用户自己的 Chrome/Edge 中。

## 方案 A：Docker Compose + SSH 隧道（推荐）

服务器安装 Docker Engine 与 Compose 插件后：

```bash
git clone https://github.com/redmaplewww/resume-campaign-agent.git
cd resume-campaign-agent
cp .env.server.example .env.server
chmod 600 .env.server
docker compose build --pull
docker compose up -d
docker compose ps
```

Compose 只发布到服务器回环地址：`127.0.0.1:18010`。LLM 参数通过 `.env.server` 或云平台密钥管理器注入；不要写入镜像、Compose、命令参数或仓库。

用户电脑建立隧道：

```bash
ssh -N -L 18010:127.0.0.1:18010 your-user@your-server.example
```

随后在用户电脑访问 <http://127.0.0.1:18010/api/health>，并按 [浏览器扩展手册](BROWSER_EXTENSION.md) 加载扩展。浏览器只连接本机回环地址，SSH 把请求转发到服务器。

更新：

```bash
git pull --ff-only
docker compose build --pull
docker compose up -d
```

停止：

```bash
docker compose down
```

## 方案 B：Python + systemd

仓库 `deploy/resume-campaign-agent.service` 是示例，假定：

- 专用系统用户 `resumeagent`；
- 代码位于 `/opt/resume-campaign-agent`；
- 虚拟环境位于 `/opt/resume-campaign-agent/.venv`；
- 环境文件位于 `/etc/resume-campaign-agent.env`；
- 服务只监听 `127.0.0.1:18010`。

准备：

```bash
sudo useradd --system --home /opt/resume-campaign-agent --shell /usr/sbin/nologin resumeagent
sudo git clone https://github.com/redmaplewww/resume-campaign-agent.git /opt/resume-campaign-agent
sudo python3 -m venv /opt/resume-campaign-agent/.venv
sudo /opt/resume-campaign-agent/.venv/bin/python -m pip install /opt/resume-campaign-agent
sudo chown -R resumeagent:resumeagent /opt/resume-campaign-agent
sudo install -m 0644 deploy/resume-campaign-agent.service /etc/systemd/system/
sudo install -m 0600 .env.server.example /etc/resume-campaign-agent.env
sudo systemctl daemon-reload
sudo systemctl enable --now resume-campaign-agent
sudo systemctl status resume-campaign-agent
```

在 `/etc/resume-campaign-agent.env` 中注入 LLM 参数时不要加日志输出。更新代码后重新安装并重启服务。

## HTTPS 反向代理

`deploy/nginx-career-*.conf` 使用 `resume-agent.example.com` 作为占位域名。替换域名和证书路径后再启用。生产反向代理至少需要：

- TLS 1.2+、HSTS、安全响应头；
- 请求体和超时限制；
- 禁止记录请求正文、Authorization 和 Cookie；
- 应用级认证、CSRF 与限流；
- 数据保留和删除接口。

Cloudflare Quick Tunnel 仅适合合成数据临时演示：地址不稳定，且 TLS 本身不能弥补应用无认证。`deploy/resume-career-tunnel.service` 仅作受控演示示例。

## 数据和备份

当前会话、看板、证据和保险箱都在内存中，容器或进程重启后清空。因此本版没有需要备份的持久业务数据库，也不应被描述为生产持久化服务。后续接入数据库时，应先制定字段加密、租户隔离、备份加密、恢复演练、保留期和用户删除策略。

## 运维检查

```bash
curl --fail http://127.0.0.1:18010/api/health
docker compose ps
docker compose logs --tail=100 resume-agent
df -h
```

健康响应应包含 `ok=true`、`deployment_mode=production`、`delivery_mode=per_application_authorized` 和 `test_fixtures_enabled=false`。磁盘不足、职位源超时或 LLM 不可用不得关闭安全闸门。日志对外分享前必须去除请求载荷、简历字段、主机信息和凭据。

## 浏览器边界

远程服务器不运行用户的招聘账号浏览器，也不保存验证码、Cookie 或密码。每位用户在自己的浏览器安装扩展、批准单站点权限、手动输入验证码并逐岗位授权。遇到 CAPTCHA、附件、缺失字段、人工声明或歧义按钮时，扩展停止。
