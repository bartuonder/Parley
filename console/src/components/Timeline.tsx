import type { TicketEvent } from "@/lib/api";

function describe(event: TicketEvent): string {
  const d = event.data;
  switch (event.kind) {
    case "queued":
      return "Ticket received";
    case "status":
      return `Status: ${String(d.status)}`;
    case "node": {
      const node = String(d.node);
      if (node === "triage") return `Routed to the ${String(d.specialist)} specialist`;
      if (node === "investigate") {
        const tools = (d.tools as string[] | undefined) ?? [];
        return `Investigated with ${tools.length} tool call${tools.length === 1 ? "" : "s"}${tools.length ? ` (${tools.join(", ")})` : ""}`;
      }
      if (node === "critic") {
        const issues = (d.issues as string[] | undefined) ?? [];
        return d.approved ? "Policy critic approved the plan" : `Policy critic sent it back: ${issues[0] ?? "see trace"}`;
      }
      if (node === "execute") {
        const actions = (d.actions as string[] | undefined) ?? [];
        return actions.length ? `Executed ${actions.join(", ")}` : "Nothing to execute";
      }
      if (node === "respond") return "Reply written";
      if (node === "remember") return "Customer memory updated";
      if (node === "approval") return "Human decision applied";
      return `Step: ${node}`;
    }
    case "reply":
      return "Reply ready";
    case "decision":
      return "Human decision received";
    case "resolved":
      return "Resolved";
    case "failed":
      return `Failed: ${String(d.error)}`;
    default:
      return event.kind;
  }
}

export function Timeline({ events, live }: { events: TicketEvent[]; live: boolean }) {
  return (
    <ol className="timeline" aria-live="polite">
      {events
        .filter((e) => !(e.kind === "status" && e.data.status === "running"))
        .map((event) => (
          <li key={event.id} className={`tl-${event.kind}`}>
            <span className="dot" aria-hidden="true" />
            <span>{describe(event)}</span>
          </li>
        ))}
      {live && (
        <li className="tl-live">
          <span className="dot pulse" aria-hidden="true" />
          <span>Working...</span>
        </li>
      )}
    </ol>
  );
}
