import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Span, Ticket, TicketEvent } from "../src/lib/api";
import { ApprovalPanel } from "../src/components/ApprovalPanel";
import { Timeline } from "../src/components/Timeline";
import { TraceView } from "../src/components/TraceView";

const decide = vi.fn();
vi.mock("../src/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../src/lib/api")>();
  return { ...original, api: { ...original.api, decide: (...args: unknown[]) => decide(...args) } };
});

afterEach(() => {
  cleanup();
  decide.mockReset();
});

const ticket = {
  id: "T-1",
  pending: [
    { refund_id: 7, amount_cents: 24900, target: "order 3" },
    { refund_id: 8, amount_cents: 12000, target: "order 4" },
  ],
} as unknown as Ticket;

describe("ApprovalPanel", () => {
  it("needs a choice for every refund before it can submit, then sends them all", async () => {
    decide.mockResolvedValue({});
    const done = vi.fn();
    const user = userEvent.setup();
    render(<ApprovalPanel ticket={ticket} onDone={done} />);
    const submit = screen.getByRole("button", { name: "Submit decision" });
    expect(submit).toBeDisabled();
    const [approveFirst, approveSecond] = screen.getAllByRole("button", { name: "Approve" });
    await user.click(approveFirst);
    expect(submit).toBeDisabled();
    await user.click(screen.getAllByRole("button", { name: "Decline" })[1]);
    expect(submit).toBeEnabled();
    expect(approveSecond).toHaveAttribute("aria-pressed", "false");
    await user.click(submit);
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(decide).toHaveBeenCalledWith("T-1", { "7": true, "8": false });
  });

  it("shows the error and stays usable when the decision is refused", async () => {
    decide.mockRejectedValue(new Error("not awaiting approval"));
    const user = userEvent.setup();
    render(<ApprovalPanel ticket={ticket} onDone={vi.fn()} />);
    for (const button of screen.getAllByRole("button", { name: "Approve" })) await user.click(button);
    await user.click(screen.getByRole("button", { name: "Submit decision" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not awaiting approval");
    expect(screen.getByRole("button", { name: "Submit decision" })).toBeEnabled();
  });
});

describe("Timeline", () => {
  const events: TicketEvent[] = [
    { id: 1, kind: "queued", data: {}, at: "" },
    { id: 2, kind: "status", data: { status: "running" }, at: "" },
    { id: 3, kind: "node", data: { node: "triage", specialist: "shipping" }, at: "" },
    { id: 4, kind: "node", data: { node: "investigate", tools: ["get_order", "check_refund_eligibility"] }, at: "" },
    { id: 5, kind: "node", data: { node: "critic", approved: false, issues: ["wrong window"] }, at: "" },
  ];

  it("describes each step in words and hides the noisy running status", () => {
    render(<Timeline events={events} live />);
    expect(screen.getByText("Routed to the shipping specialist")).toBeInTheDocument();
    expect(screen.getByText(/Investigated with 2 tool calls \(get_order, check_refund_eligibility\)/)).toBeInTheDocument();
    expect(screen.getByText("Policy critic sent it back: wrong window")).toBeInTheDocument();
    expect(screen.queryByText("Status: running")).toBeNull();
    expect(screen.getByText("Working...")).toBeInTheDocument();
  });

  it("stops saying it is working once the stream has ended", () => {
    render(<Timeline events={events} live={false} />);
    expect(screen.queryByText("Working...")).toBeNull();
  });
});

describe("TraceView", () => {
  const spans: Span[] = [
    { span_id: "t", parent_id: null, name: "ticket", kind: "ticket", started_at: "2026-06-01T12:00:00Z", duration_ms: 900, status: "ok", attributes: {} },
    {
      span_id: "x",
      parent_id: "t",
      name: "tool.get_order",
      kind: "tool",
      started_at: "2026-06-01T12:00:00.1Z",
      duration_ms: 20,
      status: "ok",
      attributes: { arguments: '{"order_id":3}', output: '{"ok":true}' },
    },
  ];

  it("lists spans with a summary and expands one to show its arguments", async () => {
    const user = userEvent.setup();
    render(<TraceView spans={spans} />);
    expect(screen.getByText(/2 spans, 0 model calls/)).toBeInTheDocument();
    expect(screen.queryByText('{"order_id":3}')).toBeNull();
    await user.click(screen.getByRole("button", { name: /tool\.get_order/ }));
    expect(screen.getByText('{"order_id":3}')).toBeInTheDocument();
  });

  it("says so when there is no trace", () => {
    render(<TraceView spans={[]} />);
    expect(screen.getByText("No trace yet.")).toBeInTheDocument();
  });
});
