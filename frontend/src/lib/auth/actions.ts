"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE, getToken } from "./session";

const EEP_URL = process.env.NEXT_PUBLIC_EEP_URL ?? "";
const MAX_AGE = 60 * 60 * 8; // 8h, matches the EEP token TTL

/** Real login: verify credentials at the EEP, store the JWT + profile in an
 * httpOnly cookie. The token never reaches browser JS. */
export async function login(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) redirect("/login?error=invalid");

  let token: string | undefined;
  let user: unknown;
  try {
    const res = await fetch(`${EEP_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
    if (!res.ok) redirect("/login?error=invalid");
    ({ token, user } = await res.json());
  } catch (err) {
    // Re-throw Next's redirect; treat anything else as a backend-unreachable error.
    if (err && typeof err === "object" && "digest" in err) throw err;
    redirect("/login?error=unavailable");
  }
  if (!token || !user) redirect("/login?error=invalid");

  (await cookies()).set(SESSION_COOKIE, JSON.stringify({ token, user }), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: MAX_AGE,
  });
  redirect("/worklist");
}

export async function logout() {
  // Best-effort server notify (stateless JWT; ignore failures).
  const token = await getToken();
  if (token) {
    try {
      await fetch(`${EEP_URL}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
    } catch {
      /* ignore */
    }
  }
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}
