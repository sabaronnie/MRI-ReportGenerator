import { login } from "@/lib/auth/actions";
import { DEMO_USERS, ROLE_LABEL } from "@/lib/auth/users";

export const metadata = { title: "Sign in · Cervical MRI" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  return (
    <div className="mx-auto flex min-h-[78vh] max-w-md flex-col justify-center px-6">
      <div className="mb-8 text-center">
        <span className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <svg width="22" height="22" viewBox="0 0 16 16" fill="none" aria-hidden>
            <rect x="4.5" y="1.5" width="7" height="2.6" rx="1.1" fill="currentColor" />
            <rect x="3.8" y="6.7" width="8.4" height="2.6" rx="1.1" fill="currentColor" />
            <rect x="4.5" y="11.9" width="7" height="2.6" rx="1.1" fill="currentColor" />
          </svg>
        </span>
        <h1 className="font-serif text-3xl font-semibold tracking-tight">Cervical MRI Reporting</h1>
        <p className="mt-2 text-sm text-muted-foreground">Demo accounts — choose a role to continue.</p>
        {error ? <p className="mt-2 text-sm text-rose-600">Unknown user.</p> : null}
      </div>
      <div className="space-y-2.5">
        {DEMO_USERS.map((u) => (
          <form key={u.email} action={login}>
            <input type="hidden" name="email" value={u.email} />
            <button
              type="submit"
              className="group flex w-full items-center justify-between rounded-xl border border-border bg-card px-4 py-3.5 text-left shadow-sm transition-all hover:border-primary/40 hover:shadow-md"
            >
              <span className="flex items-center gap-3">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-accent text-sm font-semibold text-accent-foreground">
                  {u.name.slice(0, 1)}
                </span>
                <span>
                  <span className="block font-medium text-foreground">{u.name}</span>
                  <span className="block font-mono text-xs text-muted-foreground">{u.email}</span>
                </span>
              </span>
              <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground transition-colors group-hover:bg-accent group-hover:text-accent-foreground">
                {ROLE_LABEL[u.role]}
              </span>
            </button>
          </form>
        ))}
      </div>
    </div>
  );
}
