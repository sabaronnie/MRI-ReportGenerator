"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "./session";
import { findUser } from "./users";

/**
 * Mock login (frontend-only, "as if auth is done"): set the session cookie.
 * A known demo email still selects that role; any other email signs in as the
 * primary radiologist persona so the demo flow always works. Real auth will be
 * wired into the EEP later.
 */
export async function login(formData: FormData) {
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  const user = findUser(email) ?? findUser("radiologist@demo")!;
  (await cookies()).set(SESSION_COOKIE, JSON.stringify(user), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });
  redirect("/worklist");
}

export async function logout() {
  (await cookies()).delete(SESSION_COOKIE);
  redirect("/login");
}
