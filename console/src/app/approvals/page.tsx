"use client";

import Link from "next/link";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { api } from "@/lib/api";
import { ago } from "@/lib/format";
import { usePolling } from "@/lib/hooks";

export default function Approvals() {
  const queue = usePolling(api.approvals, 3000);
  return (
    <section aria-label="Approval queue">
      <h1>Approval queue</h1>
      <p className="muted">Refunds above the approval threshold wait here for a human decision.</p>
      {queue.error && <p className="error" role="alert">{queue.error}</p>}
      {queue.data && !queue.data.length && <p className="muted">Nothing is waiting.</p>}
      {queue.data?.map((ticket) => (
        <article key={ticket.id} className="card">
          <header className="card-head">
            <Link href={`/tickets/${ticket.id}`}>{ticket.subject}</Link>
            <span className="muted small">
              {ticket.sender_email}, {ago(ticket.created_at)}
            </span>
          </header>
          <p className="quote">{ticket.body}</p>
          <ApprovalPanel ticket={ticket} onDone={queue.refresh} />
        </article>
      ))}
    </section>
  );
}
