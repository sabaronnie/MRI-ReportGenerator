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
    <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6">
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-1 text-sm text-muted-foreground">Demo accounts — pick a role to continue.</p>
      {error ? <p className="mt-2 text-sm text-red-600">Unknown user.</p> : null}
      <div className="mt-6 space-y-2">
        {DEMO_USERS.map((u) => (
          <form key={u.email} action={login}>
            <input type="hidden" name="email" value={u.email} />
            <button
              type="submit"
              className="flex w-full items-center justify-between rounded-md border px-4 py-3 text-left hover:bg-muted"
            >
              <span>
                <span className="block font-medium">{u.name}</span>
                <span className="block text-xs text-muted-foreground">{u.email}</span>
              </span>
              <span className="rounded bg-muted px-2 py-0.5 text-xs">{ROLE_LABEL[u.role]}</span>
            </button>
          </form>
        ))}
      </div>
    </div>
  );
}
