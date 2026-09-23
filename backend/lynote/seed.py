"""Golden-demo seed. Question: graph vs note pile."""

from __future__ import annotations

from lynote.contracts.models import (
    ChatMessage,
    Claim,
    Concept,
    Decision,
    DecisionBrief,
    DecisionOption,
    Evidence,
    GateCheck,
    Goal,
    InboxItem,
    Relation,
    Source,
    SourceSpan,
)


GOAL = Goal(
    id="goal_graph_vs_notes",
    title="图谱还是笔记堆",
    question="要不要把个人知识做成图谱，而不是继续堆笔记？",
    status="active",
)

SOURCES = [
    Source(
        id="src_notes_pain",
        kind="note",
        title="本周笔记：信息越存越找不到",
        text="文件夹里已经有四百条剪藏。提问时模型会编，我自己也对不上出处。笔记必须变成可召回的主张，否则只是安慰自己读过。",
        created_at="2026-09-10T08:00:00+00:00",
        credibility=0.9,
    ),
    Source(
        id="src_filter_essay",
        kind="markdown",
        title="无筛选的图谱会腐烂",
        text="知识图谱质量由拒绝率决定。全量入库再 embedding 会把营销稿和旧结论一起变成节点。主张必须挂证据才能进入已确认层。互相打架的结论不要偷偷合并。",
        created_at="2026-09-11T08:00:00+00:00",
        credibility=0.8,
    ),
    Source(
        id="src_mirosim",
        kind="url",
        title="群体模拟不适合个人决策",
        uri="https://www.qbitai.com/2026/03/384728.html",
        text="用成百上千人格智能体推演世界很酷，但个人学习与工作判断不需要平行社会。个人场景里少量专职 Agent 更可控。不要先做千人模拟。",
        created_at="2026-09-12T08:00:00+00:00",
        credibility=0.7,
    ),
    Source(
        id="src_listicle",
        kind="url",
        title="十大 AI 笔记神器，收藏即学会",
        uri="https://example.invalid/listicle",
        text="盘点今年必看的十大 AI 笔记神器，一键导入全集，收藏即学会，让你的大脑升级。",
        created_at="2026-09-14T08:00:00+00:00",
        credibility=0.2,
    ),
]

CONCEPTS = [
    Concept(
        id="concept_pkg",
        name="个人知识图谱",
        aliases=["PKG"],
        definition="以主张和证据为中心、可拒绝入库的个人知识结构",
        domain="个人知识",
    ),
    Concept(
        id="concept_notes",
        name="笔记堆积",
        definition="按时间线收藏原文，缺少主张层和冲突层",
        domain="个人知识",
    ),
    Concept(
        id="concept_graphrag",
        name="GraphRAG",
        definition="用图结构约束检索与生成，而不是只靠向量相似",
        domain="检索",
    ),
]

CLAIMS = [
    Claim(
        id="claim_rot",
        text="没有筛选的图谱会变成垃圾场",
        polarity="asserts",
        confidence=0.78,
        status="confirmed",
        evidence=[
            Evidence(
                source_id="src_filter_essay",
                quote="知识图谱质量由拒绝率决定。",
                source_span=SourceSpan(start=0, end=13),
            )
        ],
        opposed_claim_ids=["claim_ingest_all"],
    ),
    Claim(
        id="claim_ingest_all",
        text="先把材料全收进向量库，以后再清理",
        polarity="asserts",
        confidence=0.35,
        status="disputed",
        evidence=[
            Evidence(
                source_id="src_listicle",
                quote="一键导入全集，收藏即学会",
                source_span=SourceSpan(start=18, end=30),
            )
        ],
        opposed_claim_ids=["claim_rot"],
    ),
    Claim(
        id="claim_evidence",
        text="主张必须挂证据才能进入已确认层",
        polarity="asserts",
        confidence=0.84,
        status="confirmed",
        evidence=[
            Evidence(
                source_id="src_filter_essay",
                quote="主张必须挂证据才能进入已确认层。",
                source_span=SourceSpan(start=45, end=61),
            )
        ],
    ),
    Claim(
        id="claim_recall",
        text="笔记必须变成可召回的主张，否则只是安慰自己读过",
        polarity="asserts",
        confidence=0.8,
        status="confirmed",
        evidence=[
            Evidence(
                source_id="src_notes_pain",
                quote="笔记必须变成可召回的主张，否则只是安慰自己读过。",
                source_span=SourceSpan(start=31, end=55),
            )
        ],
    ),
    Claim(
        id="claim_no_swarm",
        text="个人决策不需要千人社会模拟",
        polarity="asserts",
        confidence=0.72,
        status="confirmed",
        evidence=[
            Evidence(
                source_id="src_mirosim",
                quote="个人学习与工作判断不需要平行社会。",
                source_span=SourceSpan(start=18, end=35),
            )
        ],
    ),
]

