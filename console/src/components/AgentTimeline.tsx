import { Check, Hand, LoaderCircle, TriangleAlert } from "lucide-react";
import type { TicketEvent } from "@/lib/api";
import { stepsFromEvents, type Step } from "@/lib/present";

function StepIcon({ step }: { step: Step }) {
  if (step.tone === "ok") return <Check size={13} strokeWidth={3} />;
  if (step.tone === "warn" || step.tone === "bad") return <TriangleAlert size={12} />;
  if (step.tone === "violet") return <Hand size={12} />;
  return <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />;
}

export function AgentTimeline({ events, live }: { events: TicketEvent[]; live: boolean }) {
  const steps = stepsFromEvents(events);
  return (
    <ol className="timeline" aria-live="polite" aria-label="What the agents did">
      {steps.map((step) => (
        <li key={step.key} className={`step s-${step.tone}`}>
          <span className="step-dot">
            <StepIcon step={step} />
          </span>
          <div>
            <div className="step-title">{step.title}</div>
            {step.items && step.items.length > 0 && (
              <ul className="step-items">
                {step.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
            {step.note && <p className="step-note">{step.note}</p>}
          </div>
        </li>
      ))}
      {live && (
        <li className="step working">
          <span className="step-dot">
            <LoaderCircle size={13} className="spin" />
          </span>
          <div className="step-title muted">Working on it...</div>
        </li>
      )}
    </ol>
  );
}
