import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Role } from "@/lib/api/contract";
import type { SessionUser } from "./users";

export const SESSION_COOKIE = "cs_session";

/** Cookie payload: the EEP-issued JWT (for API calls) + the user profile (for UI). */
type SessionData = { token: string; user: SessionUser };

async function readSession(): Promise<SessionData | null> {
  const raw = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as SessionData;
    return data.token && data.user ? data : null;
  } catch {
    return null;
  }
}

/** Current user (null if signed out). The token role is advisory — the EEP
 * re-checks role/active from its DB on every request. */
export async function getSession(): Promise<SessionUser | null> {
  return (await readSession())?.user ?? null;
}

/** The JWT to forward to the EEP as a Bearer token. */
export async function getToken(): Promise<string | null> {
  return (await readSession())?.token ?? null;
}

/** Guard: require any signed-in user, else redirect to /login. */
export async function requireSession(): Promise<SessionUser> {
  const s = await getSession();
  if (!s) redirect("/login");
  return s;
}

/** Guard: require one of `roles`, else bounce to the worklist. */
export async function requireRole(roles: Role[]): Promise<SessionUser> {
  const s = await requireSession();
  if (!roles.includes(s.role)) redirect("/worklist");
  return s;
}
