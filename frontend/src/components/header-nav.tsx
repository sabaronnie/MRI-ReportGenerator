"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { logout } from "@/lib/auth/actions";
import { ROLE_LABEL } from "@/lib/auth/users";
import type { Role } from "@/lib/api/contract";

type NavItem = { href: string; label: string };
type Props = { user: { name: string; role: Role } | null; items: NavItem[] };

function SpineMark() {
  // Vertical spinal column (discs + column line) — intentionally NOT three horizontal bars.
  return (
    <span className="grid h-8 w-8 place-items-center rounded-md bg-primary text-primary-foreground shadow-sm">
      <svg width="17" height="17" viewBox="0 0 16 16" fill="none" aria-hidden>
        <line x1="8" y1="2" x2="8" y2="14" stroke="currentColor" strokeWidth="0.9" opacity="0.45" />
        <ellipse cx="8" cy="3" rx="3" ry="1.35" fill="currentColor" />
        <ellipse cx="8" cy="6.4" rx="3.5" ry="1.45" fill="currentColor" />
        <ellipse cx="8" cy="9.8" rx="3.5" ry="1.45" fill="currentColor" />
        <ellipse cx="8" cy="13" rx="3" ry="1.35" fill="currentColor" />
      </svg>
    </span>
  );
}

export function HeaderNav({ user, items }: Props) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/worklist"
      ? pathname.startsWith("/worklist") || pathname.startsWith("/cases")
      : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/worklist" className="flex items-center gap-2.5">
          <SpineMark />
          <span className="flex flex-col leading-none">
            <span className="font-serif text-[17px] font-semibold tracking-tight text-foreground">
              Cervical&nbsp;MRI
            </span>
            <span className="mt-0.5 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Reporting
            </span>
          </span>
        </Link>

        {user ? (
          <>
            <nav className="hidden items-center gap-1 md:flex">
              {items.map((it) => (
                <Link
                  key={it.href}
                  href={it.href}
                  className={`relative rounded-md px-3 py-1.5 text-sm ${
                    isActive(it.href) ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {it.label}
                  {isActive(it.href) ? (
                    <motion.span
                      layoutId="nav-underline"
                      className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-primary"
                      transition={{ type: "spring", stiffness: 380, damping: 30 }}
                    />
                  ) : null}
                </Link>
              ))}
            </nav>

            <div className="hidden items-center gap-3 md:flex">
              <span className="flex items-center gap-2.5">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground ring-1 ring-inset ring-border">
                  {user.name.slice(0, 1)}
                </span>
                <span className="flex flex-col leading-tight">
                  <span className="text-sm font-medium text-foreground">{user.name}</span>
                  <span className="text-[11px] text-muted-foreground">{ROLE_LABEL[user.role]}</span>
                </span>
              </span>
              <form action={logout}>
                <button
                  type="submit"
                  className="rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  Sign out
                </button>
              </form>
            </div>

            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-label="Toggle menu"
              aria-expanded={open}
              className="grid h-9 w-9 place-items-center rounded-md border border-border text-foreground hover:bg-muted md:hidden"
            >
              <motion.svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                animate={{ rotate: open ? 90 : 0 }}
                transition={{ duration: 0.2 }}
                aria-hidden
              >
                {open ? <path d="M18 6 6 18M6 6l12 12" /> : <path d="M3 6h18M3 12h18M3 18h18" />}
              </motion.svg>
            </button>
          </>
        ) : null}
      </div>

      <AnimatePresence>
        {open && user ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden border-t border-border md:hidden"
          >
            <nav className="mx-auto flex max-w-6xl flex-col gap-1 px-6 py-3">
              {items.map((it) => (
                <Link
                  key={it.href}
                  href={it.href}
                  onClick={() => setOpen(false)}
                  className={`rounded-md px-3 py-2 text-sm ${
                    isActive(it.href)
                      ? "bg-accent font-medium text-accent-foreground"
                      : "text-muted-foreground hover:bg-muted"
                  }`}
                >
                  {it.label}
                </Link>
              ))}
              <div className="mt-2 flex items-center justify-between border-t border-border pt-3">
                <span className="flex items-center gap-2">
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                    {user.name.slice(0, 1)}
                  </span>
                  <span className="flex flex-col leading-tight">
                    <span className="text-sm font-medium">{user.name}</span>
                    <span className="text-[11px] text-muted-foreground">{ROLE_LABEL[user.role]}</span>
                  </span>
                </span>
                <form action={logout}>
                  <button
                    type="submit"
                    className="rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted"
                  >
                    Sign out
                  </button>
                </form>
              </div>
            </nav>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </header>
  );
}
