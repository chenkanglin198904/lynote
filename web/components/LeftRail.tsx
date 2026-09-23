"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { HangProposal, InboxItem, Play, PlayContext, PlayId, Profile, SourceKind, Workbench } from "@/lib/types";
import { emptyCopy } from "@/lib/copy";
import { LearnPanel } from "./LearnPanel";
import { PackList } from "./PackList";

const GATE_LABEL: Record<string, string> = {
  goal_alignment: "目标",
  quality: "质量",
  novelty: "新颖",
  actionability: "可行动",
  maintenance_cost: "维护",
};

const KINDS: { id: SourceKind; label: string }[] = [
  { id: "note", label: "笔记" },
  { id: "url", label: "网页" },
  { id: "markdown", label: "Markdown" },
  { id: "pdf", label: "PDF" },
  { id: "audio", label: "音频" },
  { id: "video", label: "视频" },
];

export function LeftRail({
  data,
  busy,
  onCapture,
  onUpload,
  onCreateGoal,
  onActivateGoal,
  onAccept,
  onReject,
  onSelectNode,
  onStartReview,
  onScratch,
  onConfirmHang,
  onSaveProfile,
  onWeeklyReport,
  onOpenBrief,
  onRunPlay,
  onSetLayer,
}: {
  data: Workbench | null;
  busy: boolean;
  onCapture: (payload: { kind: SourceKind; title: string; text: string; uri?: string }) => Promise<void>;
  onUpload: (file: File, title: string, onProgress?: (percent: number) => void) => Promise<void>;
  onCreateGoal: (title: string, question: string) => Promise<void>;
  onActivateGoal: (id: string) => Promise<void>;
  onAccept: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
  onSelectNode: (id: string) => void;
  onStartReview: (claimId?: string) => Promise<void>;
  onScratch: (text: string) => Promise<void>;
  onConfirmHang: (claimIds: string[], targetId: string, newName?: string) => Promise<void>;
  onSaveProfile: (profile: Profile) => Promise<void>;
  onWeeklyReport: () => Promise<void>;
  onOpenBrief: () => void;
  onRunPlay: (payload: {
    play_id: PlayId;
    kind?: SourceKind;
    title?: string;
    text?: string;
    uri?: string;
    compose_brief?: boolean;
  }) => Promise<void>;
  onSetLayer?: (claimId: string, layer: "keep" | "lookup" | null) => Promise<void>;
}) {
  const [kind, setKind] = useState<SourceKind>("url");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [uri, setUri] = useState("");
  const [goalTitle, setGoalTitle] = useState("");
  const [goalQuestion, setGoalQuestion] = useState("");
  const [uploadPercent, setUploadPercent] = useState<number | null>(null);
  const [scratch, setScratch] = useState("");
  const [playId, setPlayId] = useState<PlayId | null>(null);
  const [playTitle, setPlayTitle] = useState("");
  const [playText, setPlayText] = useState("");
  const [playUri, setPlayUri] = useState("");
  const [playKind, setPlayKind] = useState<SourceKind>("url");
  const [playCompose, setPlayCompose] = useState(false);
  const inbox = data?.inbox ?? [];
  const pending = inbox.filter((item) => item.status === "pending");
  const processed = inbox.filter((item) => item.status !== "pending");
  const allowed = new Set((data?.graph.nodes ?? []).map((node) => node.id));
  const hangs = (data?.hangs ?? []).filter((item) => allowed.has(item.source_id));
  const board = data?.today;
  const nextCount =
    hangs.length + pending.length + (board?.reviews.length ?? 0) + (board?.decisions.length ?? 0);

  function resetCapture() {
    setTitle("");
    setText("");
    setUri("");
  }

  return (
    <aside className="flex min-h-0 flex-col border-r border-line bg-panel">
      <TodayHeader
        busy={busy}
        nextCount={nextCount}
        onWeeklyReport={onWeeklyReport}
      />
      <TopicStrip
        data={data}
        busy={busy}
        goalTitle={goalTitle}
        goalQuestion={goalQuestion}
        onGoalTitle={setGoalTitle}
        onGoalQuestion={setGoalQuestion}
        onCreateGoal={onCreateGoal}
        onActivateGoal={onActivateGoal}
      />
      <ScratchBox
        busy={busy}
        scratch={scratch}
        onScratchChange={setScratch}
        onScratch={onScratch}
      />

      <div className="min-h-0 flex-1 overflow-y-auto">
        <PlayStrip
          plays={data?.plays ?? []}
          context={data?.play_context ?? null}
          busy={busy}
          playId={playId}
          playKind={playKind}
          playTitle={playTitle}
          playText={playText}
          playUri={playUri}
          playCompose={playCompose}
          onPlayId={(id) => {
            setPlayId(id);
            if (id === "read_article") setPlayKind("url");
            if (id === "after_meeting") setPlayKind("note");
          }}
          onPlayKind={setPlayKind}
          onPlayTitle={setPlayTitle}
          onPlayText={setPlayText}
          onPlayUri={setPlayUri}
          onPlayCompose={setPlayCompose}
          onRunPlay={onRunPlay}
          onReset={() => {
            setPlayTitle("");
            setPlayText("");
            setPlayUri("");
            setPlayCompose(false);
          }}
        />
        <NextSteps
          data={data}
          busy={busy}
          hangs={hangs}
          pending={pending}
          nextCount={nextCount}
          onAccept={onAccept}
          onReject={onReject}
          onConfirmHang={onConfirmHang}
          onCapture={onCapture}
          onSelectNode={onSelectNode}
          onStartReview={onStartReview}
          onOpenBrief={onOpenBrief}
          onSetLayer={onSetLayer}
        />
        <Fold title="送进来" hint="网页、文件、音视频过闸">
          <CaptureForm
            busy={busy}
            kind={kind}
            title={title}
            text={text}
            uri={uri}
            uploadPercent={uploadPercent}
            onKind={setKind}
            onTitle={setTitle}
            onText={setText}
            onUri={setUri}
            onCapture={onCapture}
            onUpload={onUpload}
            onUploadPercent={setUploadPercent}
            resetCapture={resetCapture}
          />
        </Fold>
        {processed.length > 0 ? (
          <Fold title="已处理" count={processed.length}>
            <div className="space-y-3">
              {processed.map((item) => (
                <InboxCard key={item.id} item={item} busy={busy} onAccept={onAccept} onReject={onReject} />
              ))}
            </div>
          </Fold>
        ) : null}
        <Fold title="掌握" hint={data?.learn ? `${Math.round((data.learn.depth ?? 0) * 100)}% 深 · ${Math.round((data.learn.breadth ?? 0) * 100)}% 广` : undefined}>
          <LearnPanel
            learn={data?.learn}
            busy={busy}
            hasGoal={Boolean(data?.goals.length)}
            hasMisconceptions={(data?.graph.nodes ?? []).some((node) => node.kind === "misconception")}
            onSelect={onSelectNode}
            onReview={onStartReview}
          />
        </Fold>
        <Fold title="偏好" hint="只影响排序，不能当答案">
          <ProfileFields profile={data?.profile} busy={busy} onSave={onSaveProfile} />
        </Fold>
      </div>
    </aside>
  );
}

