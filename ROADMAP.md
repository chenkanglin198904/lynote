# 待完善功能清单

个人外脑知识平台在「体系化入库 + 过闸 + 人审」之后，还缺学习闭环。本文件是后续实现的对照清单：做完一项就勾选，并在条目下补「落点 / 验收」。

核心目标：用 AI 解决传统学习的结构散、用错地方、不会迁移、错了不知道错在哪；在使用外脑的过程中**持续主动**加深加宽认知；从海量信息里按**当前主题缺口**推荐最有价值的材料——而不是按热度或模型流畅度。

权威产品约束仍以 [PROJECT.md](./PROJECT.md) 为准。本清单只展开「学 / 召回 / 考 / 纠 / 荐」，不改宪法。

## 现状（对照 1.0）

- [x] 源材料入库（笔记 / URL / Markdown / PDF / 音频 / 视频抽正文）
- [x] 按当前学习主题过闸，默认拒绝无关
- [x] 抽出带 `source_span` 的主张；对不上原文则丢弃
- [x] 人审收件箱后入图；冲突显式保留
- [x] 混合召回（词汇 + 可选向量 + 图跳）未命中不填垫
- [x] 决策简报：选项 / 证据 / 未知 / 最强反对；采纳需理由；结果回写
- [x] 主题可自建、可切换；导图总览分排、下钻收起兄弟层、可搜索节点
- [x] 学习频道：按图上已有概念拆章，逐章学；问答可把已引用主张收入当前章节
- [x] 独立的知识点检索（概念 / 主张 / 来源分栏，命中定位导图路径）
- [x] 问答输出「直答 / 出处 / 联想 / 未知」，而不是罗列主张
- [x] 回答后追问、批改用户作答
- [x] 个性化误区写入图谱，并在相关知识点再次召回
- [x] 掌握 / 薄弱 / 缺失仪表与主动推荐补料
- [x] 间隔复习
- [x] 向量默认落盘（重启不丢 embedding）

右侧「对话」已改为四段讲解，讲解后出一道追问并可批改；答错会在图上挂误区，相关再问会强制带回。左栏有掌握仪表、对立卡片和到期巩固。向量默认 LanceDB 落盘；扫描件 PDF 可视觉抽字。公开前仍须轮换曾进过版本库的密钥，且不要把未鉴权端口打到公网。

## 硬约束（后续任何功能都不得破）

1. 模型只能提议，对错由代码拿图上的节点 / 主张来判。
2. 不在图外编「标准答案」；没有 `source_id` / `source_span` 的结论当 bug。
3. 「举一反三」只能沿已有边走；没有边就说「图上还没连上」，允许人一键补边。
4. 误区必须挂到它反驳的正确主张上，禁止无证据的鸡汤错法。
5. 答题、巩固、推荐默认只用 `confirmed`；`candidate` 只配探索。
6. 不做千人模拟、不做全网当教材、不做全量 embedding 入库。

---

## 闭环 A · 找得准（检索 / 召回）

目标：在当前主题内，用最少噪音召回最该看的知识点。

- [x] **知识点搜索入口**：独立搜索框（不只是导图滤镜）；结果分概念 / 主张 / 来源；点击后展开该节点在导图上的路径并选中
  - 落点：`GET /v1/search`、`modules/retrieve/search.py`、`web/components/KnowledgeSearch.tsx`、`GraphCanvas` 定位
  - 验收：`tests/test_search.py`；UI 无命中时写「未知」，不编节点
- [x] **导图总览网格 + 下钻**：一级在上，二级分排；进入下一级只留祖先路径，收起兄弟层
  - 落点：`web/lib/mindmap.ts` `layoutFocusGrid`、`GraphCanvas` 受控 `drillId`
  - 验收：总览不再把全部二级排成一列；点进三级后其它二级消失，可用「上一级 / 总览」返回
- [x] **主题约束召回**：检索与问答默认锁在当前 `Goal` 邻域，避免串题
  - 落点：`RetrieveService.retrieve(..., allowed_node_ids=)`、`Workspace._topic_scope`
  - 验收：空主题搜种子词 / 问种子问题均未知
