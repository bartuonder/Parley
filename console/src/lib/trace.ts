import type { Span } from "./api";
import { humanize, toolLabel } from "./present";

export type Row = {
  span: Span;
  depth: number;
  offsetPct: number;
  widthPct: number;
};

const MIN_WIDTH_PCT = 0.8;

const NODE_LABEL: Record<string, string> = {
  triage: "Routing",
  investigate: "Investigation",
  critic: "Policy review",
  handover: "Handover",
  execute: "Execution",
  respond: "Reply writing",
  remember: "Memory update",
  approval: "Human approval",
};

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
  if (span.kind === "llm") return typeof model === "string" ? `Model call, ${model}` : "Model call";
  if (span.kind === "tool") return toolLabel(span.name.replace(/^tool\./, ""));
  if (span.kind === "node") return NODE_LABEL[span.name.replace(/^node\./, "")] ?? humanize(span.name);
  if (span.kind === "ticket") return "Ticket run";
  if (span.kind === "rag") return "Policy search";
  return humanize(span.name);
}

const SHOWN: Record<string, string> = {
  arguments: "Arguments",
  output: "Result",
  model: "Model",
  prompt_tokens: "Prompt tokens",
  completion_tokens: "Completion tokens",
  cached_tokens: "Cached tokens",
  cost_usd: "Cost (USD)",
  ok: "Succeeded",
  error_code: "Error code",
  cache_hit: "Cache hit",
};

function pretty(value: unknown): string {
  if (typeof value !== "string") return JSON.stringify(value);
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

export function details(span: Span): [string, string][] {
  const out: [string, string][] = [];
  for (const [key, title] of Object.entries(SHOWN)) {
    if (key in span.attributes) out.push([title, pretty(span.attributes[key])]);
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
