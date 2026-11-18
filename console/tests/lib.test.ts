import { describe, expect, it } from "vitest";
import type { Span } from "../src/lib/api";
import { ago, money, usd } from "../src/lib/format";
import { buildRows, details, label, totals } from "../src/lib/trace";

function span(id: string, parent: string | null, name: string, kind: string, at: number, ms: number, attributes = {}): Span {
  return {
    span_id: id,
    parent_id: parent,
    name,
    kind,
    started_at: new Date(1_700_000_000_000 + at).toISOString(),
    duration_ms: ms,
    status: "ok",
    attributes,
  };
}

const SPANS: Span[] = [
  span("c", "n1", "llm.complete", "llm", 120, 300, { model: "m", prompt_tokens: 100, completion_tokens: 20, cost_usd: 0.002 }),
  span("n1", "t", "node.investigate", "node", 100, 600),
  span("t", null, "ticket", "ticket", 0, 1000),
  span("n0", "t", "node.triage", "node", 10, 80),
];

describe("buildRows", () => {
  it("orders spans as a tree by start time and indents children", () => {
    const rows = buildRows(SPANS);
    expect(rows.map((r) => r.span.span_id)).toEqual(["t", "n0", "n1", "c"]);
    expect(rows.map((r) => r.depth)).toEqual([0, 1, 1, 2]);
  });

  it("places bars relative to the whole trace", () => {
    const rows = buildRows(SPANS);
    expect(rows[0].offsetPct).toBe(0);
    expect(rows[0].widthPct).toBe(100);
    expect(rows[2].offsetPct).toBeCloseTo(10);
    expect(rows[2].widthPct).toBeCloseTo(60);
  });

  it("keeps very short spans visible and tolerates a missing parent", () => {
    const rows = buildRows([span("a", "gone", "tool.x", "tool", 0, 0.001), span("b", null, "ticket", "ticket", 0, 500)]);
    expect(rows).toHaveLength(2);
    expect(rows.find((r) => r.span.span_id === "a")?.widthPct).toBeGreaterThan(0.5);
    expect(buildRows([])).toEqual([]);
  });
});

describe("trace helpers", () => {
  it("labels model calls with the model and lists attributes without the kind marker", () => {
    expect(label(SPANS[0])).toBe("llm.complete (m)");
    expect(label(SPANS[1])).toBe("node.investigate");
    const s = span("x", null, "tool.get_order", "tool", 0, 1, { "parley.kind": "tool", arguments: "{}", ok: true });
    expect(details(s)).toEqual([
      ["arguments", "{}"],
      ["ok", "true"],
    ]);
  });

  it("sums model calls, tokens and cost", () => {
    expect(totals(SPANS)).toEqual({ calls: 1, tokens: 120, cost: 0.002 });
  });
});

describe("format", () => {
  it("formats money and cost", () => {
    expect(money(4900)).toBe("$49.00");
    expect(usd(0.0031)).toBe("$0.0031");
    expect(usd(0.5)).toBe("$0.500");
  });

  it("says how long ago something happened", () => {
    const now = new Date("2026-06-01T12:00:00Z");
    expect(ago("2026-06-01T11:59:30Z", now)).toBe("30s ago");
    expect(ago("2026-06-01T11:00:00Z", now)).toBe("1h ago");
    expect(ago("2026-05-30T12:00:00Z", now)).toBe("2d ago");
  });
});
