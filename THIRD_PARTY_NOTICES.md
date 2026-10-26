# 第三方来源

本项目包含以下 MIT 授权衍生源码，完整原作者声明保留在 `licenses/`：

- daiemon12/catia-v5-mcp-server，固定版本 `e8b9425e690bd09c7c6b1aeee0a913eedb16588f`。
- Cai-aa/CAD-Agent-Hub 的 MCP/CATIA，固定版本 `339840b5f775e81d0b18519806ccb5e59885e2a6`。

完整 Git blob 清单见 `provenance.json`。修改包括 Python 包命名空间隔离、统一连接注入及 AST 派生 Hub 包装器；不直接启动任一上游 server。上游保留的代码不是全部都在统一接口启用；以能力矩阵为准。

chenlei-gh/mcp-catia 在审查版本缺少 LICENSE，因此没有复制其代码。通用布尔、批量参数、历史/撤销等意图列入路线图，未冒称该仓库功能已全部集成。

CATIA、Dassault Systèmes 商标及商业软件不包含在本项目中；使用者需要自己的合法许可。
