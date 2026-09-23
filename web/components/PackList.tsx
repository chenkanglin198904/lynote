"use client";

import type { PackItem } from "@/lib/types";

export function PackList({
  keep,
  lookup,
  busy = false,
  onSelect,
  onSetLayer,
}: {
  keep: PackItem[];
  lookup: PackItem[];
  busy?: boolean;
  onSelect: (id: string) => void;
  onSetLayer?: (claimId: string, layer: "keep" | "lookup" | null) => Promise<void>;
}) {
  if (keep.length === 0 && lookup.length === 0) {
    return <p className="text-xs leading-5 text-muted">还没有可装卸的主张。</p>;
  }
  return (
    <div className="space-y-3">
      <PackGroup
        title="该内化"
        hint="原理、对立、练过的主张"
        items={keep}
        empty="这一层还空。有对立或练过的主张会出现在这里。"
        busy={busy}
        moveLabel="改为外置"
        moveTo="lookup"
        onSelect={onSelect}
        onSetLayer={onSetLayer}
      />
      <PackGroup
        title="可外置"
        hint="步骤、例子、出处，需要时再查"
        items={lookup}
        empty="没有可外置的细节。"
        busy={busy}
        moveLabel="改为内化"
        moveTo="keep"
        onSelect={onSelect}
        onSetLayer={onSetLayer}
      />
    </div>
  );
}

function PackGroup({
  title,
  hint,
  items,
  empty,
  busy,
  moveLabel,
  moveTo,
  onSelect,
  onSetLayer,
}: {
  title: string;
  hint: string;
  items: PackItem[];
  empty: string;
  busy: boolean;
  moveLabel: string;
  moveTo: "keep" | "lookup";
  onSelect: (id: string) => void;
  onSetLayer?: (claimId: string, layer: "keep" | "lookup" | null) => Promise<void>;
}) {
  return (
    <section>
      <h4 className="text-[10px] uppercase tracking-[0.14em] text-gold">{title}</h4>
      <p className="mt-0.5 text-[11px] leading-4 text-muted">{hint}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-xs leading-5 text-muted">{empty}</p>
      ) : (
        <ul className="mt-1 space-y-1">
          {items.map((item) => (
            <li key={item.id} className="border border-line px-2 py-1.5">
              <button
                type="button"
                className="block w-full text-left text-sm leading-5 hover:text-gold"
                onClick={() => onSelect(item.id)}
              >
                {item.label}
              </button>
              <p className="mt-0.5 text-[11px] leading-4 text-muted">{item.reason}</p>
              {onSetLayer ? (
                <div className="mt-1 flex gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    className="text-[11px] text-gold hover:underline disabled:opacity-50"
                    onClick={() => void onSetLayer(item.id, moveTo)}
                  >
                    {moveLabel}
                  </button>
                  {item.overridden ? (
                    <button
                      type="button"
                      disabled={busy}
                      className="text-[11px] text-muted hover:underline disabled:opacity-50"
                      onClick={() => void onSetLayer(item.id, null)}
                    >
                      恢复自动
                    </button>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
