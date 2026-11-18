"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { TicketEvent } from "./api";

type Polled<T> = { data: T | null; error: string | null; refresh: () => void };

export function usePolling<T>(load: () => Promise<T>, intervalMs: number): Polled<T> {
  const [state, setState] = useState<{ data: T | null; error: string | null }>({
    data: null,
    error: null,
  });
  const [version, setVersion] = useState(0);
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });
  useEffect(() => {
    let alive = true;
    const tick = async (): Promise<void> => {
      try {
        const data = await loader.current();
        if (alive) setState({ data, error: null });
      } catch (error) {
        if (alive) setState((s) => ({ ...s, error: error instanceof Error ? error.message : "error" }));
      }
    };
    void tick();
    if (intervalMs <= 0) return () => void (alive = false);
    const timer = setInterval(() => void tick(), intervalMs);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [intervalMs, version]);
  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, refresh };
}

const KINDS = ["queued", "status", "node", "reply", "decision", "resolved", "failed"];

export function useTicketEvents(id: string, restartKey: string): { events: TicketEvent[]; live: boolean } {
  const [events, setEvents] = useState<TicketEvent[]>([]);
  const [live, setLive] = useState(true);
  useEffect(() => {
    const source = new EventSource(`/api/tickets/${encodeURIComponent(id)}/events`);
    const add = (message: MessageEvent<string>): void => {
      const event = JSON.parse(message.data) as TicketEvent;
      setLive(true);
      setEvents((prev) => (prev.some((p) => p.id === event.id) ? prev : [...prev, event]));
    };
    for (const kind of KINDS) source.addEventListener(kind, add as EventListener);
    source.addEventListener("end", () => {
      source.close();
      setLive(false);
    });
    return () => source.close();
  }, [id, restartKey]);
  return { events, live };
}
