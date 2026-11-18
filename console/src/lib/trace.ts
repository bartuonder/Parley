import type { Span } from "./api";

export type Row = {
  span: Span;
  depth: number;
  offsetPct: number;
  widthPct: number;
};

const MIN_WIDTH_PCT = 0.8;

export function buildRows(spans: Span[]): Row[] {
  if (!spans.length) return [];
  const byId = new Map(spans.map((s) => [s.span_id, s]));
  const children = new Map<string | null, Span[]>();
  for (const s of spans) {
    const key = s.parent_id && byId.has(s.parent_id) ? s.parent_id : null;
    children.set(key, [...(children.get(key) ?? []), s]);
  }
  const start = Math.min(...spans.map((s) => Date.parse(s.started_at)));
  const end = Math.max(...spans.map((s) => Date.parse(s.started_at) + s.duration_ms));
  const total = Math.max(end - start, 1);
  const rows: Row[] = [];
  const visit = (parent: string | null, depth: number): void => {
    const ordered = [...(children.get(parent) ?? [])].sort(
      (a, b) => Date.parse(a.started_at) - Date.parse(b.started_at),
    );
    for (const span of ordered) {
      rows.push({
        span,
        depth,
        offsetPct: ((Date.parse(span.started_at) - start) / total) * 100,
        widthPct: Math.max((span.duration_ms / total) * 100, MIN_WIDTH_PCT),
      });
      visit(span.span_id, depth + 1);
    }
  };
  visit(null, 0);
  return rows;
}

export function label(span: Span): string {
  const model = span.attributes.model;
  if (span.kind === "llm" && typeof model === "string") return `${span.name} (${model})`;
  return span.name;
}

export function details(span: Span): [string, string][] {
  const out: [string, string][] = [];
  for (const [key, value] of Object.entries(span.attributes)) {
    if (key === "parley.kind") continue;
    out.push([key, typeof value === "string" ? value : JSON.stringify(value)]);
  }
  return out;
}

export function totals(spans: Span[]): { calls: number; tokens: number; cost: number } {
  const llm = spans.filter((s) => s.kind === "llm");
  const num = (s: Span, key: string): number => {
    const v = s.attributes[key];
    return typeof v === "number" ? v : 0;
  };
  return {
    calls: llm.length,
    tokens: llm.reduce((n, s) => n + num(s, "prompt_tokens") + num(s, "completion_tokens"), 0),
    cost: llm.reduce((n, s) => n + num(s, "cost_usd"), 0),
  };
}
