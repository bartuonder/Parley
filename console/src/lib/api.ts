export type Status = "queued" | "running" | "awaiting_approval" | "resolved" | "failed";

export type PendingRefund = { refund_id: number; amount_cents: number; target: string };

export type Ticket = {
  id: string;
  sender_email: string;
  subject: string;
  body: string;
  status: Status;
  specialist: string | null;
  reply: string;
  followup: string;
  cost_usd: number;
  latency_s: number;
  trace_id: string | null;
  pending: PendingRefund[];
  result: {
    actions?: { name: string; arguments: Record<string, unknown>; ok: boolean }[];
    escalations?: { reason: string; summary: string }[];
    critic_issues?: string[];
    guard_events?: string[];
  };
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type Span = {
  span_id: string;
  parent_id: string | null;
  name: string;
  kind: string;
  started_at: string;
  duration_ms: number;
  status: string;
  attributes: Record<string, unknown>;
};

export type Stats = {
  by_status: Record<string, number>;
  tickets: number;
  total_cost_usd: number;
  mean_cost_usd: number;
  mean_latency_s: number;
};

export type TicketEvent = {
  id: number;
  kind: string;
  data: Record<string, unknown>;
  at: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: unknown };
    throw new ApiError(response.status, describe(body.detail) || response.statusText);
  }
  return (await response.json()) as T;
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg ?? "").join("; ");
  return "";
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  stats: () => request<Stats>("stats"),
  tickets: (status?: string) =>
    request<Ticket[]>(`tickets${status ? `?status=${encodeURIComponent(status)}` : ""}`),
  ticket: (id: string) => request<Ticket>(`tickets/${encodeURIComponent(id)}`),
  trace: (id: string) => request<Span[]>(`tickets/${encodeURIComponent(id)}/trace`),
  approvals: () => request<Ticket[]>("approvals"),
  create: (body: { sender_email: string; subject: string; body: string }) =>
    request<Ticket>("tickets", json(body)),
  decide: (id: string, decisions: Record<string, boolean>) =>
    request<Ticket>(`approvals/${encodeURIComponent(id)}/decision`, json({ decisions })),
};
