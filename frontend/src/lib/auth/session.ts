import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Role } from "@/lib/api/contract";
import type { SessionUser } from "./users";

export const SESSION_COOKIE = "cs_session";

/** Read the current session from the cookie (null if signed out). Safe in server components. */
export async function getSession(): Promise<SessionUser | null> {
  const raw = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
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
