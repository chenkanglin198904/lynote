export type NodeKind = "source" | "concept" | "claim" | "goal" | "decision" | "misconception";
export type SourceKind = "markdown" | "pdf" | "url" | "note" | "audio" | "video";
export type PlayId = "read_article" | "after_meeting";
export type ClaimStatus = "candidate" | "confirmed" | "disputed" | "deprecated";
export type GoalStatus = "active" | "paused" | "resolved";
export type DecisionStatus = "draft" | "committed" | "reviewed";
export type InboxStatus = "pending" | "accepted" | "rejected";
export type GateName =
  | "goal_alignment"
  | "quality"
  | "novelty"
  | "actionability"
  | "maintenance_cost";
export type GateVerdict = "accept" | "reject" | "review";
export type RelationType =
  | "about"
  | "belongs_to"
  | "supports"
  | "contradicts"
  | "evidenced_by"
  | "decides"
  | "related_to";

export interface Goal {
  id: string;
  title: string;
  question: string;
  status: GoalStatus;
}

export interface GateCheck {
  gate: GateName;
  passed: boolean;
  note: string;
}

export interface InboxItem {
  id: string;
  source_id: string;
  title: string;
  snippet: string;
  status: InboxStatus;
  verdict: GateVerdict;
  checks: GateCheck[];
  gap_score?: number;
  gap_note?: string | null;
}

export interface GraphNode {
  id: string;
  kind: NodeKind;
  label: string;
  subtitle?: string | null;
  status?: string | null;
}

export interface Relation {
  id: string;
  from_id: string;
  to_id: string;
  type: RelationType;
  weight?: number | null;
  source_id?: string | null;
}

export interface DecisionOption {
  id: string;
  label: string;
  summary: string;
  supporting_claim_ids: string[];
}

