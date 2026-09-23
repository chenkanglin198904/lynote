"use client";

import { emptyCopy } from "@/lib/copy";
import type { OutlineChapter, TopicOutline } from "@/lib/types";
import { PackList } from "./PackList";

export function CourseRail({
  outline,
  chapterId,
  busy = false,
  onPick,
  onSelectClaim,
  onSetLayer,
}: {
  outline: TopicOutline | null | undefined;
  chapterId: string | null;
  busy?: boolean;
  onPick: (id: string) => void;
  onSelectClaim: (id: string) => void;
  onSetLayer?: (claimId: string, layer: "keep" | "lookup" | null) => Promise<void>;
}) {
  const lessons = outlineLessons(outline);
  const overviewId = outline?.goal_id ?? null;
  const currentId = chapterId || overviewId;
  const current = lessons.find((item) => item.id === currentId) ?? null;
  const index = current ? lessons.findIndex((item) => item.id === current.id) : -1;
  const showingOverview = Boolean(overviewId && currentId === overviewId);

  if (!outline) {
    return (
      <aside className="flex min-h-0 flex-col border-r border-line bg-panel px-4 py-4">
        <p className="text-sm leading-6 text-muted">{emptyCopy.noCourse}</p>
      </aside>
    );
  }

  return (
    <aside className="flex min-h-0 flex-col border-r border-line bg-panel">
      <section className="border-b border-line px-4 py-4">
        <h2 className="text-xs uppercase tracking-[0.16em] text-muted">学习频道</h2>
        <p className="mt-2 font-serif text-lg leading-6">{outline.title || "当前主题"}</p>
        <p className="mt-2 text-xs leading-5 text-muted">{outline.intro}</p>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            className="flex-1 border border-gold/40 bg-gold/10 px-2 py-1.5 text-xs text-gold"
            onClick={() => overviewId && onPick(overviewId)}
          >
            总目录
          </button>
          <button
            type="button"
            disabled={lessons.length === 0}
            className="flex-1 border border-line px-2 py-1.5 text-xs text-muted hover:border-gold hover:text-gold disabled:opacity-40"
            onClick={() => lessons[0] && onPick(lessons[0].id)}
          >
            从头学
          </button>
        </div>
      </section>
      <section className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {showingOverview ? (
          <ol className="space-y-2">
            {lessons.length === 0 ? (
              <li className="text-sm leading-6 text-muted">图上还没有章节。先在待挂里点已有概念或原文中的新章名，或点中间导图里的主张逐条看。</li>
            ) : (
              lessons.map((item, order) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="w-full border border-line px-3 py-2 text-left hover:border-gold"
                    onClick={() => onPick(item.id)}
                  >
                    <p className="text-[11px] text-gold">
                      {item.kind === "claim" ? `节 ${order + 1}` : `第 ${order + 1} 章`}
                    </p>
                    <p className="mt-1 text-sm leading-5">{item.title}</p>
                    <p className="mt-1 text-[11px] leading-4 text-gold">
                      该内化 {(item.pack_keep ?? []).length} · 可外置 {(item.pack_lookup ?? []).length}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-muted">{item.summary}</p>
                  </button>
                </li>
              ))
            )}
          </ol>
        ) : current ? (
            <ChapterBody
            chapter={current}
            index={index}
            total={lessons.length}
            busy={busy}
            onSelectClaim={onSelectClaim}
            onSetLayer={onSetLayer}
            onPrev={() => index > 0 && onPick(lessons[index - 1].id)}
            onNext={() => index >= 0 && index < lessons.length - 1 && onPick(lessons[index + 1].id)}
          />
        ) : (
          <p className="text-sm leading-6 text-muted">点总目录里的一章，中间导图会收起其它兄弟节点。</p>
        )}
      </section>
    </aside>
  );
}

export function outlineLessons(outline: TopicOutline | null | undefined): OutlineChapter[] {
  if (!outline) return [];
  return [...outline.chapters, ...outline.loose_claims];
}

function ChapterBody({
  chapter,
  index,
  total,
  busy = false,
  onSelectClaim,
  onSetLayer,
  onPrev,
  onNext,
}: {
  chapter: OutlineChapter;
  index: number;
  total: number;
  busy?: boolean;
  onSelectClaim: (id: string) => void;
  onSetLayer?: (claimId: string, layer: "keep" | "lookup" | null) => Promise<void>;
  onPrev: () => void;
  onNext: () => void;
}) {
  const keep = chapter.pack_keep ?? [];
  const lookup = chapter.pack_lookup ?? [];
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-gold">
        {index + 1} / {total} · {chapter.kind === "claim" ? "节" : "章"}
      </p>
      <h3 className="font-serif text-xl leading-7">{chapter.title}</h3>
      <p className="text-sm leading-6 text-paper/90">{chapter.summary}</p>
      {chapter.claim_ids.length > 0 ? (
        <PackList keep={keep} lookup={lookup} busy={busy} onSelect={onSelectClaim} onSetLayer={onSetLayer} />
      ) : (
        <p className="text-xs leading-5 text-muted">这一章还没有挂主张。右侧问答若引用了已有主张，可点「收入当前章节」。</p>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          disabled={index <= 0}
          className="flex-1 border border-line px-2 py-1.5 text-xs text-muted disabled:opacity-40"
          onClick={onPrev}
        >
          上一章
        </button>
        <button
          type="button"
          disabled={index < 0 || index >= total - 1}
          className="flex-1 border border-gold/40 px-2 py-1.5 text-xs text-gold disabled:opacity-40"
          onClick={onNext}
        >
          下一章
        </button>
      </div>
    </div>
  );
}
