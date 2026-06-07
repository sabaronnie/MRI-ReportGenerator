"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { SESSION_COOKIE } from "./session";
import { findUser } from "./users";

/** Mock login: look up the demo user by email and set the session cookie. */
export async function login(formData: FormData) {
  const email = String(formData.get("email") ?? "");
  const user = findUser(email);
  if (!user) redirect("/login?error=unknown_user");
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
