# LyNote

[English](README.md) | [简体中文](README.zh-CN.md)

**人脑管上层，外脑管细节。** 一个本地优先的个人外脑：把可核对的知识放进图谱，让有限的工作记忆只保留原理、取舍和自己的误区。

普通人用不好 AI，通常不是模型不够强，而是知识散、证据对不上、错了下次还摔、判断无法复利。LyNote 不做第二个聊天窗口，也不做世界模拟。它要让**人脑和外脑合成一体**：问到时先给该放进脑子的一层，细节留在图上点开核对；学和判走同一张图。

GitHub 不会按浏览器语言切换 README。英文是默认首页，中文是同一份说明。

第一次打开工作台请读 [GUIDE.md](./GUIDE.md)（顶栏「用法」是同一份说明）。改代码先读 [PROJECT.md](./PROJECT.md)。许可证：[LICENSE](./LICENSE)（MIT）。

---

## 要解决什么

人脑容量有限。把例子、步骤、出处、数字、旧材料硬塞进长期记忆，会挤掉更高层的模型。外脑如果只是收藏夹或流畅散文，人脑仍然找不到、用错地方、不会迁移。

LyNote 的目标是：

1. **减负**：细节可召回、可核对，人只记该内化的一层。
2. **贴切**：按当前主题和情境把对的那一层送回来，而不是十段摘要。
3. **拔高**：冲突摊开、错法进图、判断能积累。软件不保证「变聪明」，但可以降低工作记忆税，让练习和决策复利。

质量看**拒绝率**和**能不能点开原文**，不看摄入量，也不看对话是否流畅。答不上来写「未知」——这是功能，不是故障。

## 五层怎么合成一体

| 层 | 人脑 | 外脑 | 合在一起时 |
|---|---|---|---|
| **分层** | 原理、取舍、自己的误区 | 例子、步骤、出处、数字 | 直答给该内化的主张，细节在「需要时再查」 |
| **装入** | 决定这批材料属于哪一层 | 过闸、抽取、挂点、人确认 | 读完/会后接到已有模型上，不另开一本教材 |
| **召回** | 用当前情境开口 | 主题锁、证据子图、误区、上次决策 | 回来的是贴切的一层，不是串题摘要 |
| **练习** | 真正改口、改判断 | 追问、批改、巩固、对立 | 错法挂在正确主张上，相关再出现时强制带回 |
| **复利** | 拍板、事后结果 | 简报、同类决策、周报 | 下次同类问题带着上次选择 |

这五层已经接到同一套环上，不是五套产品。

## 现在能做什么

本地可跑的个人工作台，不是演示幻灯：

- **入库**：随手记、网页、Markdown、PDF（含扫描件）、音频、视频。五道闸默认拒绝清单体；主张必须对上原文 `source_span`。
- **挂点**：抽取只出主张；新章名等人确认才建概念。待挂拆成该内化 / 可外置。
- **今日桌面**：下一步只列当前主题（待挂 / 待审 / 到期巩固 / 待复盘）。剧本只有「读完这篇 / 会后落地」，不是插件市场。
- **召回**：主题锁、keep / lookup 分层、用过即加固、剧本情境加权。未知不编节点。
- **学习**：直答 / 需要时再查 / 依据 / 联想 / 边界。沿已有边才说「这和你已有的 X 是同一类取舍」；没边就停，人点「标成相关」才写边。追问一道，批改只判对 / 漏 / 反。
- **决策**：选项、证据、未知、最强反对；采纳必须写理由；结果回写。同类问题带回上次选择。

种子主题可以走通：「要不要把个人知识做成图谱，而不是继续堆笔记」。

尚未承诺、也不假装已经打穿的：可靠自动抽象、保证变聪明、读心式召回、专家题序、多模态思维结构进图、多用户云端默认同步。这些写在 [ROADMAP.md](./ROADMAP.md) 的后续能力里，欢迎按宪法补，不要用它们换掉拒绝率。

## 这不是什么

- 不是 ChatGPT 套壳，不在图外编百科。
- 不是笔记全文搜索：没有主张、冲突、决策，就不算本项目。
- 不是全量 embedding 仓库。
- 不是千人社会 / 世界模拟 / 技能商店 / 行业本体。

## 参与维护

格局靠**同一套宪法**，不靠平行功能。适合动手的方向：把现有环接得更稳、测试补「未知不编造」和「必须引用 claim id」、文档与契约对齐。

1. 读 [PROJECT.md](./PROJECT.md) 的硬规则，再读 [ROADMAP.md](./ROADMAP.md)。
2. 一次只打穿清单上的下一项（或开源后待完成能力里你认领的一项），不要另起入口。
3. 新能力必须能说清消灭了哪类错误：找不到、用错、不会迁、重复摔、信息过载。
4. 契约在 [contracts/](./contracts/)。Python / TypeScript 字段名不要擅自改。
5. 测例强制内存图和内存向量，不碰 `data/`：

```bash
cd backend
python -m venv .venv
# Windows
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
# macOS / Linux
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
```

Issue 和 PR 请写：改了哪条环、如何验收「未知 / 不发明节点」。把项目做成通用助手、插件市场或云端默认同步，会直接偏离宗旨。

## 安全

这是**单人、无登录**的本地优先工具。任何能访问端口的人都能读写图谱和收件箱。

1. 复制 `.env.example` 为 `.env`，填自己的 Key。**不要提交 `.env`。**
2. 本仓库不跟踪 `.env`。若你 fork 时历史里曾出现过 Key，在网关侧轮换。
3. `API_HOST` / `WEB_HOST` 默认回环。不要把未鉴权端口映射到公网。
4. 个人知识默认留在 `./data/`，不要把该目录推进 Git。

## 启动

需要 Node.js 18+、Python 3.11 或 3.12。复制 `.env.example` 为 `.env`，填入 [OpenAI API Key](https://platform.openai.com/api-keys)。默认请求 `https://api.openai.com/v1`，embedding 共用同一把 Key。不填 Key 时启发式也能跑通，但不适合当真用。

也可用任何 OpenAI 兼容端点（Azure、vLLM、自建网关）：只改 `LLM_BASE_URL`。官方接口不要设 `LLM_CALLER`。

Docker：

```bash
docker compose up -d --build
```

- 工作台：http://localhost:3000（或 `.env` 的 `WEB_PORT`）
- API 文档：http://localhost:8000/docs（或 `.env` 的 `API_PORT`）

容器要访问宿主机上的兼容网关时，把 `LLM_BASE_URL` / `EMBEDDING_BASE_URL` 写成 `http://host.docker.internal:<端口>/v1`。

本机：

```bash
npm install
npm --prefix web install

cd backend
python -m venv .venv
# Windows
.\.venv\Scripts\python.exe -m pip install -e .
# macOS / Linux
.venv/bin/python -m pip install -e .
cd ..

npm run dev
```

`npm run setup` 在 Windows 和 Unix 上走同一套安装。

- 工作台：http://localhost:3000
- 用法：http://localhost:3000/guide
- API：http://localhost:8000/docs（前端把 `/v1/*` 转到后端）

图谱默认 Kuzu（`data/lynote.kuzu`），工作台状态在 `data/workspace.json`，向量默认 LanceDB（`data/vectors`）。
