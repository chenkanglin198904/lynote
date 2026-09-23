"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  acceptInbox,
  activateGoal,
  captureLesson,
  commitBrief,
  composeBrief,
  confirmHang,
  createGoal,
  deprecateClaim,
  fetchWeeklyReport,
  fetchWorkbench,
  gradeProbe,
  ingestSource,
  ingestUpload,
  linkRelation,
  mergeConcepts,
  rejectInbox,
  resolveMisconception,
  reviewBrief,
  runPlay,
  saveProfile,
  scratchNote,
  sendChat,
  setClaimLayer,
  startReview,
  touchClaim,
} from "@/lib/api";
import type { Profile, Workbench as WorkbenchData } from "@/lib/types";
import { CourseRail, outlineLessons } from "./CourseRail";
import { GraphCanvas } from "./GraphCanvas";
import { LeftRail } from "./LeftRail";
import { RightPanel } from "./RightPanel";

export function Workbench() {
  const [data, setData] = useState<WorkbenchData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pinned, setPinned] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusChat, setFocusChat] = useState(0);
  const [focusBrief, setFocusBrief] = useState(0);
  const [mode, setMode] = useState<"work" | "course">("work");
  const [drillId, setDrillId] = useState<string | null>(null);
  const [chapterId, setChapterId] = useState<string | null>(null);
  const touchTimer = useRef<number | null>(null);

  const reload = useCallback(async () => {
    const next = await fetchWorkbench();
    setData(next);
  }, []);

  useEffect(() => {
    reload()
      .then(() => setError(null))
      .catch(() => {
        setError("后端未启动。先在仓库根目录运行 npm run dev，或单独启动 FastAPI :8000。");
      });
  }, [reload]);

  useEffect(() => {
    return () => {
      if (touchTimer.current) window.clearTimeout(touchTimer.current);
    };
  }, []);

  async function wrap(action: () => Promise<unknown>) {
    setBusy(true);
    let actionError: string | null = null;
    try {
      await action();
    } catch (err) {
      actionError = err instanceof Error ? err.message : "请求失败";
    }
    try {
      await reload();
      if (!actionError) setError(null);
    } catch {
      actionError = actionError || "无法刷新工作台";
    }
    if (actionError) setError(actionError);
    setBusy(false);
  }

  const selectNode = useCallback(
    (id: string) => {
      setSelectedId(id);
      const kind = data?.graph.nodes.find((node) => node.id === id)?.kind;
      if (kind !== "claim") return;
      if (touchTimer.current) window.clearTimeout(touchTimer.current);
      touchTimer.current = window.setTimeout(() => {
        void touchClaim(id)
          .then(() => fetchWorkbench())
          .then(setData)
          .catch(() => {});
      }, 400);
    },
    [data],
  );

  const activeGoal = data?.goals.find((goal) => goal.status === "active") ?? data?.goals[0];

  useEffect(() => {
    const id = activeGoal?.id ?? null;
    setDrillId(id);
    setChapterId(id);
  }, [activeGoal?.id]);

  function pickChapter(id: string) {
    setChapterId(id);
    setDrillId(id);
    selectNode(id);
  }

  function handleDrill(id: string | null) {
    setDrillId(id);
    if (!id) return;
    const outline = data?.outline;
    if (id === outline?.goal_id || outlineLessons(outline).some((item) => item.id === id)) {
      setChapterId(id);
    }
  }

  const captureChapter =
    chapterId &&
    (chapterId === activeGoal?.id || (data?.outline?.chapters.some((item) => item.id === chapterId) ?? false))
      ? chapterId
      : null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-line px-5 py-3">
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-2xl tracking-tight">LyNote</h1>
          <p className="text-sm text-muted">个人外脑知识平台</p>
          <Link href="/guide" className="text-sm text-gold hover:underline">
            用法
          </Link>
          <button
            type="button"
            className={`text-sm ${mode === "course" ? "text-gold" : "text-muted hover:text-gold"}`}
            onClick={() => setMode((current) => (current === "course" ? "work" : "course"))}
          >
            {mode === "course" ? "工作台" : "学习频道"}
          </button>
        </div>
        <p className="max-w-xl truncate text-sm text-paper/80">
          {data?.learn?.trend ?? activeGoal?.question ?? "先建一个学习主题，再往里加资料"}
        </p>
      </header>
      {error ? (
        <div className="border-b border-clay/40 bg-clay/10 px-5 py-2 text-sm text-clay">{error}</div>
      ) : null}
      <div className="grid min-h-0 flex-1 grid-cols-[320px_minmax(0,1fr)_380px] overflow-hidden">
        {mode === "course" ? (
          <CourseRail
            outline={data?.outline}
            chapterId={chapterId}
            busy={busy}
            onPick={pickChapter}
            onSelectClaim={selectNode}
            onSetLayer={(claimId, layer) => wrap(() => setClaimLayer(claimId, layer))}
          />
        ) : (
          <LeftRail
            data={data}
            busy={busy}
            onCapture={(payload) => wrap(() => ingestSource(payload))}
            onUpload={(file, title, onProgress) => wrap(() => ingestUpload(file, title, onProgress))}
            onCreateGoal={(title, question) => wrap(() => createGoal(title, question))}
            onActivateGoal={(id) => wrap(() => activateGoal(id))}
            onAccept={(id) => wrap(() => acceptInbox(id))}
            onReject={(id) => wrap(() => rejectInbox(id))}
            onSelectNode={selectNode}
            onStartReview={(claimId) =>
              wrap(async () => {
                await startReview(claimId);
                setFocusChat((count) => count + 1);
              })
            }
            onScratch={(text) => wrap(() => scratchNote(text))}
            onConfirmHang={(claimIds, targetId, newName) =>
              wrap(() => confirmHang(claimIds, targetId, newName))
            }
            onSaveProfile={(profile: Profile) => wrap(() => saveProfile(profile))}
            onWeeklyReport={() =>
              wrap(async () => {
                const report = await fetchWeeklyReport();
                const blob = new Blob([report.markdown], { type: "text/markdown;charset=utf-8" });
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = `${report.title}.md`;
                link.click();
                URL.revokeObjectURL(url);
              })
            }
            onOpenBrief={() => setFocusBrief((count) => count + 1)}
            onRunPlay={(payload) =>
              wrap(async () => {
                const result = await runPlay(payload);
                if (payload.compose_brief && result.brief) {
                  setFocusBrief((count) => count + 1);
                }
              })
            }
            onSetLayer={(claimId, layer) => wrap(() => setClaimLayer(claimId, layer))}
          />
        )}
        <GraphCanvas
          graph={data?.graph ?? { nodes: [], edges: [] }}
          pinned={pinned}
          selectedId={selectedId}
          drillId={drillId}
          onSelect={selectNode}
          onDrill={handleDrill}
          onTogglePin={(id) =>
            setPinned((current) =>
              current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
            )
          }
        />
        <RightPanel
          data={data}
          busy={busy}
          pinned={pinned}
          selectedId={selectedId}
          courseMode={mode === "course"}
          captureChapterId={captureChapter}
          onChat={(content, expandCrossTopic) =>
            wrap(() =>
              sendChat(
                content,
                chapterId && mode === "course" ? [chapterId, ...pinned.filter((id) => id !== chapterId)] : pinned,
                expandCrossTopic,
              ),
            )
          }
          onCompose={() => wrap(() => composeBrief(pinned, activeGoal?.question))}
          onCommit={(optionId, rationale) => {
            if (!data?.brief) return Promise.resolve();
            return wrap(() => commitBrief(data.brief!.id, optionId, rationale));
          }}
          onReview={(outcome) => {
            if (!data?.brief) return Promise.resolve();
            return wrap(() => reviewBrief(data.brief!.id, outcome));
          }}
          onSelectNode={selectNode}
          onGradeProbe={(probeId, payload) => wrap(() => gradeProbe(probeId, payload))}
          onResolveMisconception={(id) => wrap(() => resolveMisconception(id))}
          onLinkRelated={(fromId, toId, messageId) => wrap(() => linkRelation(fromId, toId, messageId))}
          onCaptureLesson={(messageId) => {
            if (!captureChapter) return Promise.resolve();
            return wrap(() => captureLesson(messageId, captureChapter));
          }}
          onMergeConcepts={(keepId, dropId) => wrap(() => mergeConcepts(keepId, dropId))}
          onDeprecateClaim={(claimId) => wrap(() => deprecateClaim(claimId))}
          focusChat={focusChat}
          focusBrief={focusBrief}
        />
      </div>
    </div>
  );
}
