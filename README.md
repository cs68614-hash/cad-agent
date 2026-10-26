# Automotive CATIA MCP · 汽车零件设计整合版

**面向 CATIA V5 的工程原型，不是已通过汽车生产认证的 CAD 系统。**
将两个有 MIT 授权的项目接入同一个 CATIA 会话与 STA 执行队列，优先覆盖汽车零件的曲线、曲面和曲面转实体，兼顾草图、实体、装配、工程图、参数、导出与有限的原生 Analysis 操作。支持本机 stdio 和远程 Streamable HTTP。

## 组合了什么

| 来源 | 固定版本 | 使用方式 |
|---|---|---|
| [daiemon12/catia-v5-mcp-server](https://github.com/daiemon12/catia-v5-mcp-server) | `e8b9425e690bd09c7c6b1aeee0a913eedb16588f` | 保留 MIT 通知，隔离为 vendor/daiemon；来源注册 98 个工具 |
| [Cai-aa/CAD-Agent-Hub](https://github.com/Cai-aa/CAD-Agent-Hub) 的 MCP/CATIA | `339840b5f775e81d0b18519806ccb5e59885e2a6` | 保留 MIT 通知，隔离为 vendor/hub；来源注册 55 个工具 |
| [chenlei-gh/mcp-catia](https://github.com/chenlei-gh/mcp-catia) | 评估版本 `faf84686df16e1e4e4055e288eb73e509d3d03e3` | **未复制代码**：评估版本缺少 LICENSE；其 REST/会话等不完整实现不冒充可用功能 |

98 + 55 是来源注册数量，不代表 153 个互不重复、可生产使用的能力。整合保留 `daiemon__` 和 `hub__` 命名空间，重复能力可追溯；危险或已知错误的入口明确禁用，不通过“返回成功”掩盖。以运行时工具目录和[逐入口能力清单](docs/capability-inventory.md)为准。当前 144 个来源入口启用、9 个禁用，另有6个统一控制工具（含曲面步骤组合），共159个注册名称。

## 为什么适合汽车零件

- **曲面设计**：点/样条、投影/相交、扫掠/多截面、填充、偏置、分割/修剪、缝合、修复、边界、加厚/封闭。
- **工程特征**：曲面形成主体之后，继续添加草图、Pad/Pocket、孔、圆角、阵列等可用实体特征。
- **过程控制**：统一结果、有限数值校验、工作目录边界、会话/文档防误用、串行执行、请求日志与未知结果阻断。
- **远程使用**：Mac 上的 MCP 客户端可连接 Windows 上的 CATIA 执行端；不是在 macOS 上运行 CATIA。

适合参数化零件试制、重复特征自动化、曲面准备、批量检查与导出。不能据此声称自动完成整车 A 级造型、冲压成形分析、模具可制造性签核或碰撞认证。曲面指令的 G2 参数不等于曲率连续性验证。

## 安装与启动

实际执行端需要 Windows、已安装且有相应许可的 CATIA V5、Python 3.10+、与 CATIA 相同用户/权限级别。请先在 CATIA 中打开**专门用于测试的副本**。不同 V5 release、工作台许可和 COM 接口存在差异，首次部署必须完成实机验收。

```powershell
cd C:\tools\automotive-catia-mcp
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m automotive_catia --workspace C:\CATIA_MCP_Work --transport stdio
```

stdio 由客户端启动，stdout 专用于协议。不要把日志重定向到 stdout。**真实模式会操作 CATIA，安装或启动不等于已批准任何零件变更。**

离线模拟模式不连接 CATIA：

```bash
python -m pip install -e .
python -m automotive_catia --workspace ./offline-work --mock --transport stdio
```

模拟模式只用于协议、校验与控制流程，不能验证几何结果。测试：

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

PowerShell 可先执行 `$env:PYTHONPATH="src"`，再运行 `python -m unittest discover -s tests -v`。具体已运行/未运行项目见随包验证记录，本文不是测试通过声明。

## 使用约定

1. 先查看工具目录和运行状态，连接已运行的 CATIA，确认操作文档。
2. 根据工具 schema 提供请求 ID、文档绑定等保护参数；不同变更使用新的请求 ID。
3. 每完成一个关键曲面步骤，读取对象/更新状态并人工检查，不一次性盲发整车建模指令。
4. 超时、断线或未知结果时停止变更；先检查 CATIA、对象树及日志，再确认恢复。换 ID 重发不构成安全重试。
5. 保存、导出、导入和材料路径必须在明确配置的允许目录内。工作目录边界不是操作系统沙箱。

## 文档

- [汽车曲面与零件工作流](docs/automotive-workflows.md)
- [单会话架构与安全边界](docs/architecture.md)
- [远程部署与客户端示例](docs/remote.md)
- [离线测试和实机验收](docs/validation.md)
- [本次验证结果](docs/verification.md)
- [逐入口能力/禁用原因](docs/capability-inventory.md)

许可证原文在 `licenses/`。此包不包含 CATIA、CAD 模型、商业材料库或许可，也不提供任意 Python/命令行/COM 执行工具。尚未通过真实 CATIA 验证的工具不得当作生产已验证能力使用。
