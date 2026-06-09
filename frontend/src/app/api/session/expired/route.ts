import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth/session";

/** Clears the session cookie then sends the user to login. Used when the EEP
 * rejects the token (401) so a stale cookie can't cause a login↔worklist loop. */
export async function GET(req: Request) {
  (await cookies()).delete(SESSION_COOKIE);
  return NextResponse.redirect(new URL("/login?error=expired", req.url));
}
