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

export function stamp(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`;
}
