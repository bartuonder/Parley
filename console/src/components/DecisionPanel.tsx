"use client";

import { Check, X } from "lucide-react";
import { useState } from "react";
import { api, type Ticket } from "@/lib/api";
import { money, orderRef } from "@/lib/present";

export function DecisionPanel({ ticket, onDone }: { ticket: Ticket; onDone: () => void }) {
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
      setError(e instanceof Error ? e.message : "The decision could not be applied");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {ticket.pending.map((refund) => {
        const key = String(refund.refund_id);
        return (
          <div key={key} className="decision-row">
            <span>
              Refund <strong>{money(refund.amount_cents)}</strong> on {orderRef(refund.target)}
            </span>
            <span className="decision-actions" role="group" aria-label={`Decision for ${orderRef(refund.target)}`}>
              <button
                type="button"
                className="btn choice yes"
                aria-pressed={choice[key] === true}
                onClick={() => setChoice({ ...choice, [key]: true })}
              >
                <Check size={15} />
                Approve
              </button>
              <button
                type="button"
                className="btn choice no"
                aria-pressed={choice[key] === false}
                onClick={() => setChoice({ ...choice, [key]: false })}
              >
                <X size={15} />
                Decline
              </button>
            </span>
          </div>
        );
      })}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="button" className="btn primary block" disabled={!complete || busy} onClick={() => void submit()}>
        {busy ? "Applying..." : "Confirm decision"}
      </button>
    </div>
  );
}
