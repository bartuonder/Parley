"use client";

import Link from "next/link";
import type { Ticket } from "@/lib/api";
import { seconds, stamp, usd } from "@/lib/format";
import { StatusBadge } from "./StatusBadge";

export function TicketList({ tickets }: { tickets: Ticket[] }) {
  if (!tickets.length) return <p className="muted">No tickets yet.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ticket</th>
            <th>Status</th>
            <th>Specialist</th>
            <th className="num">Cost</th>
            <th className="num">Time</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((t) => (
            <tr key={t.id}>
              <td>
                <Link href={`/tickets/${t.id}`}>{t.subject}</Link>
                <div className="muted small">{t.sender_email}</div>
              </td>
              <td>
                <StatusBadge status={t.status} />
              </td>
              <td>{t.specialist ?? "-"}</td>
              <td className="num">{t.cost_usd ? usd(t.cost_usd) : "-"}</td>
              <td className="num">{t.latency_s ? seconds(t.latency_s) : "-"}</td>
              <td className="small">{stamp(t.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