- [x] **混合召回升级**：当前主题 + 词汇 / 向量 + 图上 1～2 跳（从属、对立、证据）
  - 落点：原 `retrieve/service.py` 加上主题 `allowed_node_ids` 裁剪。误区加权仍未做
- [x] **误区加权**：用户历史误区相关的主张在召回里提高权重
  - 落点：`RetrieveService._rank_claims` 对 active `Misconception` 所挂 `claim_id` 加分；相关提问还会 `force_pin`
  - 验收：`tests/test_misconception.py` 相关提问带回误区，无关提问不带回
- [x] **未知显式**：答不上来标未知，禁止用模型私货顶上
  - 落点：搜索 `unknown: true`；讲解 `grounded.direct` 为空且 `unknowns` 含「召回未命中任何 Claim」
- [x] **召回分层**：主张分成 keep（对立或练过，放进直答）与 lookup（需要时再查）。没有上层主张时不编原理。
  - 落点：`modules/retrieve/layers.py`、`compose_grounded_answer` 的 `direct`/`lookup`、搜索 `KnowledgeHit.layer`、`RightPanel` / `KnowledgeSearch`
  - 验收：`tests/test_layers.py`、`tests/test_search.py`；钉住的细节仍出现在直答，但 layer 仍报 lookup
- [x] **装卸清单**：每个概念拆成该内化 / 可外置；人可改分法，不发明节点。
  - 落点：`modules/learn/pack.py`、`OutlineChapter.pack_keep/pack_lookup`、待挂 `HangProposal`、`POST /v1/claims/{id}/layer`、学习频道与待挂 UI
  - 验收：`tests/test_pack.py`；改分法后直答/搜索跟层走；candidate 不能标成该内化
- [x] **用过即加固**：点过、挂上、简报引用过的主张提高召回权重并进入巩固。
  - 落点：`record_use` / `PracticeStat.use_count`、`RetrieveService` 加权、`POST /v1/claims/{id}/touch`、挂点与采纳写路
  - 验收：`tests/test_reinforce.py`；未命中查询不加垫；十分钟内重复点不叠次数
- [x] **剧本情境加权**：跑完「读完这篇 / 会后落地」后，当天同主题召回改权重，不另开检索。读完偏概念和对立；会后偏未复盘决策和可行动主张。
  - 落点：`modules/retrieve/context.py`、sidecar `play_context`、`RetrieveService` / 搜索、工作台 `play_context`
  - 验收：`tests/test_plays.py`；未知查询不加垫；跨日或换主题失效
- [x] **显式迁移**：讲解沿已有边标明「这和你已有的 X 是同一类取舍」。没有边就停，允许人点「标成相关」。不发明节点、不用相似度编迁移。
  - 落点：`modules/tutor/transfer.py`、`GroundedAnswer.transfers`、联想区
  - 验收：`tests/test_transfer.py`；去掉 `related_to` 后不再说出同一类取舍
- [x] **向量落盘**：`VECTOR_BACKEND=lancedb` 作为默认或一键可切换；重启后 embedding 仍在
  - 落点：`providers/vectors.py` `LanceDbVectorStore`，默认 `VECTOR_BACKEND=lancedb`，测例强制 `memory`
  - 验收：`tests/test_vectors.py` 重开目录仍命中同一 claim id
- [x] **验收**：搜主题内词能分栏命中；搜无关词返回空且 UI 写「未知」，不编造节点

建议落点：`modules/retrieve/`、工作台左栏或顶栏搜索、`GraphCanvas` 定位 API。

---

## 闭环 B · 用得上（带证据回答 + 举一反三）

目标：问到一个点时，用图里的主张答，并沿边串联相关点。

- [x] **回答模板固定五段**（每段只能引用子图里的 id）
  1. 直接答案（keep：带对立或练过的主张；默认跳过 `candidate`）
  2. 需要时再查（lookup 细节；没有 keep 时不编原理）
  3. 依据（原文 quote，点击跳转出处）
  4. 联想（同概念其他主张、`contradicts` 对立、相邻概念；沿已有边标明同一类取舍）
  5. 边界（未知、冲突、图上尚未连接、空 keep）
  - 落点：`modules/tutor/grounded.py`、`ChatMessage.grounded`、`RightPanel` 对话 Tab
