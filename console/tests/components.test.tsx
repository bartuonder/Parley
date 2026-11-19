import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Span, Ticket, TicketEvent } from "../src/lib/api";
import { AgentTimeline } from "../src/components/AgentTimeline";
import { DecisionPanel } from "../src/components/DecisionPanel";
import { TraceView } from "../src/components/TraceView";
import { Avatar, OutcomeChip } from "../src/components/ui";

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

describe("DecisionPanel", () => {
  it("needs a choice for every refund before it can confirm, then sends them all", async () => {
    decide.mockResolvedValue({});
    const done = vi.fn();
    const user = userEvent.setup();
    render(<DecisionPanel ticket={ticket} onDone={done} />);
    expect(screen.getByText("$249.00")).toBeInTheDocument();
    expect(screen.getByText(/Order #3/)).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Confirm decision" });
    expect(confirm).toBeDisabled();
    const [approveFirst, approveSecond] = screen.getAllByRole("button", { name: "Approve" });
    await user.click(approveFirst);
    expect(confirm).toBeDisabled();
    await user.click(screen.getAllByRole("button", { name: "Decline" })[1]);
    expect(confirm).toBeEnabled();
    expect(approveSecond).toHaveAttribute("aria-pressed", "false");
    await user.click(confirm);
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(decide).toHaveBeenCalledWith("T-1", { "7": true, "8": false });
  });

  it("shows the error and stays usable when the decision is refused", async () => {
    decide.mockRejectedValue(new Error("This ticket is not waiting for a decision"));
    const user = userEvent.setup();
    render(<DecisionPanel ticket={ticket} onDone={vi.fn()} />);
    for (const button of screen.getAllByRole("button", { name: "Approve" })) await user.click(button);
    await user.click(screen.getByRole("button", { name: "Confirm decision" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not waiting");
    expect(screen.getByRole("button", { name: "Confirm decision" })).toBeEnabled();
  });
});

describe("AgentTimeline", () => {
  const events: TicketEvent[] = [
    { id: 1, kind: "queued", data: {}, at: "" },
    { id: 2, kind: "node", data: { node: "triage", specialist: "shipping" }, at: "" },
    { id: 3, kind: "node", data: { node: "investigate", tools: ["get_order", "check_refund_eligibility"] }, at: "" },
  ];

  it("describes the work in plain language without tool names", () => {
    render(<AgentTimeline events={events} live />);
    expect(screen.getByText("Routed to the Shipping team")).toBeInTheDocument();
    expect(screen.getByText("Looked up the order")).toBeInTheDocument();
    expect(screen.getByText("Checked refund eligibility")).toBeInTheDocument();
    expect(screen.queryByText(/get_order|check_refund_eligibility/)).toBeNull();
    expect(screen.getByText("Working on it...")).toBeInTheDocument();
  });

  it("stops saying it is working once the stream has ended", () => {
    render(<AgentTimeline events={events} live={false} />);
    expect(screen.queryByText("Working on it...")).toBeNull();
  });
});

describe("TraceView", () => {
  const spans: Span[] = [
    { span_id: "t", parent_id: null, name: "ticket", kind: "ticket", started_at: "2026-06-01T12:00:00Z", duration_ms: 900, status: "ok", attributes: {} },
    {
      span_id: "x",
      parent_id: "t",
      name: "tool.check_refund_eligibility",
      kind: "tool",
      started_at: "2026-06-01T12:00:00.1Z",
      duration_ms: 20,
      status: "ok",
      attributes: { arguments: '{"target":"order","target_id":95}', output: '{"ok":true}' },
    },
  ];

  it("lists readable steps and shows arguments only when a step is opened", async () => {
    const user = userEvent.setup();
    render(<TraceView spans={spans} />);
    expect(screen.getByText(/2 steps, 0 model calls/)).toBeInTheDocument();
    expect(screen.queryByText("check_refund_eligibility")).toBeNull();
    expect(screen.queryByText(/target_id/)).toBeNull();
    await user.click(screen.getByRole("button", { name: /Checked refund eligibility/ }));
    expect(screen.getByText(/"target_id": 95/)).toBeInTheDocument();
  });

  it("says so when there is no trace", () => {
    render(<TraceView spans={[]} />);
    expect(screen.getByText("No trace recorded yet.")).toBeInTheDocument();
  });
});

describe("small pieces", () => {
  it("shows initials for a customer and an outcome with its amount", () => {
    render(
      <>
        <Avatar name="Donald Fischer" />
        <OutcomeChip outcome={{ tone: "ok", label: "Refund issued", detail: "$110.00" }} />
      </>,
    );
    expect(screen.getByText("DF")).toBeInTheDocument();
    expect(screen.getByText("Refund issued")).toBeInTheDocument();
    expect(screen.getByText("$110.00")).toBeInTheDocument();
  });
});
