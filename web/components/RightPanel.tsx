"use client";

import { useEffect, useState, type ReactNode } from "react";
import { fetchNodeDetail } from "@/lib/api";
import { emptyCopy } from "@/lib/copy";
import { messagesInLane } from "@/lib/session";
import type { ChatMessage, CrossTopicHit, GroundedAnswer, GroundedRef, LinkCandidate, MisconceptionRef, NodeDetail, PriorDecisionRef, Probe, ProbeGrade, Workbench } from "@/lib/types";
import { SourceExcerpt } from "./SourceExcerpt";

type Tab = "brief" | "chat" | "inspect";

const KIND_LABEL: Record<string, string> = {
  goal: "主题",
  concept: "概念",
  claim: "主张",
  decision: "决策",
  source: "来源",
  misconception: "误区",
};

export function RightPanel({
  data,
  busy,
  pinned,
  selectedId,
  courseMode = false,
  captureChapterId = null,
  onChat,
  onCompose,
  onCommit,
  onReview,
  onSelectNode,
  onGradeProbe,
  onResolveMisconception,
  onLinkRelated,
  onCaptureLesson,
  onMergeConcepts,
  onDeprecateClaim,
  focusChat = 0,
  focusBrief = 0,
}: {
  data: Workbench | null;
  busy: boolean;
  pinned: string[];
  selectedId: string | null;
  courseMode?: boolean;
  captureChapterId?: string | null;
  onChat: (content: string, expandCrossTopic?: boolean) => Promise<void>;
  onCompose: () => Promise<void>;
  onCommit: (optionId: string, rationale: string) => Promise<void>;
  onReview: (outcome: string) => Promise<void>;
  onSelectNode: (id: string) => void;
  onGradeProbe: (probeId: string, payload: { option_id?: string; text?: string }) => Promise<void>;
  onResolveMisconception: (id: string) => Promise<void>;
  onLinkRelated: (fromId: string, toId: string, messageId: string) => Promise<void>;
  onCaptureLesson?: (messageId: string) => Promise<void>;
  onMergeConcepts?: (keepId: string, dropId: string) => Promise<void>;
  onDeprecateClaim?: (claimId: string) => Promise<void>;
  focusChat?: number;
  focusBrief?: number;
}) {
  const [tab, setTab] = useState<Tab>("brief");
  const [draft, setDraft] = useState("");
  const [expandCross, setExpandCross] = useState(false);
  const [outcomeDraft, setOutcomeDraft] = useState("");
  const [pendingOptionId, setPendingOptionId] = useState<string | null>(null);
  const [rationaleDraft, setRationaleDraft] = useState("");
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const brief = data?.brief ?? null;
  const activeGoal = data?.goals.find((goal) => goal.status === "active") ?? data?.goals[0] ?? null;
  const learnMessages = messagesInLane(data?.messages ?? [], "learn", activeGoal?.id ?? null);
  const decisionMessages = messagesInLane(data?.messages ?? [], "decision", activeGoal?.id ?? null);
  const selected = data?.graph.nodes.find((node) => node.id === selectedId);
  const decisionStatus = data?.graph.nodes.find((node) => node.id === brief?.decision_id)?.status;
  const locked = decisionStatus === "committed" || decisionStatus === "reviewed";
  const reviewed = decisionStatus === "reviewed";

  useEffect(() => {
    setOutcomeDraft(brief?.outcome ?? "");
    if (brief?.rationale) setRationaleDraft(brief.rationale);
    if (locked) setPendingOptionId(null);
  }, [brief?.id, brief?.outcome, brief?.rationale, locked]);

  useEffect(() => {
    if (focusChat) setTab("chat");
  }, [focusChat]);

  useEffect(() => {
    if (courseMode) setTab((current) => (current === "brief" ? "inspect" : current));
  }, [courseMode]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setDetailError(null);
      return;
    }
    setTab("inspect");
    let cancelled = false;
    fetchNodeDetail(selectedId)
      .then((next) => {
        if (cancelled) return;
        setDetail(next);
        setDetailError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setDetail(null);
        setDetailError(err instanceof Error ? err.message : "无法读取节点出处");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    if (focusBrief) setTab("brief");
  }, [focusBrief]);

  return (
    <aside className="flex min-h-0 flex-col border-l border-line bg-panel">
      <div className="flex border-b border-line">
        {courseMode ? null : (
          <TabButton active={tab === "brief"} onClick={() => setTab("brief")}>
            决策简报
          </TabButton>
        )}
        <TabButton active={tab === "inspect"} onClick={() => setTab("inspect")}>
          出处
        </TabButton>
        <TabButton active={tab === "chat"} onClick={() => setTab("chat")}>
          {courseMode ? "问答" : "学习"}
        </TabButton>
      </div>

      {selected ? (
        <div className="border-b border-line px-4 py-3 text-xs text-muted">
          选中 {KIND_LABEL[selected.kind] ?? selected.kind}：{selected.label}
          {pinned.includes(selected.id) ? " · 已钉住" : " · 双击图谱钉住"}
        </div>
      ) : null}

      {tab === "brief" && !courseMode ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <p className="mb-4 text-xs leading-5 text-muted">
            用当前主题里的主张做选择。学知识点请切到「学习」，两条会话互不混写。
          </p>
          <button
            disabled={busy}
            onClick={() => void onCompose()}
            className="mb-4 w-full border border-gold/40 bg-gold/10 px-3 py-2 text-sm text-gold disabled:opacity-50"
          >
            按当前主题重算简报
          </button>
          {brief ? (
            <div className="space-y-4">
              <h2 className="font-serif text-xl leading-7">{brief.question}</h2>
              {(brief.prior_decisions ?? []).length > 0 ? (
                <section className="border border-line bg-raised p-3">
                  <h3 className="text-xs uppercase tracking-[0.16em] text-gold">上次同类决策</h3>
                  <ul className="mt-2 space-y-2">
                    {brief.prior_decisions!.map((item) => (
                      <li key={item.decision_id}>
                        <button type="button" className="text-left text-sm hover:text-gold" onClick={() => onSelectNode(item.decision_id)}>
                          {item.question}
                          {item.chosen_label ? ` → ${item.chosen_label}` : ""}
                        </button>
                        {item.outcome ? <p className="mt-1 text-xs text-muted">当时结果：{item.outcome}</p> : null}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {brief.recommendation ? (
                <p className="text-sm leading-6 text-paper/90">{brief.recommendation}</p>
              ) : null}
              <div className="space-y-2">
                {brief.options.map((option) => {
                  const chosen = brief.chosen_option_id === option.id;
                  const pending = pendingOptionId === option.id;
                  return (
                    <div
                      key={option.id}
                      className={`border bg-raised p-3 ${
                        chosen || pending ? "border-moss/70" : "border-line"
                      }`}
                    >
                      <button
                        disabled={busy || locked}
                        onClick={() => setPendingOptionId(option.id)}
                        className="w-full text-left hover:text-gold disabled:opacity-60"
                      >
                        <p className="text-sm font-medium">{option.label}</p>
                        <p className="mt-1 text-xs leading-5 text-muted">{option.summary}</p>
                        <p className="mt-2 text-[11px] text-gold">
                          {chosen && reviewed
                            ? "已采纳，并已复盘"
                            : chosen
                              ? "已写入图谱，待复盘"
                              : pending
                                ? "已选定，写下理由后确认"
                                : locked
                                  ? "未选此项"
                                  : "点选此项，然后写理由"}
                        </p>
                      </button>
                      <IdChips ids={option.supporting_claim_ids} onSelect={onSelectNode} />
                    </div>
                  );
                })}
              </div>
              {!locked && pendingOptionId ? (
                <section className="border border-gold/40 bg-gold/10 p-3">
                  <h3 className="text-xs uppercase tracking-[0.16em] text-gold">采纳理由</h3>
                  <p className="mt-2 text-xs leading-5 text-muted">
                    人写理由。AI 不代填。空理由不能写回 Decision。
                  </p>
                  <textarea
                    className="mt-3 h-20 w-full resize-none border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-gold"
                    placeholder="为什么选这一项？最强反对意见为什么暂时不成立？"
                    value={rationaleDraft}
                    onChange={(event) => setRationaleDraft(event.target.value)}
                  />
                  <button
                    disabled={busy || !rationaleDraft.trim()}
                    onClick={() => void onCommit(pendingOptionId, rationaleDraft.trim())}
                    className="mt-2 w-full border border-gold/50 bg-gold/15 px-3 py-2 text-sm text-gold disabled:opacity-50"
                  >
                    确认写回 Decision
                  </button>
                </section>
              ) : null}
              {brief.rationale ? (
                <p className="text-sm leading-6 text-paper/90">当时理由：{brief.rationale}</p>
              ) : null}
              {locked ? (
                <section className="border border-moss/40 bg-moss/10 p-3">
                  <h3 className="text-xs uppercase tracking-[0.16em] text-moss">事后结果</h3>
                  <p className="mt-2 text-xs leading-5 text-muted">
                    人写回真实结果。AI 不代填、不改主张。
                  </p>
                  <textarea
                    className="mt-3 h-24 w-full resize-none border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-gold"
                    placeholder="做完之后实际发生了什么？选对了还是选错了？"
                    value={outcomeDraft}
                    onChange={(event) => setOutcomeDraft(event.target.value)}
                  />
                  <button
                    disabled={busy || !outcomeDraft.trim()}
                    onClick={() => void onReview(outcomeDraft)}
                    className="mt-2 w-full border border-moss/50 bg-moss/15 px-3 py-2 text-sm text-moss disabled:opacity-50"
                  >
                    {reviewed ? "更新复盘" : "写回复盘"}
                  </button>
                </section>
              ) : null}
              <section>
                <h3 className="text-xs uppercase tracking-[0.16em] text-clay">反方</h3>
                <p className="mt-2 text-sm leading-6 text-paper/85">{brief.skeptic}</p>
              </section>
              <section>
                <h3 className="text-xs uppercase tracking-[0.16em] text-muted">未知</h3>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm leading-6 text-muted">
                  {brief.unknowns.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
              <IdChips ids={brief.evidence_claim_ids} onSelect={onSelectNode} label="简报引用" />
              <DecisionLog messages={decisionMessages} />
            </div>
          ) : (
            <p className="text-sm leading-6 text-muted">
              {data?.goals.length ? emptyCopy.noBrief : emptyCopy.noGoal}
            </p>
          )}
        </div>
      ) : null}

      {tab === "chat" ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4">
            <p className="text-xs leading-5 text-muted">
              {activeGoal
                ? courseMode
                  ? `当前章节问答 · ${activeGoal.title}。只引用图上主张；讲解后会反问。有依据的回答可收入当前章节，不会在图外编知识点。`
                  : `学习会话 · ${activeGoal.title}。只引用这个主题图上的主张；拍板去「决策简报」。`
                : emptyCopy.noGoal}
            </p>
            {learnMessages.length === 0 ? (
              <p className="text-sm leading-6 text-muted">{emptyCopy.noLearnChat}</p>
            ) : null}
            {learnMessages.map((message) => (
              <article key={message.id} className="border border-line bg-raised p-3">
                <p className="text-[11px] uppercase tracking-[0.14em] text-muted">
                  {message.role === "user" ? "你" : "LyNote"}
                </p>
                {message.role === "assistant" && message.grounded ? (
                  <GroundedBody
                    answer={message.grounded}
                    busy={busy}
                    messageId={message.id}
                    canCapture={Boolean(courseMode && captureChapterId && onCaptureLesson)}
                    onSelect={onSelectNode}
                    onLink={onLinkRelated}
                    onCapture={onCaptureLesson}
                  />
                ) : (
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                )}
                {(message.misconceptions ?? []).length > 0 ? (
                  <MisconceptionsCard
                    items={message.misconceptions ?? []}
                    busy={busy}
                    onSelect={onSelectNode}
                    onResolve={onResolveMisconception}
                  />
                ) : null}
                {message.probe ? (
                  <ProbeCard
                    probe={message.probe}
                    grade={message.grade}
                    busy={busy}
                    onSelect={onSelectNode}
                    onGrade={(payload) => onGradeProbe(message.probe!.id, payload)}
                  />
                ) : null}
                <IdChips ids={message.claim_ids} onSelect={onSelectNode} />
                {!message.grounded && message.unknowns.length > 0 ? (
                  <p className="mt-2 text-[11px] text-clay">未知 {message.unknowns.join(" · ")}</p>
                ) : null}
              </article>
            ))}
          </div>
          <form
            className="border-t border-line p-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (!draft.trim()) return;
              const content = draft.trim();
              setDraft("");
              void onChat(content, expandCross);
            }}
          >
            <textarea
              className="h-20 w-full resize-none rounded-sm border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-gold"
              placeholder={
                courseMode
                  ? "针对当前章节提问。讲解后会反问。没有证据不会编节点。有依据的回答可收入当前章节。"
                  : pinned.length
                    ? `基于 ${pinned.length} 个钉住节点提问`
                    : "针对当前主题提问。讲解后会出一道追问。没有证据不会编节点。拍板请用决策简报。"
              }
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
            <label className="mt-2 flex items-center gap-2 text-xs text-muted">
              <input type="checkbox" checked={expandCross} onChange={(event) => setExpandCross(event.target.checked)} />
              也搜其他主题（默认不混进直答）
            </label>
            <button
              type="submit"
              disabled={busy}
              className="mt-2 w-full border border-gold/50 bg-gold/10 px-3 py-2 text-sm text-gold disabled:opacity-50"
            >
              召回后讲解
            </button>
          </form>
        </div>
      ) : null}

      {tab === "inspect" ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {!selectedId ? (
            <p className="text-sm leading-6 text-muted">{emptyCopy.noInspect}</p>
          ) : detailError ? (
            <p className="text-sm text-clay">{detailError}</p>
          ) : !detail || detail.id !== selectedId ? (
            <p className="text-sm text-muted">正在定位出处…</p>
          ) : (
            <NodeInspector
              detail={detail}
              busy={busy}
              concepts={(data?.graph.nodes ?? []).filter((node) => node.kind === "concept")}
              onSelectNode={onSelectNode}
              onResolve={onResolveMisconception}
              onMerge={onMergeConcepts}
              onDeprecate={onDeprecateClaim}
            />
          )}
        </div>
      ) : null}
    </aside>
  );
}

function NodeInspector({
  detail,
  busy,
  concepts = [],
  onSelectNode,
  onResolve,
  onMerge,
  onDeprecate,
}: {
  detail: NodeDetail;
  busy: boolean;
  concepts?: { id: string; label: string }[];
  onSelectNode: (id: string) => void;
  onResolve: (id: string) => Promise<void>;
  onMerge?: (keepId: string, dropId: string) => Promise<void>;
  onDeprecate?: (claimId: string) => Promise<void>;
}) {
  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs uppercase tracking-[0.16em] text-muted">
          {KIND_LABEL[detail.kind] ?? detail.kind}
          {detail.status ? ` · ${detail.status}` : ""}
        </p>
        <h2 className="mt-2 font-serif text-xl leading-7">{detail.label}</h2>
        {detail.summary && detail.summary !== detail.label ? (
          <p className="mt-2 text-sm leading-6 text-paper/90">{detail.summary}</p>
        ) : null}
        {detail.kind === "misconception" ? (
          <p className="mt-2 text-sm leading-6 text-clay">
            出现 {detail.count ?? 1} 次
            {detail.verdict ? ` · ${detail.verdict === "contrary" ? "反了" : "漏了"}` : ""}
          </p>
        ) : null}
        {detail.polarity ? (
          <p className="mt-2 text-xs text-muted">
            {detail.polarity}
            {detail.confidence != null ? ` · 置信 ${detail.confidence}` : ""}
          </p>
        ) : null}
        {detail.definition ? <p className="mt-2 text-sm leading-6">{detail.definition}</p> : null}
        {detail.aliases.length > 0 ? (
          <p className="mt-2 text-xs text-muted">别名 {detail.aliases.join(" · ")}</p>
        ) : null}
        {detail.uri ? <p className="mt-2 break-all text-xs text-gold">{detail.uri}</p> : null}
        {detail.rationale ? <p className="mt-2 text-sm leading-6">理由：{detail.rationale}</p> : null}
        {detail.outcome ? <p className="mt-2 text-sm leading-6">复盘：{detail.outcome}</p> : null}
      </header>
      {detail.kind === "claim" && onDeprecate && detail.status !== "deprecated" ? (
        <button
          type="button"
          disabled={busy}
          className="w-full border border-line px-3 py-2 text-xs text-muted hover:border-gold hover:text-gold disabled:opacity-50"
          onClick={() => void onDeprecate(detail.id)}
        >
          标为过时（召回降权，不删历史）
        </button>
      ) : null}
      {detail.kind === "concept" && onMerge ? (
        <section>
          <h3 className="text-xs uppercase tracking-[0.16em] text-muted">合并到已有概念</h3>
          <p className="mt-1 text-[11px] leading-4 text-muted">只合并名称/边，不融合冲突主张。</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {concepts
              .filter((item) => item.id !== detail.id)
              .slice(0, 8)
              .map((item) => (
                <button
                  key={item.id}
                  type="button"
                  disabled={busy}
                  className="border border-line px-2 py-1 text-[11px] text-muted hover:border-gold hover:text-gold disabled:opacity-50"
                  onClick={() => void onMerge(item.id, detail.id)}
                >
                  并入 {item.label}
                </button>
              ))}
          </div>
        </section>
      ) : null}
      {detail.kind === "misconception" && detail.claim_id ? (
        <section>
          <h3 className="text-xs uppercase tracking-[0.16em] text-gold">反驳的主张</h3>
          {detail.question ? <p className="mt-2 text-sm leading-6">{detail.question}</p> : null}
          <IdChips ids={[detail.claim_id]} onSelect={onSelectNode} label="正确主张" />
          {detail.status === "active" ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void onResolve(detail.id)}
              className="mt-3 w-full border border-gold/40 bg-gold/10 px-3 py-2 text-sm text-gold disabled:opacity-50"
            >
              标记已纠正
            </button>
          ) : (
            <p className="mt-2 text-xs text-moss">已归档为纠正</p>
          )}
        </section>
      ) : null}
      {detail.options.length > 0 ? (
        <section className="space-y-2">
          {detail.options.map((option) => (
            <div key={option.id} className="border border-line bg-raised p-3">
              <p className="text-sm">
                {detail.chosen_option_id === option.id ? "已选 · " : ""}
                {option.label}
              </p>
              <p className="mt-1 text-xs text-muted">{option.summary}</p>
              <IdChips ids={option.supporting_claim_ids} onSelect={onSelectNode} />
            </div>
          ))}
        </section>
      ) : null}
      {detail.excerpts.length > 0 ? (
        <section className="space-y-3">
          <h3 className="text-xs uppercase tracking-[0.16em] text-gold">原文定位</h3>
          {detail.excerpts.map((excerpt, index) => (
            <SourceExcerpt
              key={`${excerpt.source_id}-${excerpt.claim_id ?? index}-${excerpt.source_span?.start ?? index}`}
              excerpt={excerpt}
              onOpenSource={onSelectNode}
              onOpenClaim={onSelectNode}
            />
          ))}
        </section>
      ) : detail.kind === "claim" || detail.kind === "source" ? (
        <p className="text-sm text-clay">没有可定位的出处。没有 source_span 的主张不能当证据。</p>
      ) : null}
      <IdChips ids={detail.opposed_claim_ids} onSelect={onSelectNode} label="对立主张" />
      {detail.neighbors.length > 0 ? (
        <section>
          <h3 className="text-xs uppercase tracking-[0.16em] text-muted">相邻节点</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {detail.neighbors.map((node) => (
              <button
                key={node.id}
                type="button"
                onClick={() => onSelectNode(node.id)}
                className="border border-line px-2 py-1 text-[11px] text-muted hover:border-gold hover:text-gold"
              >
                {KIND_LABEL[node.kind] ?? node.kind} {node.label}
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ProbeCard({
  probe,
  grade,
  busy,
  onSelect,
  onGrade,
}: {
  probe: Probe;
  grade?: ProbeGrade | null;
  busy: boolean;
  onSelect: (id: string) => void;
  onGrade: (payload: { option_id?: string; text?: string }) => Promise<void>;
}) {
  const [optionId, setOptionId] = useState(grade?.selected_option_id ?? "");
  const [text, setText] = useState(grade?.answer_text ?? "");
  const open = probe.status === "open" && !grade;
  const verdictLabel =
    grade?.verdict === "correct" ? "对" : grade?.verdict === "contrary" ? "反" : grade?.verdict === "gap" ? "漏" : null;

  return (
    <section className="mt-3 border border-gold/40 bg-gold/10 p-3">
      <h3 className="text-[10px] uppercase tracking-[0.16em] text-gold">追问</h3>
      <p className="mt-2 text-sm leading-6">{probe.prompt}</p>
      {open && probe.kind === "choice" ? (
        <div className="mt-2 space-y-2">
          {probe.options.map((option) => (
            <label key={option.id} className="flex cursor-pointer items-start gap-2 text-sm leading-6">
              <input
                type="radio"
                name={probe.id}
                className="mt-1"
                checked={optionId === option.id}
                onChange={() => setOptionId(option.id)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      ) : null}
      {open && probe.kind === "short" ? (
        <textarea
          className="mt-2 h-16 w-full resize-none border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-gold"
          placeholder="只许复述图上已有主张"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      ) : null}
      {open ? (
        <button
          type="button"
          disabled={busy || (probe.kind === "choice" ? !optionId : !text.trim())}
          onClick={() =>
            void onGrade(
              probe.kind === "choice" ? { option_id: optionId } : { text: text.trim() },
            )
          }
          className="mt-2 w-full border border-gold/50 bg-gold/15 px-3 py-2 text-sm text-gold disabled:opacity-50"
        >
          提交作答
        </button>
      ) : null}
      {grade ? (
        <div className="mt-2">
          <p className={`text-sm font-medium ${grade.verdict === "correct" ? "text-moss" : "text-clay"}`}>
            {verdictLabel} · {grade.correction}
          </p>
          <IdChips ids={grade.cited_claim_ids} onSelect={onSelect} label="批改引用" />
          {grade.misconception_id ? (
            <p className="mt-2 text-[11px] text-clay">已写入误区 {grade.misconception_id}</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function MisconceptionsCard({
  items,
  busy,
  onSelect,
  onResolve,
}: {
  items: MisconceptionRef[];
  busy: boolean;
  onSelect: (id: string) => void;
  onResolve: (id: string) => Promise<void>;
}) {
  return (
    <section className="mt-3 border border-clay/40 bg-clay/10 p-3">
      <h3 className="text-[10px] uppercase tracking-[0.16em] text-clay">常见误区</h3>
      <ul className="mt-2 space-y-2">
        {items.map((item) => (
          <li key={item.id} className="text-sm leading-6">
            <p>
              你上次把「{item.text}」当成对的（{item.count} 次）。
              {item.claim_label ? `图上应按：${item.claim_label}` : "见图上对应主张。"}
            </p>
            <div className="mt-1 flex flex-wrap gap-2">
              <button
                type="button"
                className="border border-line px-2 py-0.5 text-[11px] text-gold hover:border-gold"
                onClick={() => onSelect(item.claim_id)}
              >
                {item.claim_id}
              </button>
              <button
                type="button"
                className="border border-line px-2 py-0.5 text-[11px] text-muted hover:border-gold hover:text-gold"
                onClick={() => onSelect(item.id)}
              >
                {item.id}
              </button>
              {item.status === "active" ? (
                <button
                  type="button"
                  disabled={busy}
                  className="border border-gold/40 px-2 py-0.5 text-[11px] text-gold disabled:opacity-50"
                  onClick={() => void onResolve(item.id)}
                >
                  标记已纠正
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DecisionLog({ messages }: { messages: ChatMessage[] }) {
  return (
    <section>
      <h3 className="text-xs uppercase tracking-[0.16em] text-muted">本主题决策记录</h3>
      {messages.length === 0 ? (
        <p className="mt-2 text-sm leading-6 text-muted">{emptyCopy.noDecisionLog}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {messages.map((item) => (
            <li key={item.id} className="border border-line bg-raised p-3 text-sm leading-6">
              {item.content}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function GroundedBody({
  answer,
  busy,
  messageId,
  canCapture = false,
  onSelect,
  onLink,
  onCapture,
}: {
  answer: GroundedAnswer;
  busy: boolean;
  messageId: string;
  canCapture?: boolean;
  onSelect: (id: string) => void;
  onLink: (fromId: string, toId: string, messageId: string) => Promise<void>;
  onCapture?: (messageId: string) => Promise<void>;
}) {
  const candidates = answer.link_candidates ?? [];
  const lookup = answer.lookup ?? [];
  const cited = [...answer.direct, ...lookup].filter((item) => item.kind === "claim");
  return (
    <div className="mt-2 space-y-3">
      <GroundedSection title="直答">
        {answer.direct.length === 0 ? (
          <p className="text-sm leading-6 text-clay">当前主题里没有可引用的上层主张，不能编原理。</p>
        ) : (
          answer.direct.map((ref) => <RefLine key={`d-${ref.id}`} refItem={ref} onSelect={onSelect} />)
        )}
      </GroundedSection>
      <GroundedSection title="需要时再查">
        {lookup.length === 0 ? (
          <p className="text-sm text-muted">无</p>
        ) : (
          lookup.map((ref) => <RefLine key={`l-${ref.id}`} refItem={ref} onSelect={onSelect} />)
        )}
      </GroundedSection>
      <GroundedSection title="依据">
        {answer.evidence.length === 0 ? (
          <p className="text-sm text-muted">无</p>
        ) : (
          answer.evidence.map((ref, index) => (
            <RefLine key={`e-${ref.id}-${index}`} refItem={ref} onSelect={onSelect} quoteFirst />
          ))
        )}
      </GroundedSection>
      <GroundedSection title="联想">
        {(answer.transfers ?? []).map((item) => (
          <button
            key={`t-${item.from_id}-${item.to_id}`}
            type="button"
            className="block w-full text-left text-sm leading-6 text-gold hover:underline"
            onClick={() => onSelect(item.to_id)}
          >
            这和你已有的「{item.to_label}」是同一类取舍
          </button>
        ))}
        {answer.related.map((ref) => (
          <RefLine key={`r-${ref.relation}-${ref.id}`} refItem={ref} onSelect={onSelect} />
        ))}
        {(answer.transfers ?? []).length === 0 && answer.related.length === 0 ? (
          <UnlinkedHint
            unlinked={Boolean(answer.unlinked)}
            candidates={candidates}
            busy={busy}
            messageId={messageId}
            onSelect={onSelect}
            onLink={onLink}
          />
        ) : candidates.length > 0 ? (
          <UnlinkedHint
            unlinked={false}
            note="没有沿边找到同一类取舍。核对后可标成相关。"
            candidates={candidates}
            busy={busy}
            messageId={messageId}
            onSelect={onSelect}
            onLink={onLink}
          />
        ) : null}
      </GroundedSection>
      <GroundedSection title="边界">
        {answer.unknowns.length > 0 ? (
          <>
            {answer.unknowns.map((item) => (
              <p key={item} className="text-sm leading-6 text-clay">
                {item}
              </p>
            ))}
            {answer.direct.length === 0 && lookup.length === 0 ? (
              <p className="text-xs leading-5 text-muted">{emptyCopy.unknownNext}</p>
            ) : null}
          </>
        ) : (
          <p className="text-sm leading-6 text-muted">以上断言均可点开核对原文。</p>
        )}
      </GroundedSection>
      {(answer.cross_topic ?? []).length > 0 ? (
        <GroundedSection title="其他主题">
          {answer.cross_topic!.map((hit) => (
            <button
              key={hit.claim_id}
              type="button"
              className="block w-full text-left text-sm leading-6 hover:text-gold"
              onClick={() => onSelect(hit.claim_id)}
            >
              [{hit.goal_title}] {hit.label}
            </button>
          ))}
        </GroundedSection>
      ) : null}
      {(answer.prior_decisions ?? []).length > 0 ? (
        <GroundedSection title="上次决策">
          {answer.prior_decisions!.map((item) => (
            <button
              key={item.decision_id}
              type="button"
              className="block w-full text-left text-sm leading-6 hover:text-gold"
              onClick={() => onSelect(item.decision_id)}
            >
              {item.question}
              {item.outcome ? ` · ${item.outcome}` : ""}
            </button>
          ))}
        </GroundedSection>
      ) : null}
      {canCapture && onCapture ? (
        <button
          type="button"
          disabled={busy || cited.length === 0}
          onClick={() => void onCapture(messageId)}
          className="w-full border border-gold/40 bg-gold/10 px-3 py-2 text-xs text-gold disabled:opacity-50"
        >
          {cited.length === 0 ? "没有可收入的已有主张" : "收入当前章节"}
        </button>
      ) : null}
    </div>
  );
}

function UnlinkedHint({
  unlinked,
  note,
  candidates,
  busy,
  messageId,
  onSelect,
  onLink,
}: {
  unlinked: boolean;
  note?: string;
  candidates: LinkCandidate[];
  busy: boolean;
  messageId: string;
  onSelect: (id: string) => void;
  onLink: (fromId: string, toId: string, messageId: string) => Promise<void>;
}) {
  if (!unlinked && !note && candidates.length === 0) {
    return <p className="text-sm text-muted">无</p>;
  }
  return (
    <div className="space-y-2">
      {unlinked ? (
        <p className="text-sm text-muted">图上还没连上相关边。</p>
      ) : note ? (
        <p className="text-[11px] leading-4 text-muted">{note}</p>
      ) : null}
      {candidates.map((item) => (
        <div key={`${item.from_id}:${item.to_id}`} className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="max-w-full truncate text-left text-xs text-gold hover:underline"
            onClick={() => onSelect(item.to_id)}
          >
            {item.to_label}
          </button>
          <button
            type="button"
            disabled={busy}
            className="border border-gold/40 px-2 py-0.5 text-[11px] text-gold disabled:opacity-50"
            onClick={() => void onLink(item.from_id, item.to_id, messageId)}
          >
            标成相关
          </button>
        </div>
      ))}
    </div>
  );
}

function GroundedSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="text-[10px] uppercase tracking-[0.16em] text-gold">{title}</h3>
      <div className="mt-1 space-y-1">{children}</div>
    </section>
  );
}

function RefLine({
  refItem,
  onSelect,
  quoteFirst = false,
}: {
  refItem: GroundedRef;
  onSelect: (id: string) => void;
  quoteFirst?: boolean;
}) {
  const candidate = refItem.status === "candidate";
  const disputed = refItem.status === "disputed";
  const tag =
    refItem.relation === "contradicts"
      ? "对立"
      : refItem.relation === "related_to"
        ? "相邻"
        : refItem.relation === "about"
          ? "相关"
          : null;
  const layer = refItem.layer === "keep" ? "上层" : refItem.layer === "lookup" ? "细节" : null;
  return (
    <button
      type="button"
      onClick={() => onSelect(refItem.source_id && quoteFirst ? refItem.source_id : refItem.id)}
      className={`block w-full text-left text-sm leading-6 hover:text-gold ${
        candidate ? "text-muted" : disputed ? "text-clay" : ""
      }`}
    >
      {layer ? <span className="mr-1 text-[10px] text-gold">〔{layer}〕</span> : null}
      {tag ? <span className="mr-1 text-[10px] text-muted">[{tag}]</span> : null}
      {quoteFirst && refItem.quote ? `「${refItem.quote}」` : refItem.label}
      {refItem.status ? <span className="ml-1 text-[10px] text-muted">{refItem.status}</span> : null}
    </button>
  );
}

function IdChips({
  ids,
  onSelect,
  label = "证据",
}: {
  ids: string[];
  onSelect: (id: string) => void;
  label?: string;
}) {
  if (ids.length === 0) return null;
  return (
    <p className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted">
      <span>{label}</span>
      {ids.map((id) => (
        <button
          key={id}
          type="button"
          onClick={() => onSelect(id)}
          className="text-gold hover:underline"
        >
          {id}
        </button>
      ))}
    </p>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 px-3 py-3 text-sm ${active ? "bg-raised text-paper" : "text-muted"}`}
    >
      {children}
    </button>
  );
}
