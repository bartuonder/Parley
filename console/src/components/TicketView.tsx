"use client";

import Link from "next/link";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { Timeline } from "@/components/Timeline";
import { TraceView } from "@/components/TraceView";
import { api } from "@/lib/api";
import { seconds, usd } from "@/lib/format";
import { usePolling, useTicketEvents } from "@/lib/hooks";

export function TicketView({ id }: { id: string }) {
  const ticket = usePolling(() => api.ticket(id), 2000);
  const t = ticket.data;
  const settled = t !== null && (t.status === "resolved" || t.status === "failed");
  const trace = usePolling(() => (t?.trace_id ? api.trace(id) : Promise.resolve([])), settled ? 0 : 3000);
  const stream = useTicketEvents(id, t?.status ?? "");

  if (ticket.error && !t) {
    return (
      <p className="error" role="alert">
        {ticket.error}. <Link href="/">Back to tickets</Link>
      </p>
    );
  }
  if (!t) return <p className="muted">Loading...</p>;

  const refresh = (): void => {
    ticket.refresh();
    trace.refresh();
  };

  return (
    <div className="ticket">
      <p>
        <Link href="/">All tickets</Link>
      </p>
      <header className="ticket-head">
        <h1>{t.subject}</h1>
        <StatusBadge status={t.status} />
      </header>
      <p className="muted small">
        {t.id} | {t.sender_email}
        {t.specialist ? ` | ${t.specialist} specialist` : ""}
        {t.cost_usd ? ` | ${usd(t.cost_usd)}` : ""}
        {t.latency_s ? ` | ${seconds(t.latency_s)}` : ""}
      </p>

      <div className="columns">
        <section aria-label="Conversation">
          <h2>Conversation</h2>
          <div className="bubble customer">
            <div className="muted small">Customer</div>
            {t.body}
          </div>
          {t.reply && (
            <div className="bubble agent">
              <div className="muted small">Parley</div>
              {t.reply}
            </div>
          )}
          {t.followup && (
            <div className="bubble agent">
              <div className="muted small">Parley, after the human decision</div>
              {t.followup}
            </div>
          )}
          {t.error && <p className="error" role="alert">{t.error}</p>}
          {t.status === "awaiting_approval" && (
            <div className="card">
              <h3>Waiting for a human</h3>
              <ApprovalPanel ticket={t} onDone={refresh} />
            </div>
          )}
          {t.result.escalations?.map((e, i) => (
            <p key={i} className="note">
              Handed to a human ({e.reason}): {e.summary}
            </p>
          ))}
          {t.result.guard_events?.length ? (
            <p className="note">Guards flagged: {[...new Set(t.result.guard_events)].join(", ")}</p>
          ) : null}
        </section>

        <section aria-label="Live steps">
          <h2>Steps</h2>
          <Timeline events={stream.events} live={stream.live && !settled} />
        </section>
      </div>

      <section aria-label="Trace">
        <h2>Trace</h2>
        <TraceView spans={trace.data ?? []} />
      </section>
    </div>
  );
}
