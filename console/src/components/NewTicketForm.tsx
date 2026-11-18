"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";

export function NewTicketForm() {
  const router = useRouter();
  const [email, setEmail] = useState("lukas.torvalds.1@example.com");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ticket = await api.create({ sender_email: email, subject, body });
      router.push(`/tickets/${ticket.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "could not send the ticket");
      setBusy(false);
    }
  }

  return (
    <form className="card form" onSubmit={(e) => void submit(e)}>
      <h2>New ticket</h2>
      <label>
        Customer email
        <input value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label>
        Subject
        <input value={subject} onChange={(e) => setSubject(e.target.value)} required maxLength={300} />
      </label>
      <label>
        Message
        <textarea value={body} onChange={(e) => setBody(e.target.value)} required rows={4} maxLength={8000} />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="submit" disabled={busy}>
        {busy ? "Sending..." : "Send to the agents"}
      </button>
    </form>
  );
}
