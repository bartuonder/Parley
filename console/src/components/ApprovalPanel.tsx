"use client";

import { useState } from "react";
import { api, type Ticket } from "@/lib/api";
import { money } from "@/lib/format";

export function ApprovalPanel({ ticket, onDone }: { ticket: Ticket; onDone: () => void }) {
  const [choice, setChoice] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const complete = ticket.pending.every((p) => String(p.refund_id) in choice);

  async function submit(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await api.decide(ticket.id, choice);
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "decision failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="approval">
      {ticket.pending.map((refund) => {
        const key = String(refund.refund_id);
        return (
          <div key={key} className="approval-row">
            <span>
              Refund <strong>{money(refund.amount_cents)}</strong> on {refund.target}
            </span>
            <span className="segmented" role="group" aria-label={`Decision for refund ${key}`}>
              <button
                type="button"
                aria-pressed={choice[key] === true}
                className={choice[key] === true ? "on approve" : ""}
                onClick={() => setChoice({ ...choice, [key]: true })}
              >
                Approve
              </button>
              <button
                type="button"
                aria-pressed={choice[key] === false}
                className={choice[key] === false ? "on decline" : ""}
                onClick={() => setChoice({ ...choice, [key]: false })}
              >
                Decline
              </button>
            </span>
          </div>
        );
      })}
      {error && <p className="error" role="alert">{error}</p>}
      <button type="button" disabled={!complete || busy} onClick={() => void submit()}>
        {busy ? "Applying..." : "Submit decision"}
      </button>
    </div>
  );
}
