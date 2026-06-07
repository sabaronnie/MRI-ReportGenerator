import { login } from "@/lib/auth/actions";
import { DEMO_USERS, ROLE_LABEL } from "@/lib/auth/users";
import { Reveal, Stagger, StaggerItem } from "@/components/motion/reveal";

export const metadata = { title: "Sign in · Cervical MRI" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  return (
    <div className="mx-auto flex min-h-[78vh] max-w-md flex-col justify-center px-6">
      <Reveal className="mb-8 text-center">
        <span className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <svg width="24" height="24" viewBox="0 0 16 16" fill="none" aria-hidden>
            <line x1="8" y1="2" x2="8" y2="14" stroke="currentColor" strokeWidth="0.9" opacity="0.45" />
            <ellipse cx="8" cy="3" rx="3" ry="1.35" fill="currentColor" />
            <ellipse cx="8" cy="6.4" rx="3.5" ry="1.45" fill="currentColor" />
            <ellipse cx="8" cy="9.8" rx="3.5" ry="1.45" fill="currentColor" />
            <ellipse cx="8" cy="13" rx="3" ry="1.35" fill="currentColor" />
          </svg>
        </span>
        <h1 className="font-serif text-3xl font-semibold tracking-tight">Cervical MRI Reporting</h1>
        <p className="mt-2 text-sm text-muted-foreground">Demo accounts — choose a role to continue.</p>
        {error ? <p className="mt-2 text-sm text-rose-600">Unknown user.</p> : null}
      </Reveal>
      <Stagger className="space-y-2.5">
        {DEMO_USERS.map((u) => (
          <StaggerItem key={u.email}>
            <form action={login}>
              <input type="hidden" name="email" value={u.email} />
              <button
                type="submit"
                className="group flex w-full items-center justify-between rounded-xl border border-border bg-card px-4 py-3.5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md active:translate-y-0"
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
          </StaggerItem>
        ))}
      </Stagger>
    </div>
  );
}
