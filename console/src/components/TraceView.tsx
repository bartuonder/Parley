"use client";

import { Code2 } from "lucide-react";
import { useState } from "react";
import type { Span } from "@/lib/api";
import { buildRows, details, label, totals } from "@/lib/trace";

const usd = (v: number): string => (v >= 0.01 ? `$${v.toFixed(3)}` : `$${v.toFixed(4)}`);

export function TraceView({ spans }: { spans: Span[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const rows = buildRows(spans);
  const sum = totals(spans);
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <p className="trace-note">
        <Code2 size={16} />
        Developer view. Every model call, tool call and step of this ticket, with personal data masked.
      </p>
      {!rows.length ? (
        <p className="muted">No trace recorded yet.</p>
      ) : (
        <>
          <p className="muted small">
            {rows.length} steps, {sum.calls} model calls, {sum.tokens.toLocaleString("en-US")} tokens, {usd(sum.cost)}
          </p>
          <ul className="card trace">
            {rows.map(({ span, depth, offsetPct, widthPct }) => {
              const expanded = open === span.span_id;
              const info = details(span);
              return (
                <li key={span.span_id}>
                  <button
                    type="button"
                    className="trace-row"
                    aria-expanded={expanded}
                    onClick={() => setOpen(expanded ? null : span.span_id)}
                  >
                    <span className="trace-name" style={{ paddingLeft: `${depth * 16}px` }}>
                      {label(span)}
                    </span>
                    <span className="trace-bar">
                      <i className={`k-${span.kind}`} style={{ left: `${offsetPct}%`, width: `${widthPct}%` }} />
                    </span>
                    <span className="trace-ms">{Math.round(span.duration_ms)} ms</span>
                  </button>
                  {expanded && (
                    <dl className="trace-detail">
                      {info.length ? (
                        info.map(([key, value]) => (
                          <div key={key}>
                            <dt>{key}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))
                      ) : (
                        <div>
                          <dt>Details</dt>
                          <dd>Nothing else was recorded for this step.</dd>
                        </div>
                      )}
                    </dl>
                  )}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
