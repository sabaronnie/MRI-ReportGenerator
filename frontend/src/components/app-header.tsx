import Link from "next/link";
import { getSession } from "@/lib/auth/session";
import { ROLE_LABEL } from "@/lib/auth/users";
import { logout } from "@/lib/auth/actions";

function BrandMark() {
  return (
    <span className="grid h-8 w-8 place-items-center rounded-md bg-primary text-primary-foreground shadow-sm">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
        <rect x="4.5" y="1.5" width="7" height="2.6" rx="1.1" fill="currentColor" />
        <rect x="3.8" y="6.7" width="8.4" height="2.6" rx="1.1" fill="currentColor" />
        <rect x="4.5" y="11.9" width="7" height="2.6" rx="1.1" fill="currentColor" />
      </svg>
    </span>
  );
}

export async function AppHeader() {
  const session = await getSession();
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/worklist" className="flex items-center gap-2.5">
          <BrandMark />
          <span className="flex flex-col leading-none">
            <span className="font-serif text-[17px] font-semibold tracking-tight text-foreground">
              Cervical&nbsp;MRI
            </span>
            <span className="mt-0.5 text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Reporting
            </span>
          </span>
        </Link>
        {session ? (
          <div className="flex items-center gap-4 text-sm">
            {session.role === "admin" ? (
              <Link href="/admin" className="text-muted-foreground transition-colors hover:text-foreground">
                Admin
              </Link>
            ) : null}
            <span className="flex items-center gap-2.5">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-xs font-semibold text-accent-foreground ring-1 ring-inset ring-border">
                {session.name.slice(0, 1)}
              </span>
              <span className="hidden flex-col leading-tight sm:flex">
                <span className="font-medium text-foreground">{session.name}</span>
                <span className="text-[11px] text-muted-foreground">{ROLE_LABEL[session.role]}</span>
              </span>
            </span>
            <form action={logout}>
              <button
                type="submit"
                className="rounded-md border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                Sign out
              </button>
            </form>
          </div>
        ) : null}
      </div>
    </header>
  );
}