- [x] **禁止主张列表当答案**：现有 chat 把 cited claims 堆出来的行为要换成上述模板
- [x] **缺边可写回**：「图上还没连上」旁提供「标成相关」，经人确认后写 `Relation`。有边才说同一类取舍。
  - 落点：`POST /v1/relations`、`modules/tutor/link.py`、`GroundedAnswer.link_candidates`、对话联想区按钮
  - 验收：`tests/test_link.py`；只连当前主题里已有概念/主张，不发明节点；未知讲解不出按钮
- [x] **可信度分层展示**：`confirmed` 与 `candidate` 视觉区分；直答默认不引用 candidate（钉住除外）。`disputed` 用反方色
- [x] **验收**：问已入库问题，回答里的每个断言都能点开核对；问图外问题，边界段为未知且不出现无 id 的新知识
  - 回归：`test_chat_grounded_four_sections`、`test_chat_unknown_empty_claims`

建议落点：`workspace.chat` / 新 `tutor` 模块、`RightPanel` 对话 Tab、`contracts` 增加 `GroundedAnswer` 一类响应。

---

## 闭环 C · 学得住（反问、批改、误区档案）

目标：外脑会考你、会纠正，并把你的错法变成可召回的一等公民。

- [x] **学习会话（Session）**：一次「学某主题」是独立会话，不和决策简报、闲聊搅在同一条无限聊天里
  - 落点：`ChatMessage.lane` + `goal_id`；`workspace._stamp`；右侧「学习」只显示当前主题 learn 车道，决策记录留在简报页
  - 验收：`tests/test_lanes.py` 讲解为 learn，采纳为 decision；新主题学习会话为空
- [x] **苏格拉底追问**：讲解之后出 **一道** 针对刚用过的主张的追问（不是题海）
  - 落点：`modules/tutor/probe.py` `attach_probe`；有对立则选择题，否则短答。未知讲解不出题
- [x] **用户作答**：短答或选择题；提交后对照图上主张判定 对 / 漏 / 反
  - 落点：`POST /v1/probes/{id}/grade`、`RightPanel` 追问卡片
- [x] **批改与纠正**：指出错在哪一条主张、正确表述、原文依据；模型不得另编标准答案
  - 落点：代码用选项 `claim_id` 或短答与主张文本覆盖率判定；`correction` 只复述图上主张 + quote
  - 回归：`tests/test_probe.py`
- [x] **`Misconception` 入图**（新节点类型，需改 `contracts/schema.json` 及 Python / TS）
  - 用户原话
  - 它反驳的 `claim_id`
  - 所属 `goal_id`
  - 出现次数 / 最近出现时间
  - 状态：active / resolved
  - 落点：`modules/tutor/misconceptions.py`、`graph/store.py`、Kuzu hydrate；批改 `gap`/`contrary` 写入，按 `(goal_id, claim_id)` 去重
- [x] **相关再学时强制召回误区**：「你上次把 A 当成 B，图上是这样区分的……」
  - 落点：chat 前 force-pin 误区主张；子图 / 同概念 / 同源 / 词汇相关才带回；`ChatMessage.misconceptions` + 对话「常见误区」
- [x] **误区可归档为已纠正**：连续答对或人手动标记 resolved 后，降权但仍可查
  - 落点：连续答对 2 次 `resolved`；`POST /v1/misconceptions/{id}/resolve`；节点留在图上
- [x] **验收**：故意答错 → 图上多一条误区；换问相邻概念 → 回答/追问里带上该误区；契约与前后端类型三方对齐
  - 回归：`tests/test_misconception.py`

建议落点：新模块 `learn/` 或 `tutor/`（禁止塞进 `brief/`）；`graph/` CRUD；过闸与抽取仍不负责出题。

---

## 闭环 D · 主动变深变宽（缺口、推荐、复习）

目标：不等你问；按「对当前主题缺口的贡献」从信息里捞东西。

- [x] **掌握状态**：概念 / 主张上维护 已掌握 / 薄弱 / 缺失
  - 多次答对且无活跃误区 → 掌握
  - 反复误区或批改为「反」→ 薄弱
  - 孤立概念、无对立、无证据 → 缺失
  - 落点：`modules/learn/service.py`，练习次数写 sidecar `workspace.json` 的 `practice`，不把掌握写进图节点