RELATIONS = [
    Relation(id="rel_goal_pkg", from_id="goal_graph_vs_notes", to_id="concept_pkg", type="about"),
    Relation(id="rel_goal_notes", from_id="goal_graph_vs_notes", to_id="concept_notes", type="about"),
    Relation(id="rel_rot_pkg", from_id="claim_rot", to_id="concept_pkg", type="about"),
    Relation(id="rel_rot_vs_all", from_id="claim_rot", to_id="claim_ingest_all", type="contradicts"),
    Relation(
        id="rel_rot_ev",
        from_id="claim_rot",
        to_id="src_filter_essay",
        type="evidenced_by",
        source_id="src_filter_essay",
    ),
    Relation(
        id="rel_evi_ev",
        from_id="claim_evidence",
        to_id="src_filter_essay",
        type="evidenced_by",
        source_id="src_filter_essay",
    ),
    Relation(
        id="rel_recall_ev",
        from_id="claim_recall",
        to_id="src_notes_pain",
        type="evidenced_by",
        source_id="src_notes_pain",
    ),
    Relation(
        id="rel_swarm_ev",
        from_id="claim_no_swarm",
        to_id="src_mirosim",
        type="evidenced_by",
        source_id="src_mirosim",
    ),
    Relation(id="rel_graphrag", from_id="concept_graphrag", to_id="concept_pkg", type="related_to"),
    Relation(
        id="rel_decision_goal",
        from_id="decision_week",
        to_id="goal_graph_vs_notes",
        type="decides",
    ),
    Relation(id="rel_evi_goal", from_id="claim_evidence", to_id="goal_graph_vs_notes", type="about"),
    Relation(id="rel_recall_goal", from_id="claim_recall", to_id="goal_graph_vs_notes", type="about"),
    Relation(id="rel_swarm_goal", from_id="claim_no_swarm", to_id="goal_graph_vs_notes", type="about"),
    Relation(id="rel_all_goal", from_id="claim_ingest_all", to_id="goal_graph_vs_notes", type="about"),
    Relation(
        id="rel_all_ev",
        from_id="claim_ingest_all",
        to_id="src_listicle",
        type="evidenced_by",
        source_id="src_listicle",
    ),
]

OPTIONS = [
    DecisionOption(
        id="opt_notes",
        label="继续堆笔记 + 通用聊天",
        summary="成本最低，但出处对不上，知识不复利。",
        supporting_claim_ids=[],
    ),
    DecisionOption(
        id="opt_graph_thin",
        label="做个人图谱，先打穿筛选 + 主张 + 召回",
        summary="先拒绝垃圾，再让判断可追溯。不先做仿真。",
        supporting_claim_ids=["claim_rot", "claim_evidence", "claim_recall", "claim_no_swarm"],
    ),
    DecisionOption(
        id="opt_swarm",
        label="直接上多智能体世界模拟",
        summary="叙事酷，但个人决策复核成本高。",
        supporting_claim_ids=["claim_ingest_all"],
    ),
]

DECISION = Decision(
    id="decision_week",
    goal_id="goal_graph_vs_notes",
    question=GOAL.question,
    options=OPTIONS,
    status="draft",
)

BRIEF = DecisionBrief(
    id="brief_week",
    decision_id="decision_week",
    question=GOAL.question,
    options=OPTIONS,
    evidence_claim_ids=["claim_rot", "claim_evidence", "claim_recall", "claim_no_swarm"],
    unknowns=[
        "你是否会持续过闸，而不是情绪上来就全收下",
        "维护图谱的周均时间是否真低于翻笔记",
    ],
    skeptic="图谱的维护税可能高于笔记。若筛选纪律守不住，三个月后这张图会比文件夹更难用；先做世界模拟则是用不可复核的戏剧感代替判断。",
    recommendation="若目标是可验证的学习与决策，选「先打穿筛选 + 主张 + 召回」。反对意见成立的条件是：你不准备拒绝任何东西。",
)

INBOX = [
    InboxItem(
        id="inbox_listicle",
        source_id="src_listicle",
        title="十大 AI 笔记神器，收藏即学会",
        snippet="盘点今年必看的十大 AI 笔记神器，一键导入全集，收藏即学会…",
        status="pending",
        verdict="reject",
        checks=[
            GateCheck(gate="goal_alignment", passed=True, note="命中目标：图谱还是笔记堆"),
            GateCheck(gate="quality", passed=False, note="营销/清单体信号，论证密度不足"),
            GateCheck(gate="novelty", passed=True, note="标题相对已有来源是新的"),
            GateCheck(gate="actionability", passed=False, note="看不出能更新哪个选项或下一步"),
            GateCheck(gate="maintenance_cost", passed=False, note="噪声实体风险高，入库后难消歧"),
        ],
    )
]

MESSAGES = [
    ChatMessage(
        id="msg_seed",
        role="assistant",
        content="当前图上已有互斥主张：无筛选入库会腐烂，与「先全收进向量库」冲突。回答任何问题都会把两边一并给你，不会只讲好听的一侧。",
        claim_ids=["claim_rot", "claim_ingest_all"],
        lane="learn",
        goal_id="goal_graph_vs_notes",
    )
]
