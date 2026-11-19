"use client";

import { Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type FormEvent } from "react";
import { api, type Customer } from "@/lib/api";
import { EXAMPLES, type Example } from "@/lib/present";

type ComposerApi = { open: (example?: Example) => void };

const ComposerContext = createContext<ComposerApi>({ open: () => undefined });

export const useComposer = (): ComposerApi => useContext(ComposerContext);

export function ComposerProvider({ children }: { children: React.ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [seed, setSeed] = useState<{ example?: Example; n: number }>({ n: 0 });
  const open = useCallback((example?: Example) => {
    setSeed((s) => ({ example, n: s.n + 1 }));
    dialog.current?.showModal();
  }, []);
  return (
    <ComposerContext.Provider value={{ open }}>
      {children}
      <dialog ref={dialog} className="modal" aria-labelledby="composer-title">
        <ComposerForm key={seed.n} seed={seed.example} onClose={() => dialog.current?.close()} />
      </dialog>
    </ComposerContext.Provider>
  );
}

function ComposerForm({ seed, onClose }: { seed?: Example; onClose: () => void }) {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [email, setEmail] = useState(seed?.email ?? "");
  const [subject, setSubject] = useState(seed?.subject ?? "");
  const [body, setBody] = useState(seed?.body ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .customers()
      .then((list) => {
        if (!alive) return;
        setCustomers(list);
        setEmail((current) => current || list[0]?.email || "");
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  const fill = (example: Example): void => {
    setEmail(example.email);
    setSubject(example.subject);
    setBody(example.body);
  };

  async function submit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const ticket = await api.create({ sender_email: email, subject, body });
      onClose();
      router.push(`/tickets/${ticket.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the ticket");
      setBusy(false);
    }
  }

  const known = customers.some((c) => c.email === email);

  return (
    <form className="modal-body" onSubmit={(e) => void submit(e)}>
      <div className="modal-head">
        <div>
          <h2 id="composer-title">New ticket</h2>
          <p className="muted">Write as a customer. The agents pick the ticket up right away.</p>
        </div>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
      </div>

      <div className="field">
        <span className="small faint">Try an example</span>
        <div className="examples">
          {EXAMPLES.map((example) => (
            <button type="button" key={example.label} className="example" onClick={() => fill(example)}>
              <strong>{example.label}</strong>
              <span>{example.hint}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <label htmlFor="composer-customer">Customer</label>
        <select id="composer-customer" value={email} onChange={(e) => setEmail(e.target.value)} required>
          {!known && email && <option value={email}>{email}</option>}
          {customers.map((c) => (
            <option key={c.email} value={c.email}>
              {c.name} ({c.email})
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="composer-subject">Subject</label>
        <input id="composer-subject" value={subject} onChange={(e) => setSubject(e.target.value)} required maxLength={300} />
      </div>
      <div className="field">
        <label htmlFor="composer-body">Message</label>
        <textarea id="composer-body" value={body} onChange={(e) => setBody(e.target.value)} required maxLength={8000} />
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="modal-foot">
        <button type="button" className="btn" onClick={onClose}>
          Cancel
        </button>
        <button type="submit" className="btn primary" disabled={busy}>
          <Send size={15} />
          {busy ? "Sending..." : "Send to the agents"}
        </button>
      </div>
    </form>
  );
}
