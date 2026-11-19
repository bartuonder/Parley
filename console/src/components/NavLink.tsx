"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const path = usePathname();
  const active = href === "/" ? path === "/" || path.startsWith("/tickets") : path.startsWith(href);
  return (
    <Link href={href} className={active ? "nav-active" : undefined} aria-current={active ? "page" : undefined}>
      {children}
    </Link>
  );
}
