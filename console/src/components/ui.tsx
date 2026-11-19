import { Bot } from "lucide-react";
import { avatarHue, initials, type Outcome } from "@/lib/present";

export function Avatar({ name, small = false }: { name: string; small?: boolean }) {
  const hue = avatarHue(name);
  return (
    <span
      className={`avatar${small ? " sm" : ""}`}
      style={{ background: `hsl(${hue} 80% 91%)`, color: `hsl(${hue} 55% 28%)` }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}

export function AgentAvatar({ small = false }: { small?: boolean }) {
  return (
    <span className={`avatar agent${small ? " sm" : ""}`} aria-hidden="true">
      <Bot size={small ? 15 : 18} />
    </span>
  );
}

export function OutcomeChip({ outcome }: { outcome: Outcome }) {
  return (
    <span className={`chip tone-${outcome.tone}${outcome.tone === "info" ? " pulse" : ""}`}>
      {outcome.label}
      {outcome.detail && <span className="detail">{outcome.detail}</span>}
    </span>
  );
}

export function Skeleton({ width = "100%", height = 14 }: { width?: string | number; height?: number }) {
  return <div className="skeleton" style={{ width, height }} aria-hidden="true" />;
}

export function Empty({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <span className="flow-icon">{icon}</span>
      <strong>{title}</strong>
      {children && <p className="muted">{children}</p>}
    </div>
  );
}
