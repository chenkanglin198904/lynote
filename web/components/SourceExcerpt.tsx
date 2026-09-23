"use client";

import { useEffect, useRef } from "react";
import type { EvidenceExcerpt } from "@/lib/types";

export function SourceExcerpt({
  excerpt,
  onOpenSource,
  onOpenClaim,
}: {
  excerpt: EvidenceExcerpt;
  onOpenSource?: (id: string) => void;
  onOpenClaim?: (id: string) => void;
}) {
  const hitRef = useRef<HTMLElement>(null);

  useEffect(() => {
    hitRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [excerpt.source_id, excerpt.source_span?.start, excerpt.source_span?.end, excerpt.hit]);

  return (
    <article className="border border-line bg-raised p-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted">
        <button
          type="button"
          onClick={() => onOpenSource?.(excerpt.source_id)}
          className="text-gold hover:underline"
        >
          {excerpt.source_title}
        </button>
        {excerpt.claim_id ? (
          <button
            type="button"
            onClick={() => onOpenClaim?.(excerpt.claim_id!)}
            className="hover:underline"
          >
            {excerpt.claim_id}
          </button>
        ) : null}
        {excerpt.source_span ? (
          <span>
            字符 {excerpt.source_span.start}–{excerpt.source_span.end}
          </span>
        ) : null}
        <span className={excerpt.aligned ? "text-moss" : "text-clay"}>
          {excerpt.aligned ? "已对齐原文" : "未能对齐"}
        </span>
      </div>
      {excerpt.claim_text ? (
        <p className="mt-2 text-sm leading-6">{excerpt.claim_text}</p>
      ) : null}
      {excerpt.quote ? (
        <p className="mt-2 text-xs leading-5 text-muted">引用：{excerpt.quote}</p>
      ) : null}
      {excerpt.note ? <p className="mt-2 text-xs leading-5 text-clay">{excerpt.note}</p> : null}
      <div className="mt-3 max-h-48 overflow-y-auto whitespace-pre-wrap border border-line bg-ink px-3 py-2 text-sm leading-6">
        {excerpt.before}
        {excerpt.hit ? (
          <mark ref={hitRef} className="bg-gold/35 text-paper">
            {excerpt.hit}
          </mark>
        ) : null}
        {excerpt.after}
      </div>
    </article>
  );
}