- [x] **深度 / 广度仪表**：深度 = 主张有证据且有对立；广度 = 概念覆盖面。主题页能看见这周深了还是只变宽了
  - 落点：`TopicLearn.depth/breadth/trend`、左栏 `LearnPanel`、工作台顶栏趋势句
- [x] **对比学习卡片**：把 `contradicts` 做成并排卡片（例如 SFT vs 指令微调 vs RLHF），作为主动推送，而不是再吸十篇综述
  - 落点：`TopicLearn.contrasts`，只引用图上已有冲突对
- [x] **巩固题**：对薄弱主张按间隔出题（先简单间隔：1 / 3 / 7 天，再考虑遗忘曲线参数）
  - 落点：答反/漏则立即到期；`POST /v1/learn/reviews` 复用追问批改。答对后按 1/3/7 天改 `next_review_at`
- [x] **补料推荐**：缺失点 → 建议该补哪类材料（对立观点、原始论文、反例）；过闸时提高「能补这个缺口」的材料权重
  - 落点：`GapAdvice`；`apply_gap_boost` 提高 actionability，不改质量闸的拒绝
- [x] **收件箱价值排序**：待审材料按「对缺口的贡献」排序，而不是时间倒序
- [x] **验收**：一个只有主张没有对立的概念，仪表标缺失；过闸时同类补对立的材料排序高于闲聊文
  - 回归：`tests/test_learn.py`
- [x] **学习频道**：庞大主题先给图上已有目录，再按章从前到后学；左栏摘要、中间导图、右栏出处 / 问答
  - 落点：`modules/learn/outline.py` `compose_outline` / `capture_to_chapter`、`POST /v1/learn/capture`、`CourseRail`、工作台顶栏「学习频道」
  - 验收：目录标题必须是图上已有概念或主张，不另编教材大纲；「收入当前章节」只写 `about` 边，问答不能发明节点。`tests/test_outline.py`

建议落点：`gate/` 增加缺口特征（仍不直接写图）；工作台左栏或简报上方仪表；`Goal` 或 sidecar 存掌握状态（先 sidecar，稳了再入图）。

---

## 日常外脑（切片 9–18）

目标：让外脑能接住随手记下的经验、音视频、旧决策和图谱卫生，而不是只能处理长文 PDF。

- [x] **随手记**：一句话也能入库。`Source.kind=note`，用户原文就是 `source_span`。过闸对人记材料放宽过短规则，仍进收件箱等人审。营销清单体照样拒。
  - 落点：`POST /v1/notes`、`Workspace.scratch_note`、左栏「随手记」
  - 验收：`test_scratch_note_is_evidence_and_proposes_existing_hang`
- [x] **挂到何处**：抽取后只提议已有概念、当前主题，以及原文中出现的新章名。人点已有节点只写 `about`；点新章名才建 `Concept`。模型起的、原文没有的词直接丢掉。挂上后主张从 `candidate` 升为 `confirmed`。
  - 落点：`modules/extract/service.py` 不再 `upsert_concept`；`modules/learn/hang.py` `proposed_names`；`POST /v1/hangs/confirm` 的 `new_name`
  - 验收：`test_extract_model_keeps_locatable_span`、`test_confirm_hang_writes_about_and_rejects_invented_target`
- [x] **行业检索只辅助归类**：可选联网搜索对照已有概念/主题和偏好领域。检索片段不能当主张、不能建行业本体；人对上后才写边，网页要进图仍须过闸。
  - 落点：`providers/websearch.py`、`modules/learn/industry.py`、`HangProposal.industry_hints`
  - 验收：`tests/test_industry.py`
- [x] **音频转写**：上传音频转成可定位正文，未听到的句子不发明。
  - 落点：`modules/ingest/avtext.py` `transcribe_audio`、`POST /audio/transcriptions`、采集栏音频
  - 验收：`test_audio_transcript_becomes_source_text`
- [x] **今日面板**：到期巩固、待审、待复盘决策、今日亲手记下的材料。
  - 落点：`modules/learn/today.py`、`Workbench.today`、左栏「今日」
