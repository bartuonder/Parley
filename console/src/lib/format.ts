import type { Status } from "./api";

export const money = (cents: number): string => `$${(cents / 100).toFixed(2)}`;

export const usd = (value: number): string =>
  value >= 0.01 ? `$${value.toFixed(3)}` : `$${value.toFixed(4)}`;

export const seconds = (value: number): string => `${value.toFixed(1)}s`;

export const STATUS_LABEL: Record<Status, string> = {
  queued: "Queued",
  running: "Running",
  awaiting_approval: "Awaiting approval",
  resolved: "Resolved",
  failed: "Failed",
};

export function ago(iso: string, now: Date = new Date()): string {
  const delta = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (delta < 60) return `${delta}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}
