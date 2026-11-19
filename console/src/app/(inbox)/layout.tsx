import { InboxShell } from "@/components/InboxShell";

export default function InboxLayout({ children }: { children: React.ReactNode }) {
  return <InboxShell>{children}</InboxShell>;
}
