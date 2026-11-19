"use client";

import { Inbox, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ComposerProvider } from "@/components/Composer";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/hooks";

function NavItem({
  href,
  active,
  icon,
  children,
  count,
}: {
  href: string;
  active: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <Link href={href} aria-current={active ? "page" : undefined}>
      {icon}
      {children}
      {count ? <span className="count">{count}</span> : null}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const approvals = usePolling(api.approvals, 4000);
  const waiting = approvals.data?.length ?? 0;
  return (
    <ComposerProvider>
      <div className="shell">
        <aside className="sidebar">
          <Link href="/" className="brand" aria-label="Parley home">
            <span className="logo">P</span>
            <span>
              <div className="brand-name">Parley</div>
              <div className="brand-sub">Support operations</div>
            </span>
          </Link>
          <nav className="nav" aria-label="Main">
            <NavItem href="/" active={path === "/" || path.startsWith("/tickets")} icon={<Inbox size={17} />}>
              Inbox
            </NavItem>
            <NavItem href="/approvals" active={path.startsWith("/approvals")} icon={<ShieldCheck size={17} />} count={waiting}>
              Approvals
            </NavItem>
          </nav>
          <div className="side-foot">
            <strong>
              <span className="live-dot" aria-hidden="true" />
              Demo environment
            </strong>
            Synthetic customers and policies. Nothing here is real data.
          </div>
        </aside>
        <main className="main">{children}</main>
      </div>
    </ComposerProvider>
  );
}
