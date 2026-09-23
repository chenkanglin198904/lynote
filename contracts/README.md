# contracts

权威数据契约。改字段必须先改这里，再改 Python / TypeScript 镜像。

| 文件 | 用途 |
|---|---|
| `schema.json` | JSON Schema（节点、边、收件箱、简报、工作台） |
| `openapi.yaml` | HTTP API |
| `python` 镜像 | `backend/lynote/contracts/models.py` |
| `ts` 镜像 | `web/lib/types.ts` |

冻结原则：骨架阶段不改字段名。要扩展就加可选字段。