- [x] **决策复利**：再问同类问题时带回已拍板/已复盘的 Decision，不编新结论。
  - 落点：`modules/learn/prior.py`、简报「上次同类决策」、讲解「上次决策」
  - 验收：`test_prior_decisions_surface_on_similar_brief`
- [x] **偏好 sidecar**：角色 / 领域 / 更信亲手笔记。偏好不是知识，不能填未知。召回可给 `note`/`audio`/`video` 主张加权，可跳过 `candidate`。
  - 落点：`Profile`、`GET/PUT /v1/profile`、`RetrieveService.own_note_boost`
  - 验收：`test_own_notes_boost_and_cross_topic_stays_explicit`
- [x] **视频**：抽旁白；有 ffmpeg 时抽少量帧做画面文字。抽不出则拒绝，不发明。
  - 落点：`transcribe_video`、Docker 镜像含 ffmpeg、采集栏视频
  - 验收：`test_video_uses_transcript_without_inventing`
- [x] **显式跨主题**：默认锁当前主题。其它主题命中单独列出，勾选「也搜其他主题」才并入召回。
  - 落点：`ChatRequest.expand_cross_topic`、`modules/learn/crosstopic.py`、学习输入框复选框
- [x] **概念合并 / 过时降权**：合并只加别名、改写边，不融合冲突主张。过时主张 `deprecated`，召回跳过，历史仍可查。
  - 落点：`modules/graph/maintain.py`、出处面板「并入」「标为过时」
  - 验收：`test_merge_and_deprecate_do_not_invent_nodes`
- [x] **带引用周报**：只列出图上已有来源 / 主张 / 决策 id，可下载 Markdown。
  - 落点：`GET /v1/report/weekly`、`modules/learn/report.py`、今日栏「导出本周」
  - 验收：`test_today_board_and_weekly_report_only_cite_existing_ids`

---

## 基础设施与体验（支撑上面四条）

这些不是学习算法，但缺了会让闭环空转。

- [x] **扫描件 / 图片 PDF**：视觉抽字或 OCR；否则教材进不了图
  - 落点：`modules/ingest/pdftext.py` 先 pypdf，正文过短则渲染页面走 `complete_vision_text`；无 Key 仍拒绝空白件
  - 验收：`test_blank_pdf_is_rejected`、`test_scanned_pdf_uses_vision_transcript`
- [x] **学习会话与决策简报分栏**：避免「问知识点」和「要不要做 X 决策」抢同一个 Chat
  - 落点：右栏 Tab「决策简报 / 学习 / 出处」；`web/lib/session.ts` 按 lane 与当前主题过滤
- [x] **空状态文案**：无主题、无命中、无误区、无缺口时说明下一步该入库还是该先学已有点
  - 落点：`web/lib/copy.ts`，左栏 / 导图 / 搜索 / 学习 / 简报 / 出处 / 仪表共用
  - 第一次使用说明：仓库 [GUIDE.md](./GUIDE.md)，工作台顶栏「用法」打开 `/guide`
- [x] **左栏收成今日桌面**：主题和随手记常驻；待挂 / 待审 / 巩固 / 复盘并进「下一步」；采集、掌握、偏好默认折叠
  - 落点：`web/components/LeftRail.tsx`、顶栏趋势仍用 `TopicLearn.trend`
  - 验收：工作台左栏不再同时铺开仪表、采集和收件箱全文；待审接受/拒绝仍在下一步卡片上
- [x] **剧本（非插件）**：内置「读完这篇」「会后落地」，只编排过闸 / 待审 / 待挂 / 可选简报。不自动接受、不自动建章、不替人拍板。跑完后当天召回按情境加权。
  - 落点：`modules/learn/plays.py`、`modules/retrieve/context.py`、`POST /v1/plays/run`、左栏「剧本」
  - 验收：`tests/test_plays.py`
- [x] **测试**：每个新闭环至少一条「未知不编造」和一条「必须引用 claim id」的回归
  - 落点：`backend/tests/test_search.py`