function TodayHeader({
  busy,
  nextCount,
  onWeeklyReport,
}: {
  busy: boolean;
  nextCount: number;
  onWeeklyReport: () => Promise<void>;
}) {
  return (
    <section className="border-b border-line px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-xs uppercase tracking-[0.16em] text-muted">今日桌面</h2>
          <p className="mt-1 text-[11px] text-muted">
            {nextCount > 0 ? `${nextCount} 件下一步` : "没有待办，记下或送进来"}
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          className="text-[11px] text-gold hover:underline disabled:opacity-50"
          onClick={() => void onWeeklyReport()}
        >
          导出本周
        </button>
      </div>
    </section>
  );
}

function TopicStrip({
  data,
  busy,
  goalTitle,
  goalQuestion,
  onGoalTitle,
  onGoalQuestion,
  onCreateGoal,
  onActivateGoal,
}: {
  data: Workbench | null;
  busy: boolean;
  goalTitle: string;
  goalQuestion: string;
  onGoalTitle: (value: string) => void;
  onGoalQuestion: (value: string) => void;
  onCreateGoal: (title: string, question: string) => Promise<void>;
  onActivateGoal: (id: string) => Promise<void>;
}) {
  const goals = data?.goals ?? [];
  return (
    <section className="border-b border-line px-4 py-3">
      <h3 className="text-[10px] uppercase tracking-[0.14em] text-muted">当前主题</h3>
      {goals.length === 0 ? (
        <p className="mt-2 text-xs leading-5 text-muted">{emptyCopy.noGoal}</p>
      ) : (
        <div className="mt-2 space-y-1">
          {goals.map((goal) => {
            const active = goal.status === "active";
            return (
              <button
                key={goal.id}
                type="button"
                disabled={busy || active}
                onClick={() => void onActivateGoal(goal.id)}
                className={`w-full truncate border px-2 py-1.5 text-left text-sm ${
                  active ? "border-gold/50 bg-gold/10 text-gold" : "border-line text-muted hover:border-gold/40 hover:text-paper"
                }`}
                title={goal.question}
              >
                {goal.title}
                {active ? <span className="ml-2 text-[10px] text-muted">当前</span> : null}
              </button>
            );
          })}
        </div>
      )}
      <details className="mt-2">
        <summary className="cursor-pointer list-none text-[11px] text-gold hover:underline [&::-webkit-details-marker]:hidden">
          新建主题
        </summary>
        <form
          className="mt-2 space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!goalTitle.trim()) return;
            void onCreateGoal(goalTitle.trim(), goalQuestion.trim()).then(() => {
              onGoalTitle("");
              onGoalQuestion("");
            });
          }}
        >
          <input
            className="w-full rounded-sm border border-line bg-ink px-3 py-2 text-sm outline-none placeholder:text-muted/70 focus:border-gold"
            placeholder="新主题，例如：大模型学习"
            value={goalTitle}
            onChange={(event) => onGoalTitle(event.target.value)}
          />
          <input
            className="w-full rounded-sm border border-line bg-ink px-3 py-2 text-sm outline-none placeholder:text-muted/70 focus:border-gold"
            placeholder="想搞清什么（可空，默认用主题名）"
            value={goalQuestion}
            onChange={(event) => onGoalQuestion(event.target.value)}
          />
          <button
            type="submit"
            disabled={busy || !goalTitle.trim()}
            className="w-full border border-gold/50 bg-gold/10 px-3 py-2 text-xs text-gold disabled:opacity-50"
          >
            新建并切换到这个主题
          </button>
        </form>
      </details>
    </section>
  );
}

