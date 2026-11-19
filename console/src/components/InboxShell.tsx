"use client";

import { Inbox, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useComposer } from "@/components/Composer";
import { Avatar, Empty, OutcomeChip, Skeleton } from "@/components/ui";
import { api, type Ticket } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { displayName, formatWhen, needsAttention, outcomeOf, SPECIALIST_LABEL } from "@/lib/present";

type Filter = "all" | "attention" | "resolved";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "attention", label: "Needs a person" },
  { id: "resolved", label: "Resolved" },
];

function matches(filter: Filter, t: Ticket): boolean {
  if (filter === "attention") return needsAttention(t);
  if (filter === "resolved") return t.status === "resolved" && !needsAttention(t);
  return true;
}

function Row({ ticket, active }: { ticket: Ticket; active: boolean }) {
  const name = displayName(ticket);
  return (
    <Link href={`/tickets/${ticket.id}`} className="row" aria-current={active ? "page" : undefined}>
      <Avatar name={name} />
      <div style={{ minWidth: 0 }}>
        <div className="row-top">
          <span className="row-name">{name}</span>
          <span className="row-time">{formatWhen(ticket.created_at)}</span>
        </div>
        <div className="row-subject">{ticket.subject}</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <OutcomeChip outcome={outcomeOf(ticket)} />
          {ticket.specialist && (
            <span className="chip plain tone-neutral">{SPECIALIST_LABEL[ticket.specialist] ?? ticket.specialist}</span>
          )}
        </div>
      </div>
    </Link>
  );
}

export function InboxShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const composer = useComposer();
  const tickets = usePolling(() => api.tickets(), 3000);
  const [filter, setFilter] = useState<Filter>("all");
  const activeId = path.startsWith("/tickets/") ? decodeURIComponent(path.split("/")[2] ?? "") : null;
  const shown = (tickets.data ?? []).filter((t) => matches(filter, t));

  return (
    <div className="inbox" data-detail={activeId ? "true" : "false"}>
      <section className="pane-list" aria-label="Tickets">
        <div className="pane-head">
          <div className="pane-title">
            <h1>Inbox</h1>
            <button type="button" className="btn primary" onClick={() => composer.open()}>
              <Plus size={16} />
              New ticket
            </button>
          </div>
          <div className="tabs" role="tablist" aria-label="Filter tickets">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                className="tab"
                aria-selected={filter === f.id}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <div className="list">
          {!tickets.data && !tickets.error && (
            <div style={{ display: "grid", gap: 18, padding: 12 }}>
              {[0, 1, 2, 3].map((i) => (
                <div key={i} style={{ display: "grid", gap: 8 }}>
                  <Skeleton width="55%" />
                  <Skeleton width="80%" />
                </div>
              ))}
            </div>
          )}
          {tickets.error && !tickets.data && (
            <p className="error" role="alert" style={{ padding: 16 }}>
              The service is not reachable. {tickets.error}
            </p>
          )}
          {tickets.data && !shown.length && (
            <Empty icon={<Inbox size={20} />} title={filter === "all" ? "No tickets yet" : "Nothing here"}>
              {filter === "all" ? "Create a ticket to watch the agents work on it." : "No ticket matches this filter."}
            </Empty>
          )}
          {shown.map((t) => (
            <Row key={t.id} ticket={t} active={t.id === activeId} />
          ))}
        </div>
      </section>
      <div className="pane-main">{children}</div>
    </div>
  );
}
