"use client";

import { useEffect, useMemo, useState } from "react";
import { searchKnowledge } from "@/lib/api";
import { emptyCopy } from "@/lib/copy";
import type { KnowledgeHit, KnowledgeSearchResponse, NodeKind } from "@/lib/types";

const KIND_LABEL: Record<NodeKind, string> = {
  goal: "主题",
  concept: "概念",
  claim: "主张",
  decision: "决策",
  source: "来源",
  misconception: "误区",
};

export function KnowledgeSearch({
  onLocate,
  onHits,
}: {
  onLocate: (id: string, pathIds: string[]) => void;
  onHits: (ids: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<KnowledgeSearchResponse | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const needle = query.trim();
    if (!needle) {
      setResult(null);
      onHits([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void searchKnowledge(needle)
        .then((next) => {
          setResult(next);
          onHits([
            ...next.concepts.map((hit) => hit.id),
            ...next.claims.map((hit) => hit.id),
            ...next.sources.map((hit) => hit.id),
          ]);
        })
        .catch(() => {
          setResult({
            query: needle,
            concepts: [],
            claims: [],
            sources: [],
            unknown: true,
          });
          onHits([]);
        });
    }, 220);
    return () => window.clearTimeout(timer);
  }, [query, onHits]);

  const groups = useMemo(() => {
    const claims = result?.claims ?? [];
    const keep = claims.filter((hit) => hit.layer === "keep");
    const lookup = claims.filter((hit) => hit.layer !== "keep");
    return [
      { key: "concepts" as const, label: "概念", items: result?.concepts ?? [] },
      { key: "keep" as const, label: "主张 · 上层", items: keep },
      { key: "lookup" as const, label: "主张 · 需要时再查", items: lookup },
      { key: "sources" as const, label: "来源", items: result?.sources ?? [] },
    ].filter((group) => group.items.length > 0);
  }, [result]);

  return (
    <div className="relative w-72">
      <input
        className="w-full rounded-sm border border-line bg-panel px-3 py-1.5 text-sm outline-none placeholder:text-muted/70 focus:border-gold"
        placeholder="搜索当前主题的知识点"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && query.trim() ? (
        <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-80 overflow-y-auto border border-line bg-panel shadow-lg">
          {result == null ? (
            <p className="px-3 py-2 text-xs text-muted">正在检索…</p>
          ) : result.unknown ? (
            <p className="px-3 py-2 text-xs leading-5 text-clay">{emptyCopy.noHits}</p>
          ) : (
            groups.map((group) => (
              <section key={group.key} className="border-b border-line last:border-b-0">
                <h3 className="px-3 pt-2 text-[10px] uppercase tracking-[0.16em] text-muted">{group.label}</h3>
                <ul>
                  {group.items.map((hit) => (
                    <HitRow
                      key={hit.id}
                      hit={hit}
                      onPick={() => {
                        onLocate(hit.id, hit.path_ids);
                        setOpen(false);
                      }}
                    />
                  ))}
                </ul>
              </section>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

function HitRow({ hit, onPick }: { hit: KnowledgeHit; onPick: () => void }) {
  const candidate = hit.status === "candidate";
  return (
    <li>
      <button
        type="button"
        onClick={onPick}
        className="w-full px-3 py-2 text-left hover:bg-gold/10"
      >
        <p className={`text-sm leading-5 ${candidate ? "text-muted" : ""}`}>
          <span className="mr-2 text-[10px] text-gold">{KIND_LABEL[hit.kind]}</span>
          {hit.layer === "keep" ? <span className="mr-2 text-[10px] text-gold">上层</span> : null}
          {hit.layer === "lookup" && hit.kind === "claim" ? (
            <span className="mr-2 text-[10px] text-muted">细节</span>
          ) : null}
          {hit.label}
        </p>
        {hit.snippet ? <p className="mt-1 line-clamp-2 text-[11px] text-muted">{hit.snippet}</p> : null}
      </button>
    </li>
  );
}
