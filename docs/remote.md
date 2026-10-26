# 远程 MCP：Windows 执行，Mac/Web 连接

## 推荐拓扑

```text
Mac MCP 客户端 ── HTTPS / 受保护 VPN / SSH 隧道 ── Windows CATIA 执行端
                          │                           │
                   可选 TLS 反向代理             单用户 CATIA 会话
```

服务端只能在有 CATIA V5 与许可的 Windows 上执行真实模型操作。Mac 是客户端。Web 客户端能否连接取决于它是否支持 Streamable HTTP、所需认证方式和网络可达性；本包只提供 Bearer 认证，没有 OAuth 授权服务器，不能保证直接接入所有 Web 产品。

## 回环试运行

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m automotive_catia --transport http --workspace C:\CATIA_MCP_Work
```

地址为 `http://127.0.0.1:8765/mcp`。默认不对外监听；不要为了“能连上”直接关闭防火墙。传输是 Streamable HTTP，不是旧 SSE 专用端点，也不是 Flask REST 路由。

## 内网/VPN 访问

先通过受控方式给进程设置 `AUTO_CATIA_TOKEN`，至少 32 个字符，使用密码管理器生成独立随机值。不要把真实 token 写进仓库、聊天或共享配置文件。本文不生成或保存凭据。

```powershell
# AUTO_CATIA_TOKEN 必须已安全注入到当前进程环境。
.\.venv\Scripts\python.exe -m automotive_catia --transport http `
  --workspace C:\CATIA_MCP_Work --host 0.0.0.0 --port 8765 `
  --allowed-host catia-worker.internal:8765
```

客户端请求 `http://catia-worker.internal:8765/mcp` 并发送：

```text
Authorization: Bearer <从安全配置读取的令牌>
```

**上述 HTTP 仅可置于已保护的专用网络/隧道内。** 跨不可信网络必须由运维配置 HTTPS 反向代理或加密隧道。Bearer token 不提供加密。本项目不会替你部署代理、打开端口、配置证书或持久化凭据。

`--allowed-host` 是精确 HTTP Host 值，通常包含端口，可重复指定；不允许 `*`。经过反向代理时应明确它转发的 Host，与白名单一致，不依赖任意 `X-Forwarded-*` 头绕过校验。代理需要支持 MCP 的 POST/GET/DELETE 与长请求，不应缓存响应。

来自浏览器的 Origin 默认拒绝；只有确有需要时追加精确可信值，例如 `--allowed-origin https://cad-client.example`。这不等于启用了任意跨域访问；客户端如依赖浏览器预检/CORS，应先验证其接入方式，必要时通过同源受控代理，不要设置通配 Origin。

## 客户端配置

`examples/stdio-client.json` 是常见桌面 MCP 客户端的 stdio 配置模板。替换 Python、workspace 的绝对路径；不同客户端配置格式可能不同。

`examples/remote-client.json` 展示 URL/传输/请求头所需语义，不是所有客户端通用的配置标准。`${AUTO_CATIA_TOKEN}` 只是占位符；仅在客户端确实支持该环境变量插值时使用，否则通过其安全凭据设置配置。不要把占位符原样当认证凭据。

## 多客户端限制

HTTP 可以有多个 MCP 协议会话，但底层仍是一个 CATIA 会话、一份活动文档和一个执行队列。文档 token 与请求日志防止部分误调用，不提供租户隔离、账号级 RBAC、项目权限或不同用户独立 CATIA 实例。建议一个专用设计任务对应一台执行机/独立进程和一个授权操作者。
