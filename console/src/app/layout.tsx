import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Parley console",
  description: "Tickets, live agent steps, traces and the approval queue for Parley.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            Parley
          </Link>
          <nav aria-label="Main">
            <Link href="/">Tickets</Link>
            <Link href="/approvals">Approvals</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
