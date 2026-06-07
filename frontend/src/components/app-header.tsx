import Link from "next/link";
import { getSession } from "@/lib/auth/session";
import { ROLE_LABEL } from "@/lib/auth/users";
import { logout } from "@/lib/auth/actions";

export async function AppHeader() {
  const session = await getSession();
  return (
    <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href="/worklist" className="flex items-center gap-2 font-semibold">
          <span className="inline-block h-5 w-5 rounded bg-foreground" aria-hidden />
          Cervical&nbsp;MRI
          <span className="font-normal text-muted-foreground">· Worklist</span>
        </Link>
        {session ? (
          <div className="flex items-center gap-3 text-sm">
            {session.role === "admin" ? (
              <Link href="/admin" className="text-muted-foreground hover:underline">
                Admin
              </Link>
            ) : null}
            <span className="text-muted-foreground">
              {session.name} · {ROLE_LABEL[session.role]}
            </span>
            <form action={logout}>
              <button type="submit" className="rounded border px-2 py-1 text-xs hover:bg-muted">
                Sign out
              </button>
            </form>
          </div>
        ) : null}
      </div>
    </header>
  );
}