- [x] **公开前**：`.env` 移出版本库并轮换密钥；LICENSE；README 与本清单、PROJECT 对齐；未鉴权端口不要对公网裸奔
  - 落点：`.gitignore` 忽略 `.env`；`LICENSE`（MIT）；README 安全节。**密钥轮换须你在网关侧操作**，代码不能替你作废已泄露的 Key

---

## 明确不做（写在清单里以免跑偏）

- 不拿全网检索结果当教材直接教用户
- 不在图外生成「百科标准答案」
- 不把误区写成没有反驳证据的鸡汤
- 不做人设千人 / 世界模拟
- 不先做多用户、云端默认同步、完美本体
- 不把学习闭环做成通用 ChatGPT 套壳

---

## 推荐实现顺序（一次只打穿一条能天天用的环）

按依赖排列。前一项未勾，不要跳去做仪表和推荐。

| 顺序 | 切片 | 对应条目 | 状态 |
|---|---|---|---|
| 1 | 主题内知识点搜索 + 命中定位导图 | 闭环 A 前两项 | 已做 |
| 2 | 带引用的回答（直答 / 需要时再查 / 出处 / 联想 / 未知） | 闭环 B | 已做 |
| 3 | 回答后一道追问 + 对用户作答打分 | 闭环 C 追问与批改 | 已做 |
| 4 | `Misconception` 入图，相关召回强制带上 | 闭环 C 误区 | 已做 |
| 5 | 掌握仪表、对比卡片、间隔复习、缺口推荐 | 闭环 D | 已做 |
| 6 | 向量落盘、扫描件 PDF、公开前安全项 | 基础设施 | 已做 |
| 7 | 导图总览网格 + 下钻收起兄弟层 | 闭环 A 增补 | 已做 |
| 8 | 学习频道按章拆解 + 问答收入章节 | 闭环 D 增补 | 已做 |
| 9 | 随手记：原文即证据，过闸后人审 | 日常捕获 | 已做 |
| 10 | 抽取后「挂到何处」人确认 | 日常捕获 | 已做 |
| 11 | 音频转写，时间戳可定位 | 日常捕获 | 已做 |
| 12 | 今日面板：巩固 / 待审 / 待复盘 | 日常入口 | 已做 |
| 13 | 决策复利：同类问题带回上次选择 | 决策 | 已做 |
| 14 | 偏好 sidecar + 亲手笔记加权 | 记忆分层 | 已做 |
| 15 | 视频旁白 / 抽帧，不发明未见内容 | 日常捕获 | 已做 |
| 16 | 跨主题只显式展开，不默默混进直答 | 召回 | 已做 |
| 17 | 概念合并别名改边；过时主张降权不删 | 图谱卫生 | 已做 |
| 18 | 导出只引用已有节点的周报 | 复盘 | 已做 |
| 19 | 行业检索只对照已有节点，不建本体 | 归类 | 已做 |
| 20 | 剧本：读完这篇 / 会后落地，不做插件 | 一体化 | 已做 |
| 21 | 召回分层：keep 进直答，lookup 需要时再查 | 召回 | 已做 |
| 22 | 装卸清单：该内化 / 可外置，人可改分法 | 学习 | 已做 |
| 23 | 用过即加固：点过/挂上/拍板引用进入巩固 | 练习 | 已做 |
| 24 | 剧本情境加权：读完偏概念对立，会后偏待复盘 | 召回 | 已做 |
| 25 | 显式迁移：沿已有边说同一类取舍，没边就停 | 召回 | 已做 |

切片 1–25 已落地。公开到 GitHub 前仍须轮换密钥、确认 `.env` 不在版本库，并用防火墙/反代挡住未鉴权端口。

---

## 后续 Agent 怎么用这份清单

1. 先读 [PROJECT.md](./PROJECT.md) 再读本文件。
2. 一次只认领表中的**下一个未完成切片**，不要平行铺开四条闭环。
3. 做完后：勾选对应 `- [ ]`、把表格状态改成「已做」，并在该条下用一句话写落点文件与验收方式。
4. 若发现新缺口，追加到对应闭环，不要另起一份平行路线图。
5. 新能力必须能说清它消灭了哪类学习错误（找不到、用错、不会迁、重复摔、信息过载）。
