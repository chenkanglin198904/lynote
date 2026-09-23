"use client";

import type { TopicLearn } from "@/lib/types";
import { emptyCopy } from "@/lib/copy";

const STATUS_LABEL = {
  mastered: "掌握",
  weak: "薄弱",
  missing: "缺失",
  ready: "可学",
} as const;

export function LearnPanel({
  learn,
  busy,
  hasGoal = true,
  hasMisconceptions = false,
  onSelect,
  onReview,
}: {
  learn: TopicLearn | null | undefined;
  busy: boolean;
  hasGoal?: boolean;
  hasMisconceptions?: boolean;
  onSelect: (id: string) => void;
  onReview: (claimId?: string) => Promise<void>;
}) {
  if (!hasGoal || !learn) {
    return <p className="text-sm leading-6 text-muted">{emptyCopy.noGoal}</p>;
  }

  const missing = [...learn.concepts, ...learn.claims].filter((item) => item.status === "missing").slice(0, 4);
  const weak = learn.claims.filter((item) => item.status === "weak").slice(0, 3);
  const noGaps = learn.gaps.length === 0 && missing.length === 0;

  return (
    <div className="space-y-3">
      <div className="flex gap-3 text-sm">
        <Stat label="深度" value={learn.depth} />
        <Stat label="广度" value={learn.breadth} />
      </div>
      <p className="text-xs leading-5 text-muted">{learn.trend}</p>
      <p className="text-[11px] text-muted">
        {STATUS_LABEL.mastered} {learn.mastered} · {STATUS_LABEL.weak} {learn.weak} · {STATUS_LABEL.missing}{" "}
        {learn.missing}
      </p>
      {learn.contrasts[0] ? (
        <button
          type="button"
          className="grid w-full grid-cols-2 gap-1 border border-line bg-raised p-2 text-left"
          onClick={() => onSelect(learn.contrasts[0].left_id)}
        >
          <span className="text-[11px] leading-4 text-gold">{learn.contrasts[0].left_label}</span>
          <span className="text-[11px] leading-4 text-clay">{learn.contrasts[0].right_label}</span>
        </button>
      ) : (
        <p className="text-xs leading-5 text-muted">
          还没有对立主张。补一篇冲突材料才能加深，而不是再堆同观点摘要。
        </p>
      )}
      {learn.reviews.length > 0 ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => void onReview(learn.reviews[0]?.claim_id)}
          className="w-full border border-gold/40 bg-gold/10 px-3 py-2 text-sm text-gold disabled:opacity-50"
        >
          巩固到期主张
        </button>
      ) : (
        <p className="text-xs leading-5 text-muted">
          没有到期的巩固题。先在「学习」里答几道追问，薄弱点会按 1/3/7 天再出现。
        </p>
      )}
      {weak.length > 0 ? (
        <ChipList
          title="薄弱"
          items={weak.map((item) => ({ id: item.id, label: item.label }))}
          onSelect={onSelect}
          tone="clay"
        />
      ) : null}
      {missing.length > 0 ? (
        <ChipList
          title="缺失"
          items={missing.map((item) => ({ id: item.id, label: item.reason }))}
          onSelect={onSelect}
          tone="muted"
        />
      ) : null}
      {learn.gaps[0] ? (
        <p className="text-[11px] leading-5 text-gold">{learn.gaps[0].advice}</p>
      ) : noGaps ? (
        <p className="text-xs leading-5 text-muted">{emptyCopy.noGaps}</p>
      ) : null}
      {hasMisconceptions ? null : <p className="text-xs leading-5 text-muted">{emptyCopy.noMisconceptions}</p>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className="font-serif text-lg">{Math.round(value * 100)}%</p>
    </div>
  );
}

function ChipList({
  title,
  items,
  onSelect,
  tone,
}: {
  title: string;
  items: Array<{ id: string; label: string }>;
  onSelect: (id: string) => void;
  tone: "clay" | "muted";
}) {
  return (
    <div>
      <h3 className="text-[10px] uppercase tracking-[0.14em] text-muted">{title}</h3>
      <div className="mt-1 flex flex-wrap gap-1">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className={`max-w-full truncate border border-line px-1.5 py-0.5 text-[11px] hover:border-gold ${
              tone === "clay" ? "text-clay" : "text-muted"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
