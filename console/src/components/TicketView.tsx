"use client";

import { ArrowLeft, CircleCheck, FileText, Hand, ShieldAlert, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { DecisionPanel } from "@/components/DecisionPanel";
import { AgentTimeline } from "@/components/AgentTimeline";
import { TraceView } from "@/components/TraceView";
import { AgentAvatar, Avatar, OutcomeChip, Skeleton } from "@/components/ui";
import { api, type Ticket } from "@/lib/api";
import { usePolling, useTicketEvents } from "@/lib/hooks";
import { displayName, formatWhen, money, orderRef, outcomeOf, SPECIALIST_LABEL } from "@/lib/present";

type Tab = "overview" | "trace";

const shorten = (text: string, max: number): string => (text.length > max ? `${text.slice(0, max - 3).trimEnd()}...` : text);

function Resolution({ ticket }: { ticket: Ticket }) {
  const outcome = outcomeOf(ticket);
  const refund = (ticket.result.actions ?? []).find((a) => a.name === "issue_refund" && a.ok);
  const handover = (ticket.result.escalations ?? [])[0];
  if (outcome.tone === "info") return null;
  let icon = <CircleCheck size={18} />;
  let title = outcome.label;
  let text = "";
  if (outcome.label === "Refund issued" && refund) {
    title = `Refund of ${outcome.detail} issued`;
    text = `${orderRef(`${refund.arguments.target} ${refund.arguments.target_id}`)}. The customer has the answer above.`;
  } else if (outcome.label === "Awaiting approval") {
    icon = <Hand size={18} />;
    title = `Waiting for a person to approve ${outcome.detail}`;
    text = "This refund is above the approval threshold. Nothing is paid out until someone decides.";
  } else if (outcome.label === "Handed to a human") {
    icon = <Hand size={18} />;
    title = "Handed to a human";
    text = handover ? shorten(handover.summary, 200) : "A person will follow up with the customer.";
  } else if (outcome.label === "Cancellation scheduled") {
    text = "The plan stays active until the end of the paid period.";
  } else if (outcome.tone === "bad") {
    icon = <TriangleAlert size={18} />;
    title = "The agents could not finish this ticket";
    text = "Nothing was changed on the customer's account. You can send the ticket again.";
  } else {
    title = "Answered";
    text = "No change to the customer's records was needed.";
  }
  return (
    <div className={`callout tone-${outcome.tone}`} role="status">
      {icon}
      <div>
        <strong>{title}</strong>
        {text && <p>{text}</p>}
      </div>
    </div>
  );
}

export function TicketView({ id }: { id: string }) {
  const ticket = usePolling(() => api.ticket(id), 2000);
  const t = ticket.data;
  const settled = t !== null && (t.status === "resolved" || t.status === "failed");
  const [tab, setTab] = useState<Tab>("overview");
  const trace = usePolling(
    () => (t?.trace_id && tab === "trace" ? api.trace(id) : Promise.resolve([])),
    settled ? 0 : 3000,
    tab,
  );
  const stream = useTicketEvents(id, t?.status ?? "");

  if (ticket.error && !t) {
    return (
      <div className="page">
        <p className="error" role="alert">
          {ticket.error}
        </p>
        <Link href="/" className="btn">
          <ArrowLeft size={15} />
          Back to the inbox
        </Link>
      </div>
    );
  }
  if (!t) {
    return (
      <div className="page" aria-busy="true">
        <Skeleton width="30%" height={14} />
        <Skeleton width="60%" height={28} />
        <Skeleton height={140} />
      </div>
    );
  }

  const name = displayName(t);
  const refresh = (): void => {
    ticket.refresh();
    trace.refresh();
  };
  const team = t.specialist ? (SPECIALIST_LABEL[t.specialist] ?? t.specialist) : null;
  const flagged = (t.result.guard_events ?? []).length > 0;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Ticket #{t.number}</p>
          <h1>{t.subject}</h1>
        </div>
        <OutcomeChip outcome={outcomeOf(t)} />
      </div>

      <div className="tabs-line" role="tablist" aria-label="Ticket views">
        <button type="button" role="tab" className="tab-line" aria-selected={tab === "overview"} onClick={() => setTab("overview")}>
          Overview
        </button>
        <button type="button" role="tab" className="tab-line" aria-selected={tab === "trace"} onClick={() => setTab("trace")}>
          Trace
        </button>
      </div>

      {tab === "trace" ? (
        <TraceView spans={trace.data ?? []} />
      ) : (
        <div className="detail-grid">
          <div className="thread">
            <div className="msg">
              <Avatar name={name} />
              <div>
                <div className="msg-head">
                  <strong>{name}</strong>
                  <span className="faint small">{formatWhen(t.created_at)}</span>
                </div>
                <div className="bubble">{t.body}</div>
              </div>
            </div>

            {t.reply && (
              <div className="msg">
                <AgentAvatar />
                <div>
                  <div className="msg-head">
                    <strong>Parley</strong>
                    <span className="faint small">Reply to the customer</span>
                  </div>
                  <div className="bubble agent">{t.reply}</div>
                </div>
              </div>
            )}
            {t.followup && (
              <div className="msg">
                <AgentAvatar />
                <div>
                  <div className="msg-head">
                    <strong>Parley</strong>
                    <span className="faint small">After the decision</span>
                  </div>
                  <div className="bubble agent">{t.followup}</div>
                </div>
              </div>
            )}

            {flagged && (
              <div className="callout tone-warn" role="note">
                <ShieldAlert size={18} />
                <div>
                  <strong>Safety check triggered</strong>
                  <p>
                    The message contained instructions aimed at the agents. It was treated as untrusted text, and
                    refunds and cancellations were locked for this ticket.
                  </p>
                </div>
              </div>
            )}

            <Resolution ticket={t} />

            {t.status === "awaiting_approval" && (
              <div className="card card-pad">
                <h2>Your decision</h2>
                <DecisionPanel ticket={t} onDone={refresh} />
              </div>
            )}
          </div>

          <aside className="aside" aria-label="Details">
            <section className="card card-pad">
              <h2>What the agents did</h2>
              <AgentTimeline events={stream.events} live={stream.live && !settled} />
            </section>

            {t.policies.length > 0 && (
              <section className="card card-pad">
                <h2>Policy applied</h2>
                {t.policies.map((p) => (
                  <div key={`${p.id}-${p.version}`} className="policy">
                    <FileText size={16} />
                    <div>
                      <strong>{p.title}</strong>
                      <span className="faint small">
                        {p.id}, version {p.version}
                      </span>
                    </div>
                  </div>
                ))}
              </section>
            )}

            <section className="card card-pad">
              <h2>Details</h2>
              <dl className="kv">
                <div>
                  <dt>Customer</dt>
                  <dd>{name}</dd>
                </div>
                {t.customer_name && (
                  <div>
                    <dt>Email</dt>
                    <dd>{t.sender_email}</dd>
                  </div>
                )}
                {team && (
                  <div>
                    <dt>Handled by</dt>
                    <dd>{team} team</dd>
                  </div>
                )}
                {t.latency_s > 0 && (
                  <div>
                    <dt>Time to reply</dt>
                    <dd>{t.latency_s.toFixed(1)} s</dd>
                  </div>
                )}
                {t.cost_usd > 0 && (
                  <div>
                    <dt>Model cost</dt>
                    <dd>${t.cost_usd.toFixed(4)}</dd>
                  </div>
                )}
                {t.pending.length > 0 && (
                  <div>
                    <dt>Amount at stake</dt>
                    <dd>{money(t.pending.reduce((n, p) => n + p.amount_cents, 0))}</dd>
                  </div>
                )}
              </dl>
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
