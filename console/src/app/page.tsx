"use client";

import { NewTicketForm } from "@/components/NewTicketForm";
import { TicketList } from "@/components/TicketList";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { seconds, usd } from "@/lib/format";

export default function Home() {
  const stats = usePolling(api.stats, 4000);
  const tickets = usePolling(() => api.tickets(), 3000);
  const s = stats.data;
  return (
    <div className="grid">
      <section aria-label="Overview" className="stats">
        <Stat label="Tickets" value={s ? String(s.tickets) : "-"} />
        <Stat label="Awaiting approval" value={s ? String(s.by_status.awaiting_approval ?? 0) : "-"} />
        <Stat label="Cost per ticket" value={s ? usd(s.mean_cost_usd) : "-"} />
        <Stat label="Mean time" value={s ? seconds(s.mean_latency_s) : "-"} />
      </section>
      {tickets.error && <p className="error" role="alert">{tickets.error}</p>}
      <section aria-label="Tickets">
        <h2>Recent tickets</h2>
        {tickets.data ? <TicketList tickets={tickets.data} /> : <p className="muted">Loading...</p>}
      </section>
      <aside>
        <NewTicketForm />
      </aside>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="muted small">{label}</div>
    </div>
  );
}
