"use client";

import { Gauge, Hand, Layers, Route, Scale, SearchCheck, Wallet, Zap } from "lucide-react";
import { useComposer } from "@/components/Composer";
import { Skeleton } from "@/components/ui";
import { api, type Ticket } from "@/lib/api";
import { usePolling } from "@/lib/hooks";
import { money, outcomeOf } from "@/lib/present";

type Bucket = { label: string; color: string; count: number };

function buckets(tickets: Ticket[]): Bucket[] {
  const count = (pick: (t: Ticket) => boolean): number => tickets.filter(pick).length;
  const tone = (t: Ticket): string => outcomeOf(t).tone;
  return [
    { label: "Resolved by the agents", color: "var(--ok)", count: count((t) => t.status === "resolved" && tone(t) !== "violet") },
    { label: "Awaiting approval", color: "var(--warn)", count: count((t) => t.status === "awaiting_approval") },
    { label: "Handed to a human", color: "var(--violet)", count: count((t) => t.status === "resolved" && tone(t) === "violet") },
    { label: "In progress", color: "var(--info)", count: count((t) => t.status === "queued" || t.status === "running") },
    { label: "Failed", color: "var(--bad)", count: count((t) => t.status === "failed") },
  ];
}

function Kpi({ icon, label, value, note }: { icon: React.ReactNode; label: string; value: string; note: string }) {
  return (
    <div className="card kpi">
      <div className="kpi-label">
        {icon}
        {label}
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-note">{note}</div>
    </div>
  );
}

const FLOW = [
  { icon: <Route size={18} />, title: "Route", text: "A small model sends the ticket to the billing, shipping or subscription team." },
  { icon: <SearchCheck size={18} />, title: "Investigate", text: "The specialist reads the customer's records and finds the policy in force on that day." },
  { icon: <Scale size={18} />, title: "Review", text: "A policy critic checks the plan. Only an approved plan is carried out." },
  { icon: <Hand size={18} />, title: "Decide", text: "Large refunds stop for a person. Suspicious tickets go to one too." },
];

export default function Overview() {
  const composer = useComposer();
  const tickets = usePolling(() => api.tickets(), 3000);
  const stats = usePolling(api.stats, 4000);
  const list = tickets.data;
  const parts = list ? buckets(list) : [];
  const done = list ? list.filter((t) => t.status !== "queued" && t.status !== "running").length : 0;
  const auto = parts[0]?.count ?? 0;
  const humans = (parts[1]?.count ?? 0) + (parts[2]?.count ?? 0);
  const threshold = stats.data ? money(stats.data.approval_threshold_cents) : null;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>How the agents are doing</h1>
        </div>
        <button type="button" className="btn primary" onClick={() => composer.open()}>
          Try a ticket
        </button>
      </div>

      <section className="kpis" aria-label="Key numbers">
        <Kpi icon={<Layers size={15} />} label="Tickets handled" value={list ? String(list.length) : "-"} note={list ? `${done} finished` : " "} />
        <Kpi
          icon={<Zap size={15} />}
          label="Auto-resolved"
          value={list && done ? `${Math.round((auto / done) * 100)}%` : "-"}
          note={list ? `${auto} of ${done} finished` : " "}
        />
        <Kpi icon={<Hand size={15} />} label="Needed a person" value={list ? String(humans) : "-"} note="approvals and handovers" />
        <Kpi
          icon={<Wallet size={15} />}
          label="Cost per ticket"
          value={stats.data && stats.data.tickets ? `$${stats.data.mean_cost_usd.toFixed(4)}` : "-"}
          note={stats.data && stats.data.tickets ? `${stats.data.mean_latency_s.toFixed(1)} s on average` : " "}
        />
      </section>

      <section className="card card-pad" aria-label="Outcomes">
        <h2>Outcomes</h2>
        {!list && <Skeleton height={10} />}
        {list && !list.length && <p className="muted">No tickets yet. Send one to see the outcomes fill in.</p>}
        {list && list.length > 0 && (
          <>
            <div className="bar" role="img" aria-label="Share of tickets by outcome">
              {parts
                .filter((p) => p.count)
                .map((p) => (
                  <span key={p.label} style={{ flex: p.count, background: p.color }} />
                ))}
            </div>
            <div className="legend">
              {parts
                .filter((p) => p.count)
                .map((p) => (
                  <span key={p.label}>
                    <i style={{ background: p.color }} />
                    {p.label} <strong>{p.count}</strong>
                  </span>
                ))}
            </div>
          </>
        )}
      </section>

      <section className="card card-pad" aria-label="How a ticket is handled">
        <h2>
          <Gauge size={14} style={{ verticalAlign: "-2px", marginRight: 6 }} />
          How a ticket is handled
        </h2>
        <div className="flow">
          {FLOW.map((step) => (
            <div key={step.title} className="flow-step">
              <span className="flow-icon">{step.icon}</span>
              <strong>{step.title}</strong>
              <span className="muted small">{step.text}</span>
            </div>
          ))}
        </div>
        {threshold && (
          <p className="muted small" style={{ marginTop: 16 }}>
            Refunds above {threshold} always wait for a person.
          </p>
        )}
      </section>
    </div>
  );
}
