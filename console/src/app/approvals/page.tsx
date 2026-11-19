"use client";

import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { DecisionPanel } from "@/components/DecisionPanel";
import { Avatar, Empty, Skeleton } from "@/components/ui";
import { api, type Ticket } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { displayName, formatWhen, money } from "@/lib/present";

function reasonOf(t: Ticket): string | null {
  const proposal = (t.result.actions ?? []).find((a) => a.name === "propose_refund");
  const reason = proposal?.arguments.reason;
  return typeof reason === "string" ? reason : null;
}

export default function Approvals() {
  const queue = usePolling(api.approvals, 3000);
  const stats = usePolling(api.stats, 8000);
  const limit = stats.data ? money(stats.data.approval_threshold_cents) : "the threshold";
  const items = queue.data;
  return (
    <div className="page" style={{ maxWidth: 820, margin: "0 auto" }}>
      <div className="page-head">
        <div>
          <p className="eyebrow">Approvals</p>
          <h1>Waiting for your decision</h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Refunds above {limit} stop here. The agents carry on as soon as you decide.
          </p>
        </div>
      </div>
      {queue.error && !items && (
        <p className="error" role="alert">
          The service is not reachable. {queue.error}
        </p>
      )}
      {!items && !queue.error && <Skeleton height={180} />}
      {items && !items.length && (
        <div className="card">
          <Empty icon={<ShieldCheck size={22} />} title="Nothing is waiting">
            New refunds above {limit} will show up here.
          </Empty>
        </div>
      )}
      {items?.map((ticket) => {
        const name = displayName(ticket);
        const total = ticket.pending.reduce((n, p) => n + p.amount_cents, 0);
        const reason = reasonOf(ticket);
        return (
          <article key={ticket.id} className="card approval-card">
            <div className="approval-top">
              <div className="who">
                <Avatar name={name} />
                <div>
                  <strong>{name}</strong>
                  <Link href={`/tickets/${ticket.id}`} className="muted small">
                    Ticket #{ticket.number}, {formatWhen(ticket.created_at)}
                  </Link>
                </div>
              </div>
              <div>
                <div className="amount">{money(total)}</div>
                <div className="faint small" style={{ textAlign: "right" }}>
                  refund requested
                </div>
              </div>
            </div>
            <div>
              <p className="small faint" style={{ marginBottom: 6 }}>
                {ticket.subject}
              </p>
              <p className="quote">{ticket.body}</p>
            </div>
            {reason && (
              <p className="muted">
                <strong style={{ color: "var(--text)" }}>Why the agents proposed it: </strong>
                {reason}
              </p>
            )}
            <DecisionPanel ticket={ticket} onDone={queue.refresh} />
          </article>
        );
      })}
    </div>
  );
}