function ScratchBox({
  busy,
  scratch,
  onScratchChange,
  onScratch,
}: {
  busy: boolean;
  scratch: string;
  onScratchChange: (value: string) => void;
  onScratch: (text: string) => Promise<void>;
}) {
  return (
    <section className="border-b border-line px-4 py-3">
      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!scratch.trim()) return;
          void onScratch(scratch.trim()).then(() => onScratchChange(""));
        }}
      >
        <textarea
          className="h-16 w-full resize-none rounded-sm border border-line bg-ink px-3 py-2 text-sm outline-none placeholder:text-muted/70 focus:border-gold"
          placeholder="随手记：刚才悟到的、会上记下的……"
          value={scratch}
          onChange={(event) => onScratchChange(event.target.value)}
        />
        <button
          type="submit"
          disabled={busy || scratch.trim().length < 8}
          className="w-full border border-gold/50 bg-gold/10 px-3 py-1.5 text-xs text-gold disabled:opacity-50"
        >
          记下
        </button>
      </form>
    </section>
  );
}

function PlayStrip({
  plays,
  context,
  busy,
  playId,
  playKind,
  playTitle,
  playText,
  playUri,
  playCompose,
  onPlayId,
  onPlayKind,
  onPlayTitle,
  onPlayText,
  onPlayUri,
  onPlayCompose,
  onRunPlay,
  onReset,
}: {
  plays: Play[];
  context: PlayContext | null;
  busy: boolean;
  playId: PlayId | null;
  playKind: SourceKind;
  playTitle: string;
  playText: string;
  playUri: string;
  playCompose: boolean;
  onPlayId: (id: PlayId | null) => void;
  onPlayKind: (kind: SourceKind) => void;
  onPlayTitle: (value: string) => void;
  onPlayText: (value: string) => void;
  onPlayUri: (value: string) => void;
  onPlayCompose: (value: boolean) => void;
  onRunPlay: (payload: {
    play_id: PlayId;
    kind?: SourceKind;
    title?: string;
    text?: string;
    uri?: string;
    compose_brief?: boolean;
  }) => Promise<void>;
  onReset: () => void;
}) {
  const current = plays.find((item) => item.id === playId) ?? null;
  const canSubmit =
    playId === "read_article"
      ? Boolean(playUri.trim() || playText.trim())
      : playText.trim().length >= 8;
  return (
    <section className="border-b border-line px-4 py-3">
      <h3 className="text-[10px] uppercase tracking-[0.14em] text-muted">剧本</h3>
      <p className="mt-1 text-[11px] leading-4 text-muted">走现有闭环，不是插件。不自动接受、不自动建章、不替你拍板。</p>
      {context ? <p className="mt-1 text-[11px] leading-4 text-gold">{context.hint}</p> : null}
      <div className="mt-2 flex flex-wrap gap-1">
        {plays.map((item) => (
          <button
            key={item.id}
            type="button"
            disabled={busy}
            className={`px-2 py-1 text-[11px] ${playId === item.id ? "bg-raised text-gold" : "text-muted hover:text-gold"}`}
            onClick={() => onPlayId(playId === item.id ? null : item.id)}
          >
            {item.title}
          </button>
        ))}
      </div>
      {current ? (
        <form
          className="mt-2 space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!canSubmit) return;
            void onRunPlay({
              play_id: current.id,
              kind: playKind,
              title: playTitle,
              text: playText,
              uri: playUri || undefined,
              compose_brief: current.id === "after_meeting" && playCompose,
            }).then(() => onReset());
          }}
        >
          <p className="text-[11px] leading-4 text-muted">{current.steps.join(" → ")}</p>
          {current.id === "read_article" ? (
            <>
              <div className="flex flex-wrap gap-1">
                {(["url", "markdown"] as SourceKind[]).map((kind) => (
                  <button
                    key={kind}
                    type="button"
                    className={`px-2 py-0.5 text-[11px] ${playKind === kind ? "bg-raised text-gold" : "text-muted"}`}
                    onClick={() => onPlayKind(kind)}
                  >
                    {kind === "url" ? "网页" : "Markdown"}
                  </button>
                ))}
              </div>
              <input
                className="w-full border border-line bg-ink px-2 py-1 text-xs outline-none focus:border-gold"
                placeholder="标题（可空）"
                value={playTitle}
                onChange={(event) => onPlayTitle(event.target.value)}
              />
              {playKind === "url" ? (
                <input
                  className="w-full border border-line bg-ink px-2 py-1 text-xs outline-none focus:border-gold"
                  placeholder="网址 https://"
                  value={playUri}
                  onChange={(event) => onPlayUri(event.target.value)}
                />
              ) : null}
              <textarea
                className="h-16 w-full resize-none border border-line bg-ink px-2 py-1 text-xs outline-none focus:border-gold"
                placeholder={playKind === "url" ? "可选：粘贴正文。PDF 请展开下面「送进来」上传。" : "粘贴 Markdown 正文"}
                value={playText}
                onChange={(event) => onPlayText(event.target.value)}
              />
            </>
          ) : (
            <>
              <textarea
                className="h-16 w-full resize-none border border-line bg-ink px-2 py-1 text-xs outline-none focus:border-gold"
                placeholder="会上要留下来的判断，至少一句完整话。音视频请展开「送进来」。"
                value={playText}
                onChange={(event) => onPlayText(event.target.value)}
              />
              <label className="flex items-center gap-2 text-[11px] text-muted">
                <input
                  type="checkbox"
                  checked={playCompose}
                  onChange={(event) => onPlayCompose(event.target.checked)}
                />
                记下后打开简报（只用已有主张）
              </label>
            </>
          )}
          <button
            type="submit"
            disabled={busy || !canSubmit}
            className="w-full border border-gold/50 bg-gold/10 px-3 py-1.5 text-xs text-gold disabled:opacity-50"
          >
            {current.id === "read_article" ? "送去过闸" : "落地"}
          </button>
        </form>
      ) : null}
    </section>
  );
}

