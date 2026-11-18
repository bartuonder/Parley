"use client";

import { useState } from "react";
import type { Span } from "@/lib/api";
import { usd } from "@/lib/format";
import { buildRows, details, label, totals } from "@/lib/trace";

export function TraceView({ spans }: { spans: Span[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const rows = buildRows(spans);
  const sum = totals(spans);
  if (!rows.length) return <p className="muted">No trace yet.</p>;
  return (
    <div className="trace">
      <p className="muted">
        {rows.length} spans, {sum.calls} model calls, {sum.tokens.toLocaleString()} tokens, {usd(sum.cost)}
      </p>
      <ul>
        {rows.map(({ span, depth, offsetPct, widthPct }) => {
          const expanded = open === span.span_id;
          return (
            <li key={span.span_id}>
              <button
                type="button"
                className="trace-row"
                aria-expanded={expanded}
                onClick={() => setOpen(expanded ? null : span.span_id)}
              >
                <span className="trace-name" style={{ paddingLeft: `${depth * 14}px` }}>
                  {label(span)}
                </span>
                <span className="trace-bar">
                  <span
                    className={`bar bar-${span.kind}${span.status === "error" ? " bar-error" : ""}`}
                    style={{ left: `${offsetPct}%`, width: `${widthPct}%` }}
                  />
                </span>
                <span className="trace-ms">{Math.round(span.duration_ms)} ms</span>
              </button>
              {expanded && (
                <dl className="trace-details">
                  {details(span).map(([key, value]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
