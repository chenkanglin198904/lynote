"""Pydantic mirror of contracts/schema.json. Do not rename fields."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeKind = Literal["source", "concept", "claim", "goal", "decision", "misconception"]
SourceKind = Literal["markdown", "pdf", "url", "note", "audio", "video"]
PlayId = Literal["read_article", "after_meeting"]
ClaimPolarity = Literal["asserts", "denies", "uncertain"]
ClaimStatus = Literal["candidate", "confirmed", "disputed", "deprecated"]
GoalStatus = Literal["active", "paused", "resolved"]
DecisionStatus = Literal["draft", "committed", "reviewed"]
InboxStatus = Literal["pending", "accepted", "rejected"]
GateName = Literal[
    "goal_alignment",
    "quality",
    "novelty",
    "actionability",
    "maintenance_cost",
]
GateVerdict = Literal["accept", "reject", "review"]
RelationType = Literal[
    "about",
    "belongs_to",
    "supports",
    "contradicts",
    "evidenced_by",
    "decides",
    "related_to",
]


class SourceSpan(BaseModel):
    start: int
    end: int


class Evidence(BaseModel):
    source_id: str
    quote: str | None = None
    source_span: SourceSpan | None = None


class Source(BaseModel):
    id: str
    kind: SourceKind
    title: str
    uri: str | None = None
    text: str | None = None
    created_at: str
    credibility: float = 0.5


class Concept(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    definition: str | None = None
    domain: str | None = None


class Claim(BaseModel):
    id: str
    text: str
    polarity: ClaimPolarity
    confidence: float
    as_of: str | None = None
    status: ClaimStatus
    evidence: list[Evidence]
    opposed_claim_ids: list[str] = Field(default_factory=list)


class Goal(BaseModel):
    id: str
    title: str
    question: str
    status: GoalStatus


class Misconception(BaseModel):
    id: str
    text: str
    claim_id: str
    goal_id: str
    count: int = 1
    correct_streak: int = 0
    last_seen_at: str
    status: Literal["active", "resolved"] = "active"
    verdict: Literal["gap", "contrary"]


class MisconceptionRef(BaseModel):
    id: str
    text: str
    claim_id: str
    claim_label: str | None = None
    count: int = 1
    status: str = "active"
    verdict: str | None = None


class DecisionOption(BaseModel):
    id: str
    label: str
    summary: str
    supporting_claim_ids: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    id: str
    goal_id: str
    question: str
    options: list[DecisionOption]
    chosen_option_id: str | None = None
    rationale: str | None = None
    outcome: str | None = None
    status: DecisionStatus


class Relation(BaseModel):
    id: str
    from_id: str
    to_id: str
    type: RelationType
    weight: float | None = None
    source_id: str | None = None


class GateCheck(BaseModel):
    gate: GateName
    passed: bool
    note: str


class InboxItem(BaseModel):
    id: str
    source_id: str
    title: str
    snippet: str
    status: InboxStatus
    verdict: GateVerdict
    checks: list[GateCheck]
    gap_score: float = 0.0
    gap_note: str | None = None


class GraphNode(BaseModel):
    id: str
    kind: NodeKind
    label: str
    subtitle: str | None = None
    status: str | None = None


class EvidenceExcerpt(BaseModel):
    source_id: str
    source_title: str
    aligned: bool
    claim_id: str | None = None
    claim_text: str | None = None
    quote: str | None = None
    source_span: SourceSpan | None = None
    before: str = ""
    hit: str = ""
    after: str = ""
    note: str | None = None


class NodeDetail(BaseModel):
    id: str
    kind: NodeKind
    label: str
    status: str | None = None
    summary: str | None = None
    polarity: str | None = None
    confidence: float | None = None
    definition: str | None = None
    aliases: list[str] = Field(default_factory=list)
    domain: str | None = None
    uri: str | None = None
    body: str | None = None
    question: str | None = None
    options: list[DecisionOption] = Field(default_factory=list)
    chosen_option_id: str | None = None
    rationale: str | None = None
    outcome: str | None = None
    opposed_claim_ids: list[str] = Field(default_factory=list)
    claim_id: str | None = None
    count: int | None = None
    verdict: str | None = None
    excerpts: list[EvidenceExcerpt] = Field(default_factory=list)
    neighbors: list[GraphNode] = Field(default_factory=list)


class DecisionBrief(BaseModel):
    id: str
    decision_id: str
    question: str
    options: list[DecisionOption]
    evidence_claim_ids: list[str]
    unknowns: list[str]
    skeptic: str
    recommendation: str | None = None
    chosen_option_id: str | None = None
    rationale: str | None = None
    outcome: str | None = None
    prior_decisions: list["PriorDecisionRef"] = Field(default_factory=list)


class GroundedRef(BaseModel):
    id: str
    kind: NodeKind
    label: str
    status: str | None = None
    quote: str | None = None
    source_id: str | None = None
    relation: str | None = None
    layer: Literal["keep", "lookup"] | None = None


class LinkCandidate(BaseModel):
    from_id: str
    to_id: str
    from_kind: NodeKind
    to_kind: NodeKind
    from_label: str
    to_label: str


class TransferRef(BaseModel):
    from_id: str
    from_label: str
    to_id: str
    to_label: str
    path_ids: list[str] = Field(default_factory=list)
    reason: str = "同一类取舍"


class GroundedAnswer(BaseModel):
    direct: list[GroundedRef] = Field(default_factory=list)
    lookup: list[GroundedRef] = Field(default_factory=list)
    evidence: list[GroundedRef] = Field(default_factory=list)
    related: list[GroundedRef] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    unlinked: bool = False
    link_candidates: list[LinkCandidate] = Field(default_factory=list)
    transfers: list[TransferRef] = Field(default_factory=list)
    cross_topic: list["CrossTopicHit"] = Field(default_factory=list)
    prior_decisions: list["PriorDecisionRef"] = Field(default_factory=list)


class ProbeOption(BaseModel):
    id: str
    label: str
    claim_id: str | None = None


class Probe(BaseModel):
    id: str
    prompt: str
    kind: Literal["choice", "short"]
    target_claim_id: str
    options: list[ProbeOption] = Field(default_factory=list)
    status: Literal["open", "graded"] = "open"


class ProbeGrade(BaseModel):
    verdict: Literal["correct", "gap", "contrary"]
    target_claim_id: str
    cited_claim_ids: list[str] = Field(default_factory=list)
    correction: str
    selected_option_id: str | None = None
    answer_text: str | None = None
    misconception_id: str | None = None


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    claim_ids: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    grounded: GroundedAnswer | None = None
    probe: Probe | None = None
    grade: ProbeGrade | None = None
    misconceptions: list[MisconceptionRef] = Field(default_factory=list)
    lane: Literal["learn", "decision"] = "learn"
    goal_id: str | None = None


class KnowledgeHit(BaseModel):
    id: str
    kind: NodeKind
    label: str
    snippet: str | None = None
    status: str | None = None
    score: float
    path_ids: list[str] = Field(default_factory=list)
    layer: Literal["keep", "lookup"] | None = None


class KnowledgeSearchResponse(BaseModel):
    query: str
    goal_id: str | None = None
    concepts: list[KnowledgeHit] = Field(default_factory=list)
    claims: list[KnowledgeHit] = Field(default_factory=list)
    sources: list[KnowledgeHit] = Field(default_factory=list)
    unknown: bool = False


class GraphSnapshot(BaseModel):
    nodes: list[GraphNode]
    edges: list[Relation]


class PracticeStat(BaseModel):
    goal_id: str
    claim_id: str
    correct_count: int = 0
    contrary_count: int = 0
    gap_count: int = 0
    use_count: int = 0
    last_practiced_at: str | None = None
    next_review_at: str | None = None
    interval_index: int = 0


class MasteryItem(BaseModel):
    id: str
    kind: Literal["claim", "concept"]
    label: str
    status: Literal["mastered", "weak", "missing", "ready"]
    reason: str
    claim_ids: list[str] = Field(default_factory=list)


class ContrastCard(BaseModel):
    left_id: str
    left_label: str
    right_id: str
    right_label: str


class ReviewItem(BaseModel):
    claim_id: str
    label: str
    due: bool
    reason: str
    next_review_at: str | None = None


class GapAdvice(BaseModel):
    id: str
    kind: Literal["claim", "concept"]
    label: str
    need: Literal["opposition", "evidence", "claim"]
    advice: str


class TopicLearn(BaseModel):
    goal_id: str | None = None
    depth: float = 0.0
    breadth: float = 0.0
    trend: str = ""
    mastered: int = 0
    weak: int = 0
    missing: int = 0
    ready: int = 0
    claims: list[MasteryItem] = Field(default_factory=list)
    concepts: list[MasteryItem] = Field(default_factory=list)
    contrasts: list[ContrastCard] = Field(default_factory=list)
    reviews: list[ReviewItem] = Field(default_factory=list)
    gaps: list[GapAdvice] = Field(default_factory=list)


class PackItem(BaseModel):
    id: str
    label: str
    layer: Literal["keep", "lookup"]
    reason: str = ""
    overridden: bool = False
    source_id: str | None = None


class OutlineChapter(BaseModel):
    id: str
    title: str
    kind: Literal["concept", "claim", "overview"] = "concept"
    summary: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    child_count: int = 0
    pack_keep: list[PackItem] = Field(default_factory=list)
    pack_lookup: list[PackItem] = Field(default_factory=list)


class TopicOutline(BaseModel):
    goal_id: str | None = None
    title: str = ""
    intro: str = ""
    chapters: list[OutlineChapter] = Field(default_factory=list)
    loose_claims: list[OutlineChapter] = Field(default_factory=list)


class Workbench(BaseModel):
    goals: list[Goal]
    inbox: list[InboxItem]
    graph: GraphSnapshot
    brief: DecisionBrief | None
    messages: list[ChatMessage]
    learn: TopicLearn | None = None
    outline: TopicOutline | None = None
    hangs: list[HangProposal] = Field(default_factory=list)
    today: TodayBoard | None = None
    profile: Profile | None = None
    plays: list[Play] = Field(default_factory=list)
    play_context: PlayContext | None = None


class CreateGoalRequest(BaseModel):
    title: str
    question: str = ""


class IngestSourceRequest(BaseModel):
    kind: SourceKind = "note"
    title: str = ""
    text: str = ""
    uri: str | None = None


class ChatRequest(BaseModel):
    content: str
    pinned_node_ids: list[str] = Field(default_factory=list)
    expand_cross_topic: bool = False


class GradeProbeRequest(BaseModel):
    option_id: str | None = None
    text: str | None = None


class StartReviewRequest(BaseModel):
    claim_id: str | None = None


class CommitBriefRequest(BaseModel):
    option_id: str
    rationale: str | None = None


class ComposeBriefRequest(BaseModel):
    question: str | None = None
    pinned_node_ids: list[str] = Field(default_factory=list)
    use_model: bool = True


class ReviewBriefRequest(BaseModel):
    outcome: str


class CaptureLessonRequest(BaseModel):
    message_id: str
    chapter_id: str


class LinkRelationRequest(BaseModel):
    from_id: str
    to_id: str
    message_id: str | None = None


class ScratchNoteRequest(BaseModel):
    text: str
    title: str = ""


class Play(BaseModel):
    id: PlayId
    title: str
    summary: str
    steps: list[str] = Field(default_factory=list)
    kinds: list[SourceKind] = Field(default_factory=list)


class PlayContext(BaseModel):
    play_id: PlayId
    title: str
    hint: str
    at: str


class RunPlayRequest(BaseModel):
    play_id: PlayId
    kind: SourceKind | None = None
    title: str = ""
    text: str = ""
    uri: str | None = None
    compose_brief: bool = False


class RunPlayResult(BaseModel):
    play: Play
    inbox: InboxItem
    brief: DecisionBrief | None = None
    next_hint: str = ""


class HangCandidate(BaseModel):
    node_id: str
    kind: Literal["concept", "goal"]
    label: str
    score: float = 0.0
    reason: str = ""


class IndustryHint(BaseModel):
    title: str
    url: str
    snippet: str = ""
    matched_node_id: str | None = None
    matched_label: str = ""
    reason: str = ""


class HangProposal(BaseModel):
    source_id: str
    inbox_id: str | None = None
    claim_ids: list[str] = Field(default_factory=list)
    candidates: list[HangCandidate] = Field(default_factory=list)
    proposed_names: list[str] = Field(default_factory=list)
    industry_hints: list[IndustryHint] = Field(default_factory=list)
    pack_keep: list[PackItem] = Field(default_factory=list)
    pack_lookup: list[PackItem] = Field(default_factory=list)


class SetClaimLayerRequest(BaseModel):
    layer: Literal["keep", "lookup"] | None = None


class ConfirmHangRequest(BaseModel):
    claim_ids: list[str]
    target_id: str = ""
    new_name: str = ""


class MergeConceptsRequest(BaseModel):
    keep_id: str
    drop_id: str


class Profile(BaseModel):
    domains: list[str] = Field(default_factory=list)
    role: str = ""
    language: str = "zh"
    prefer_own_notes: bool = True
    skip_candidates: bool = True


class PriorDecisionRef(BaseModel):
    decision_id: str
    question: str
    chosen_label: str = ""
    outcome: str | None = None
    status: str = ""


class CrossTopicHit(BaseModel):
    goal_id: str
    goal_title: str
    claim_id: str
    label: str


class TodayItem(BaseModel):
    kind: Literal["review", "inbox", "decision", "note"]
    id: str
    title: str
    detail: str = ""


class TodayBoard(BaseModel):
    reviews: list[TodayItem] = Field(default_factory=list)
    inbox: list[TodayItem] = Field(default_factory=list)
    decisions: list[TodayItem] = Field(default_factory=list)
    notes: list[TodayItem] = Field(default_factory=list)


class WeeklyReport(BaseModel):
    title: str
    markdown: str
    claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    decision_ids: list[str] = Field(default_factory=list)