export interface DecisionBrief {
  id: string;
  decision_id: string;
  question: string;
  options: DecisionOption[];
  evidence_claim_ids: string[];
  unknowns: string[];
  skeptic: string;
  recommendation?: string | null;
  chosen_option_id?: string | null;
  rationale?: string | null;
  outcome?: string | null;
  prior_decisions?: PriorDecisionRef[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  claim_ids: string[];
  unknowns: string[];
  grounded?: GroundedAnswer | null;
  probe?: Probe | null;
  grade?: ProbeGrade | null;
  misconceptions?: MisconceptionRef[];
  lane?: "learn" | "decision";
  goal_id?: string | null;
}

export interface ProbeOption {
  id: string;
  label: string;
  claim_id?: string | null;
}

export interface Probe {
  id: string;
  prompt: string;
  kind: "choice" | "short";
  target_claim_id: string;
  options: ProbeOption[];
  status: "open" | "graded";
}

export interface ProbeGrade {
  verdict: "correct" | "gap" | "contrary";
  target_claim_id: string;
  cited_claim_ids: string[];
  correction: string;
  selected_option_id?: string | null;
  answer_text?: string | null;
  misconception_id?: string | null;
}

export interface MisconceptionRef {
  id: string;
  text: string;
  claim_id: string;
  claim_label?: string | null;
  count: number;
  status: string;
  verdict?: string | null;
}

export interface GroundedRef {
  id: string;
  kind: NodeKind;
  label: string;
  status?: string | null;
  quote?: string | null;
  source_id?: string | null;
  relation?: string | null;
  layer?: "keep" | "lookup" | null;
}

export interface GroundedAnswer {
  direct: GroundedRef[];
  lookup?: GroundedRef[];
  evidence: GroundedRef[];
  related: GroundedRef[];
  unknowns: string[];
  unlinked?: boolean;
  link_candidates?: LinkCandidate[];
  transfers?: TransferRef[];
  cross_topic?: CrossTopicHit[];
  prior_decisions?: PriorDecisionRef[];
}

export interface TransferRef {
  from_id: string;
  from_label: string;
  to_id: string;
  to_label: string;
  path_ids: string[];
  reason: string;
}

export interface LinkCandidate {
  from_id: string;
  to_id: string;
  from_kind: NodeKind;
  to_kind: NodeKind;
  from_label: string;
  to_label: string;
}

export interface KnowledgeHit {
  id: string;
  kind: NodeKind;
  label: string;
  snippet?: string | null;
  status?: string | null;
  score: number;
  path_ids: string[];
  layer?: "keep" | "lookup" | null;
}

export interface KnowledgeSearchResponse {
  query: string;
  goal_id?: string | null;
  concepts: KnowledgeHit[];
  claims: KnowledgeHit[];
  sources: KnowledgeHit[];
  unknown: boolean;
}

export interface Workbench {
  goals: Goal[];
  inbox: InboxItem[];
  graph: { nodes: GraphNode[]; edges: Relation[] };
  brief: DecisionBrief | null;
  messages: ChatMessage[];
  learn?: TopicLearn | null;
  outline?: TopicOutline | null;
  hangs?: HangProposal[];
  today?: TodayBoard | null;
  profile?: Profile | null;
  plays?: Play[];
  play_context?: PlayContext | null;
}

export interface Play {
  id: PlayId;
  title: string;
  summary: string;
  steps: string[];
  kinds: SourceKind[];
}

export interface PlayContext {
  play_id: PlayId;
  title: string;
  hint: string;
  at: string;
}

export interface RunPlayResult {
  play: Play;
  inbox: InboxItem;
  brief?: DecisionBrief | null;
  next_hint: string;
}

export interface MasteryItem {
  id: string;
  kind: "claim" | "concept";
  label: string;
  status: "mastered" | "weak" | "missing" | "ready";
  reason: string;
  claim_ids: string[];
}

export interface ContrastCard {
  left_id: string;
  left_label: string;
  right_id: string;
  right_label: string;
}

export interface ReviewItem {
  claim_id: string;
  label: string;
  due: boolean;
  reason: string;
  next_review_at?: string | null;
}

export interface GapAdvice {
  id: string;
  kind: "claim" | "concept";
  label: string;
  need: "opposition" | "evidence" | "claim";
  advice: string;
}

export interface TopicLearn {
  goal_id?: string | null;
  depth: number;
  breadth: number;
  trend: string;
  mastered: number;
  weak: number;
  missing: number;
  ready: number;
  claims: MasteryItem[];
  concepts: MasteryItem[];
  contrasts: ContrastCard[];
  reviews: ReviewItem[];
  gaps: GapAdvice[];
}

export interface PackItem {
  id: string;
  label: string;
  layer: "keep" | "lookup";
  reason: string;
  overridden?: boolean;
  source_id?: string | null;
}

export interface OutlineChapter {
  id: string;
  title: string;
  kind: "concept" | "claim" | "overview";
  summary: string;
  claim_ids: string[];
  child_count: number;
  pack_keep?: PackItem[];
  pack_lookup?: PackItem[];
}

export interface TopicOutline {
  goal_id?: string | null;
  title: string;
  intro: string;
  chapters: OutlineChapter[];
  loose_claims: OutlineChapter[];
}

export interface HangCandidate {
  node_id: string;
  kind: "concept" | "goal";
  label: string;
  score: number;
  reason: string;
}

export interface HangProposal {
  source_id: string;
  inbox_id?: string | null;
  claim_ids: string[];
  candidates: HangCandidate[];
  proposed_names?: string[];
  industry_hints?: IndustryHint[];
  pack_keep?: PackItem[];
  pack_lookup?: PackItem[];
}

export interface IndustryHint {
  title: string;
  url: string;
  snippet?: string;
  matched_node_id?: string | null;
  matched_label?: string;
  reason?: string;
}

export interface Profile {
  domains: string[];
  role: string;
  language: string;
  prefer_own_notes: boolean;
  skip_candidates: boolean;
}

export interface PriorDecisionRef {
  decision_id: string;
  question: string;
  chosen_label: string;
  outcome?: string | null;
  status: string;
}

export interface CrossTopicHit {
  goal_id: string;
  goal_title: string;
  claim_id: string;
  label: string;
}

export interface TodayItem {
  kind: "review" | "inbox" | "decision" | "note";
  id: string;
  title: string;
  detail: string;
}

export interface TodayBoard {
  reviews: TodayItem[];
  inbox: TodayItem[];
  decisions: TodayItem[];
  notes: TodayItem[];
}

export interface WeeklyReport {
  title: string;
  markdown: string;
  claim_ids: string[];
  source_ids: string[];
  decision_ids: string[];
}

export interface SourceSpan {
  start: number;
  end: number;
}

export interface EvidenceExcerpt {
  source_id: string;
  source_title: string;
  aligned: boolean;
  claim_id?: string | null;
  claim_text?: string | null;
  quote?: string | null;
  source_span?: SourceSpan | null;
  before: string;
  hit: string;
  after: string;
  note?: string | null;
}

export interface NodeDetail {
  id: string;
  kind: NodeKind;
  label: string;
  status?: string | null;
  summary?: string | null;
  polarity?: string | null;
  confidence?: number | null;
  definition?: string | null;
  aliases: string[];
  domain?: string | null;
  uri?: string | null;
  body?: string | null;
  question?: string | null;
  options: DecisionOption[];
  chosen_option_id?: string | null;
  rationale?: string | null;
  outcome?: string | null;
  opposed_claim_ids: string[];
  claim_id?: string | null;
  count?: number | null;
  verdict?: string | null;
  excerpts: EvidenceExcerpt[];
  neighbors: GraphNode[];
}
