# 本次验证记录

日期：2026-10-26。环境：隔离 Linux 云端，无 Windows CATIA、无商业模型、未连接用户电脑。

## 已通过

- `PYTHONPATH=src python -m unittest discover -s tests -v`：**59 项通过**（最终发布前重跑）。
- 实际 MCP SDK stdio 子进程：initialize、159 个唯一工具名称、调用 auto_session；运行 `--mock`，不接 COM。
- 实际 MCP SDK Streamable HTTP：通过内存 ASGI 执行 initialize/list/call；未向外暴露 TCP 服务。
- HTTP Bearer、Host、Origin、重复安全头、错误结果 isError。
- 98 个 daiemon 原生工具 schema 与静态清单逐项一致；全部 159 个统一 schema 可由 jsonschema 校验。
- Hub 54 个非禁用连接包装的转发参数，与真实 executor AST 签名一致；共享 app 注入，不创建第二线程。不是54个几何操作实机通过。
- 上游真实 Python 实现 + mock COM：GSD 点、Offset 参数、失败更新、Pocket 无效果分支。
- 统一请求日志、重复/冲突请求、单线程、超时不取消、未知结果阻断、日志写故障、同journal独占锁。
- 有限数、路径/符号链接逃逸、组件路径数组、隐式Save、保留journal路径、文档token、活动文档切换、跨文档Sketcher/GSD缓存失效。
- 同线程曲面步骤组合在失败时停止并报告已完成步骤；质量检查更新失败不当成功。
- 本地 wheel 构建，以及包内两份工具目录和两份原始 MIT 许可证内容存在性检查。

## 未验证 / 不能据此推断

- Windows pywin32、msvcrt进程锁分支、真实CATIA COM接口、不同V5版本/工作台许可。
- 实际曲面/实体质量、G2/A级连续性、厚度/单位/法向、稳定拓扑与装配约束。
- 真实网络TLS代理、VPN、防火墙、远程客户端兼容性、多人负载与生产部署。
- Analysis材料引用闭环、求解物理可信度、制造及汽车行业认证。
- 单个journal锁不阻止另一工作目录的服务/其他软件连接同一CATIA；必须一CATIA会话一服务进程。

## 已知依赖提示

测试环境 MCP 1.29.0、jsonschema 4.26.0、uvicorn 0.52.1。在部分带资源追踪的内存HTTP测试退出过程中，MCP SDK的SSE读取器曾报告非致命 `ResourceWarning`（`mcp/server/streamable_http.py`）；测试仍通过，未屏蔽警告。长时间真实HTTP部署的资源回收仍需单独验收。

上游细致Windows安装探针没有通过统一health接口运行；该入口当前提供无需连接的轻量状态，并明确返回探针延期说明。没有把未连接状态冒充CATIA可用。
