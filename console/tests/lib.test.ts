import { describe, expect, it } from "vitest";
import type { Span, Ticket, TicketEvent } from "../src/lib/api";
import {
  displayName,
  formatWhen,
  humanize,
  initials,
  money,
  needsAttention,
  orderRef,
  outcomeOf,
  stepsFromEvents,
  toolLabel,
} from "../src/lib/present";
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

describe("trace labels", () => {
  it("shows readable names, never internal identifiers", () => {
    expect(label(SPANS[0])).toBe("Model call, m");
    expect(label(SPANS[1])).toBe("Investigation");
    expect(label(SPANS[2])).toBe("Ticket run");
    expect(label(span("x", null, "tool.get_customer_overview", "tool", 0, 1))).toBe("Reviewed the customer's account");
    expect(label(span("y", null, "tool.some_new_tool", "tool", 0, 1))).toBe("Some new tool");
  });

  it("lists readable attribute titles with JSON pretty-printed and no internal markers", () => {
    const s = span("x", null, "tool.get_order", "tool", 0, 1, {
      "parley.kind": "tool",
      arguments: '{"order_id":3}',
      ok: true,
    });
    expect(details(s)).toEqual([
      ["Arguments", '{\n  "order_id": 3\n}'],
      ["Succeeded", "true"],
    ]);
  });

  it("sums model calls, tokens and cost", () => {
    expect(totals(SPANS)).toEqual({ calls: 1, tokens: 120, cost: 0.002 });
  });
});

describe("wording and formatting", () => {
  it("turns tool and identifier names into plain language", () => {
    expect(toolLabel("check_refund_eligibility")).toBe("Checked refund eligibility");
    expect(toolLabel("brand_new_tool")).toBe("Brand new tool");
    expect(humanize("node.respond")).toBe("Respond");
  });

  it("formats money, names, initials and order references", () => {
    expect(money(4900)).toBe("$49.00");
    expect(money(123456)).toBe("$1,234.56");
    expect(initials("Donald Fischer")).toBe("DF");
    expect(initials("ken.smith.59@example.com")).toBe("KS");
    expect(orderRef("order 95")).toBe("Order #95");
    expect(displayName({ customer_name: null, sender_email: "a@b.co" })).toBe("a@b.co");
    expect(displayName({ customer_name: "Ada Lovelace", sender_email: "a@b.co" })).toBe("Ada Lovelace");
  });

  it("shows timestamps as absolute UTC so a pinned demo clock reads correctly", () => {
    expect(formatWhen("2026-06-01T12:00:00.123456Z")).toBe("Jun 1, 12:00 PM");
  });
});

function ticket(overrides: Partial<Ticket>): Ticket {
  return {
    id: "T-1",
    number: 1001,
    customer_name: "Ada Lovelace",
    policies: [],
    sender_email: "ada@example.com",
    subject: "s",
    body: "b",
    status: "resolved",
    specialist: "billing",
    reply: "r",
    followup: "",
    cost_usd: 0.003,
    latency_s: 6,
    trace_id: null,
    pending: [],
    result: {},
    error: null,
    created_at: "2026-06-01T12:00:00Z",
    updated_at: "2026-06-01T12:00:00Z",
    ...overrides,
  };
}

describe("outcomeOf", () => {
  it("summarizes what happened to a ticket", () => {
    const refund = { name: "issue_refund", ok: true, arguments: { target: "order", target_id: 95, amount_cents: 11000 } };
    expect(outcomeOf(ticket({ result: { actions: [{ name: "get_order", ok: true, arguments: {} }, refund] } }))).toEqual({
      tone: "ok",
      label: "Refund issued",
      detail: "$110.00",
    });
    expect(
      outcomeOf(ticket({ status: "awaiting_approval", pending: [{ refund_id: 1, amount_cents: 22000, target: "order 160" }] })),
    ).toEqual({ tone: "warn", label: "Awaiting approval", detail: "$220.00" });
    expect(outcomeOf(ticket({ result: { escalations: [{ reason: "x", summary: "y" }] } })).label).toBe("Handed to a human");
    expect(outcomeOf(ticket({ result: { actions: [{ name: "cancel_subscription", ok: true, arguments: {} }] } })).label).toBe(
      "Cancellation scheduled",
    );
    expect(outcomeOf(ticket({})).label).toBe("Answered");
    expect(outcomeOf(ticket({ status: "running" })).label).toBe("In progress");
    expect(outcomeOf(ticket({ status: "failed" })).tone).toBe("bad");
  });

  it("flags tickets that need a person", () => {
    expect(needsAttention(ticket({ status: "awaiting_approval" }))).toBe(true);
    expect(needsAttention(ticket({ result: { escalations: [{ reason: "x", summary: "y" }] } }))).toBe(true);
    expect(needsAttention(ticket({}))).toBe(false);
  });
});

describe("stepsFromEvents", () => {
  const events: TicketEvent[] = [
    { id: 1, kind: "queued", data: {}, at: "" },
    { id: 2, kind: "status", data: { status: "running" }, at: "" },
    { id: 3, kind: "node", data: { node: "triage", specialist: "subscription" }, at: "" },
    { id: 4, kind: "node", data: { node: "investigate", tools: ["get_order", "get_order", "check_refund_eligibility"] }, at: "" },
    { id: 5, kind: "node", data: { node: "critic", approved: false, issues: ["The refund exceeds the window."] }, at: "" },
    { id: 6, kind: "node", data: { node: "critic", approved: true, issues: [] }, at: "" },
    { id: 7, kind: "node", data: { node: "execute", actions: ["issue_refund"] }, at: "" },
    { id: 8, kind: "node", data: { node: "respond" }, at: "" },
    { id: 9, kind: "node", data: { node: "remember" }, at: "" },
    { id: 10, kind: "reply", data: {}, at: "" },
    { id: 11, kind: "status", data: { status: "resolved" }, at: "" },
  ];

  it("tells the story in plain words and drops internal bookkeeping", () => {
    const steps = stepsFromEvents(events);
    expect(steps.map((s) => s.title)).toEqual([
      "Ticket received",
      "Routed to the Subscriptions team",
      "Investigated the case",
      "Policy review asked for changes",
      "Policy review approved the plan",
      "Carried out the plan",
      "Reply written",
      "Resolved",
    ]);
    expect(steps[2].items).toEqual(["Looked up the order", "Checked refund eligibility"]);
    expect(steps[3].note).toBe("The refund exceeds the window.");
    expect(steps[5].items).toEqual(["Refund issued"]);
    const text = JSON.stringify(steps);
    expect(text).not.toMatch(/get_order|issue_refund|check_refund|remember|node/);
  });

  it("reports a waiting approval, a human decision and a failure", () => {
    const waiting = stepsFromEvents([{ id: 1, kind: "status", data: { status: "awaiting_approval" }, at: "" }]);
    expect(waiting[0]).toMatchObject({ title: "Waiting for a human to approve the refund", tone: "warn" });
    const decided = stepsFromEvents([{ id: 2, kind: "decision", data: { decisions: { "5": false } }, at: "" }]);
    expect(decided[0].title).toBe("A human declined the refund");
    const failed = stepsFromEvents([{ id: 3, kind: "failed", data: { error: "x".repeat(400) }, at: "" }]);
    expect(failed[0].tone).toBe("bad");
    expect(failed[0].note?.length).toBeLessThanOrEqual(150);
  });
});