const MAIN_LIMIT = 3;

function NextSteps({
  data,
  busy,
  hangs,
  pending,
  nextCount,
  onAccept,
  onReject,
  onConfirmHang,
  onCapture,
  onSelectNode,
  onStartReview,
  onOpenBrief,
  onSetLayer,
}: {
  data: Workbench | null;
  busy: boolean;
  hangs: HangProposal[];
  pending: InboxItem[];
  nextCount: number;
  onAccept: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
  onConfirmHang: (claimIds: string[], targetId: string, newName?: string) => Promise<void>;
  onCapture: (payload: { kind: SourceKind; title: string; text: string; uri?: string }) => Promise<void>;
  onSelectNode: (id: string) => void;
  onStartReview: (claimId?: string) => Promise<void>;
  onOpenBrief: () => void;
  onSetLayer?: (claimId: string, layer: "keep" | "lookup" | null) => Promise<void>;
}) {
  const board = data?.today;
  const notes = board?.notes ?? [];
  const cards: ReactNode[] = [
    ...hangs.map((item) => (
      <HangCard
        key={item.source_id}
        item={item}
        busy={busy}
        onConfirmHang={onConfirmHang}
        onCapture={onCapture}
        onSelect={onSelectNode}
        onSetLayer={onSetLayer}
      />
    )),
    ...pending.map((item) => (
      <InboxCard key={item.id} item={item} busy={busy} onAccept={onAccept} onReject={onReject} />
    )),
    ...(board?.reviews ?? []).map((item) => (
      <button
        key={`r-${item.id}`}
        type="button"
        disabled={busy}
        className="block w-full border border-gold/30 bg-gold/5 px-3 py-2 text-left disabled:opacity-50"
        onClick={() => void onStartReview(item.id)}
      >
        <p className="text-[10px] uppercase tracking-[0.14em] text-gold">巩固</p>
        <p className="mt-1 text-sm leading-5">{item.title}</p>
        {item.detail ? <p className="mt-1 text-[11px] text-muted">{item.detail}</p> : null}
      </button>
    )),
    ...(board?.decisions ?? []).map((item) => (
      <button
        key={`d-${item.id}`}
        type="button"
        className="block w-full border border-line bg-raised px-3 py-2 text-left hover:border-gold/40"
        onClick={() => {
          onSelectNode(item.id);
          onOpenBrief();
        }}
      >
        <p className="text-[10px] uppercase tracking-[0.14em] text-muted">{item.detail}</p>
        <p className="mt-1 text-sm leading-5">{item.title}</p>
      </button>
    )),
  ];
  const main = cards.slice(0, MAIN_LIMIT);
  const rest = cards.slice(MAIN_LIMIT);
  const empty = nextCount === 0 && notes.length === 0;
  return (
    <section className="border-b border-line px-4 py-3">
      <h3 className="text-[10px] uppercase tracking-[0.14em] text-muted">下一步</h3>
      {empty ? (
        <p className="mt-2 text-xs leading-5 text-muted">{emptyCopy.noToday}</p>
      ) : (
        <div className="mt-2 space-y-3">
          {main}
          {rest.length > 0 ? (
            <details>
              <summary className="cursor-pointer list-none text-[11px] text-gold hover:underline [&::-webkit-details-marker]:hidden">
                还有 {rest.length} 件
              </summary>
              <div className="mt-2 space-y-3">{rest}</div>
            </details>
          ) : null}
          {notes.map((item) => (
            <button
              key={`n-${item.id}`}
              type="button"
              className="block w-full text-left text-xs text-gold hover:underline"
              onClick={() => onSelectNode(item.id)}
            >
              今日记下 · {item.title}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function Fold({
  title,
  hint,
  count,
  children,
}: {
  title: string;
  hint?: string;
  count?: number;
  children: ReactNode;
}) {
  return (
    <details className="border-b border-line">
      <summary className="flex cursor-pointer list-none items-baseline justify-between gap-2 px-4 py-3 text-xs uppercase tracking-[0.16em] text-muted hover:text-paper [&::-webkit-details-marker]:hidden">
        <span>
          {title}
          {count != null ? ` · ${count}` : ""}
        </span>
        {hint ? <span className="normal-case tracking-normal text-[10px] font-normal text-muted/80">{hint}</span> : null}
      </summary>
      <div className="px-4 pb-4">{children}</div>
    </details>
  );
}

function CaptureForm({
  busy,
  kind,
  title,
  text,
  uri,
  uploadPercent,
  onKind,
  onTitle,
  onText,
  onUri,
  onCapture,
  onUpload,
  onUploadPercent,
  resetCapture,
}: {
  busy: boolean;
  kind: SourceKind;
  title: string;
  text: string;
  uri: string;
  uploadPercent: number | null;
  onKind: (kind: SourceKind) => void;
  onTitle: (value: string) => void;
  onText: (value: string) => void;
  onUri: (value: string) => void;
  onCapture: (payload: { kind: SourceKind; title: string; text: string; uri?: string }) => Promise<void>;
  onUpload: (file: File, title: string, onProgress?: (percent: number) => void) => Promise<void>;
  onUploadPercent: (value: number | null) => void;
  resetCapture: () => void;
}) {
  return (
    <>
      <p className="text-xs leading-5 text-muted">
        网页、Markdown、PDF、音频或视频过闸后进人审。音频/视频转写成可定位正文，不会发明没听到的句子。一句话请用上面的随手记。
      </p>
      <div className="mt-3 flex flex-wrap gap-1">
        {KINDS.filter((item) => item.id !== "note").map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onKind(item.id)}
            className={`px-2 py-1 text-[11px] ${kind === item.id ? "bg-raised text-gold" : "text-muted"}`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <form
        className="mt-3 space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (kind === "url") {
            if (!uri.trim()) return;
            void onCapture({ kind, title: title.trim(), text: text.trim(), uri: uri.trim() }).then(resetCapture);
            return;
          }
          if (kind === "pdf" || kind === "audio" || kind === "video") return;
          if (!title.trim() || !text.trim()) return;
          void onCapture({ kind, title: title.trim(), text: text.trim() }).then(resetCapture);
        }}
      >
        {kind === "url" ? (
          <input
            className="w-full rounded-sm border border-line bg-ink px-3 py-2 text-sm outline-none placeholder:text-muted/70 focus:border-gold"
            placeholder="https://..."
            value={uri}
            onChange={(event) => onUri(event.target.value)}
          />
        ) : null}
        <input
          className="w-full rounded-sm border border-line bg-ink px-3 py-2 text-sm outline-none placeholder:text-muted/70 focus:border-gold"
          placeholder={kind === "url" ? "标题（可空，用网页标题）" : "来源标题（音频/视频可空，用文件名）"}
          value={title}
          onChange={(event) => onTitle(event.target.value)}
        />
        {kind !== "pdf" && kind !== "audio" && kind !== "video" ? (
          <textarea
            className="h-24 w-full resize-none rounded-sm border border-line bg-ink px-3 py-2 text-sm outline-none placeholder:text-muted/70 focus:border-gold"
            placeholder={
              kind === "url"
                ? "可选：已有正文就不必抓取"
                : kind === "markdown"
                  ? "粘贴 Markdown，或下面上传 .md"
                  : "粘贴笔记、摘要或网页正文"
            }
            value={text}
            onChange={(event) => onText(event.target.value)}
          />
        ) : kind === "pdf" ? (
          <p className="text-xs text-muted">PDF 请上传文件。扫描件在配置了模型 Key 后会视觉抽字；仍然抽不出字会被拒绝。</p>
        ) : (
          <p className="text-xs text-muted">
            {kind === "audio"
              ? "上传音频。会转写成带时间信息的正文，未听到的句子不会发明。"
              : "上传视频。抽取旁白；若本机有 ffmpeg 还会抽几帧画面文字。抽不出则拒绝。"}
          </p>
        )}
        {kind === "markdown" || kind === "pdf" || kind === "audio" || kind === "video" ? (
          <label className="block cursor-pointer border border-dashed border-line px-3 py-2 text-center text-xs text-muted">
            {uploadPercent == null
              ? `上传 ${kind === "pdf" ? ".pdf" : kind === "audio" ? "音频" : kind === "video" ? "视频" : ".md / .txt"}`
              : `上传中 ${uploadPercent}%`}
            <input
              type="file"
              className="hidden"
              disabled={busy}
              accept={
                kind === "pdf"
                  ? "application/pdf,.pdf"
                  : kind === "audio"
                    ? "audio/*,.mp3,.wav,.m4a,.ogg,.webm,.aac"
                    : kind === "video"
                      ? "video/*,.mp4,.mov,.mkv,.webm"
                      : ".md,.markdown,.txt"
              }
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (!file) return;
                const maxBytes = 32 * 1024 * 1024;
                if (file.size > maxBytes) {
                  window.alert("文件超过 32MB，请先压缩或拆分后再上传");
                  return;
                }
                onUploadPercent(0);
                void onUpload(file, title.trim(), onUploadPercent)
                  .then(resetCapture)
                  .finally(() => onUploadPercent(null));
              }}
            />
          </label>
        ) : null}
        {uploadPercent != null ? (
          <div className="h-1.5 overflow-hidden border border-line bg-ink">
            <div className="h-full bg-gold" style={{ width: `${uploadPercent}%` }} />
          </div>
        ) : null}
        {kind !== "pdf" && kind !== "audio" && kind !== "video" ? (
          <button
            type="submit"
            disabled={busy}
            className="w-full border border-gold/50 bg-gold/10 px-3 py-2 text-sm text-gold disabled:opacity-50"
          >
            送去过闸
          </button>
        ) : null}
      </form>
    </>
  );
}

function InboxCard({
  item,
  busy,
  onAccept,
  onReject,
}: {
  item: InboxItem;
  busy: boolean;
  onAccept: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
}) {
  const pending = item.status === "pending";
  return (
    <article className="border border-line bg-raised p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-5">{item.title}</p>
        <VerdictMark verdict={item.verdict} status={item.status} />
      </div>
      <p className="mt-2 text-xs leading-5 text-muted">{item.snippet}</p>
      {item.gap_note && (item.gap_score ?? 0) > 0 ? (
        <p className="mt-2 text-[11px] leading-4 text-gold">缺口 {item.gap_note}</p>
      ) : null}
      <ul className="mt-3 space-y-1">
        {item.checks.map((check) => (
          <li key={check.gate} className="flex gap-2 text-[11px] leading-4">
            <span className={check.passed ? "text-moss" : "text-clay"}>{check.passed ? "过" : "拒"}</span>
            <span className="text-muted">
              {GATE_LABEL[check.gate]} · {check.note}
            </span>
          </li>
        ))}
      </ul>
      {pending ? (
        <div className="mt-3 flex gap-2">
          <button
            disabled={busy}
            onClick={() => void onReject(item.id)}
            className="flex-1 border border-line px-2 py-1 text-xs text-muted"
          >
            拒绝
          </button>
          <button
            disabled={busy}
            onClick={() => void onAccept(item.id)}
            className="flex-1 border border-paper/30 px-2 py-1 text-xs"
          >
            接受并抽取
          </button>
        </div>
      ) : (
        <p className="mt-3 text-[11px] text-muted">
          已{item.status === "accepted" ? "接受" : "拒绝"}，图谱不会被拒绝项写入。
        </p>
      )}
    </article>
  );
}

function VerdictMark({
  verdict,
  status,
}: {
  verdict: InboxItem["verdict"];
  status: InboxItem["status"];
}) {
  const label = status !== "pending" ? status : verdict;
  const tone =
    label === "reject" || label === "rejected"
      ? "text-clay"
      : label === "accept" || label === "accepted"
        ? "text-moss"
        : "text-gold";
  const text =
    label === "reject"
      ? "建议拒"
      : label === "accept"
        ? "建议收"
        : label === "review"
          ? "待审"
          : label === "accepted"
            ? "已收"
            : "已拒";
  return <span className={`shrink-0 text-[11px] ${tone}`}>{text}</span>;
}

function HangCard({
  item,
  busy,
  onConfirmHang,
  onCapture,
  onSelect,
  onSetLayer,
}: {
  item: HangProposal;
  busy: boolean;
  onConfirmHang: (claimIds: string[], targetId: string, newName?: string) => Promise<void>;
  onCapture: (payload: { kind: SourceKind; title: string; text: string; uri?: string }) => Promise<void>;
  onSelect: (id: string) => void;
  onSetLayer?: (claimId: string, layer: "keep" | "lookup" | null) => Promise<void>;
}) {
  const keep = item.pack_keep ?? [];
  const lookup = item.pack_lookup ?? [];
  return (
    <div className="border border-gold/40 bg-gold/5 p-3">
      <p className="text-[10px] uppercase tracking-[0.14em] text-gold">待挂</p>
      <p className="mt-1 text-xs leading-5 text-muted">
        {item.claim_ids.length} 条主张还没挂概念。点已有概念或当前主题；原文里出现的新章名点了才建概念。
      </p>
      {keep.length + lookup.length > 0 ? (
        <div className="mt-2">
          <PackList keep={keep} lookup={lookup} busy={busy} onSelect={onSelect} onSetLayer={onSetLayer} />
        </div>
      ) : null}
      <div className="mt-2 flex flex-wrap gap-1">
        {item.candidates.map((candidate) => (
          <button
            key={candidate.node_id}
            type="button"
            disabled={busy}
            className="border border-gold/40 px-2 py-1 text-[11px] text-gold disabled:opacity-50"
            onClick={() => void onConfirmHang(item.claim_ids, candidate.node_id)}
          >
            {candidate.kind === "goal" ? "主题" : "概念"} {candidate.label}
          </button>
        ))}
        {(item.proposed_names ?? []).map((name) => (
          <button
            key={`new-${name}`}
            type="button"
            disabled={busy}
            className="border border-dashed border-gold/40 px-2 py-1 text-[11px] text-gold disabled:opacity-50"
            onClick={() => void onConfirmHang(item.claim_ids, "", name)}
          >
            新章 {name}
          </button>
        ))}
      </div>
      {(item.industry_hints ?? []).length > 0 ? (
        <ul className="mt-2 space-y-1 border-t border-line pt-2">
          {item.industry_hints!.map((hint) => (
            <li key={hint.url} className="text-[11px] leading-4 text-muted">
              <a href={hint.url} target="_blank" rel="noreferrer" className="text-gold hover:underline">
                行业检索 · {hint.title}
              </a>
              {hint.matched_label ? ` → 更接近「${hint.matched_label}」` : " · 未对上已有概念"}
              <button
                type="button"
                disabled={busy}
                className="ml-2 text-gold hover:underline disabled:opacity-50"
                onClick={() => void onCapture({ kind: "url", title: hint.title, text: "", uri: hint.url })}
              >
                送去过闸
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ProfileFields({
  profile,
  busy,
  onSave,
}: {
  profile?: Profile | null;
  busy: boolean;
  onSave: (profile: Profile) => Promise<void>;
}) {
  const current = profile ?? {
    domains: [],
    role: "",
    language: "zh",
    prefer_own_notes: true,
    skip_candidates: true,
  };
  const [role, setRole] = useState(current.role);
  const [domains, setDomains] = useState(current.domains.join("、"));
  const [preferOwn, setPreferOwn] = useState(current.prefer_own_notes);
  useEffect(() => {
    setRole(current.role);
    setDomains(current.domains.join("、"));
    setPreferOwn(current.prefer_own_notes);
  }, [current.role, current.domains, current.prefer_own_notes]);
  return (
    <>
      <p className="text-xs leading-5 text-muted">只影响排序和口吻，不能当答案。未知仍然是未知。</p>
      <input
        className="mt-2 w-full border border-line bg-ink px-2 py-1 text-xs outline-none focus:border-gold"
        placeholder="角色，例如后端 / 学大模型"
        value={role}
        onChange={(event) => setRole(event.target.value)}
      />
      <input
        className="mt-2 w-full border border-line bg-ink px-2 py-1 text-xs outline-none focus:border-gold"
        placeholder="领域，顿号分隔"
        value={domains}
        onChange={(event) => setDomains(event.target.value)}
      />
      <label className="mt-2 flex items-center gap-2 text-xs text-muted">
        <input type="checkbox" checked={preferOwn} onChange={(event) => setPreferOwn(event.target.checked)} />
        召回更信亲手笔记
      </label>
      <button
        type="button"
        disabled={busy}
        className="mt-2 w-full border border-line px-2 py-1 text-xs text-muted hover:border-gold hover:text-gold disabled:opacity-50"
        onClick={() =>
          void onSave({
            ...current,
            role: role.trim(),
            domains: domains
              .split(/[、,，]/)
              .map((item) => item.trim())
              .filter(Boolean),
            prefer_own_notes: preferOwn,
          })
        }
      >
        保存偏好
      </button>
    </>
  );
}
