import { getToken } from "@/lib/auth/session";
import type { ManagedUser } from "@/lib/auth/users";
import type { Role } from "@/lib/api/contract";

const EEP_URL = process.env.NEXT_PUBLIC_EEP_URL ?? "";

async function authed(path: string, init?: RequestInit): Promise<Response> {
  const token = await getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body) headers.set("Content-Type", "application/json");
  return fetch(`${EEP_URL}${path}`, { ...init, headers, cache: "no-store" });
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === "string" ? body.detail : `request failed (${res.status})`;
  } catch {
    return `request failed (${res.status})`;
  }
}

export type Result = { ok: true } | { ok: false; error: string };

export async function listUsers(): Promise<ManagedUser[]> {
  const res = await authed("/auth/users");
  if (!res.ok) throw new Error(`GET /auth/users → ${res.status}`);
  return res.json();
}

export async function createUser(input: {
  email: string;
  name: string;
  role: Role;
  password: string;
}): Promise<Result> {
  const res = await authed("/auth/users", { method: "POST", body: JSON.stringify(input) });
  return res.ok ? { ok: true } : { ok: false, error: await errorDetail(res) };
}

export async function updateUser(
  id: string,
  patch: { role?: Role; active?: boolean },
): Promise<Result> {
  const res = await authed(`/auth/users/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return res.ok ? { ok: true } : { ok: false, error: await errorDetail(res) };
}

export async function resetPassword(id: string, password: string): Promise<Result> {
  const res = await authed(`/auth/users/${encodeURIComponent(id)}/password`, {
    method: "POST",
    body: JSON.stringify({ password }),
  });
  return res.ok ? { ok: true } : { ok: false, error: await errorDetail(res) };
}

export async function deleteUser(id: string): Promise<Result> {
  const res = await authed(`/auth/users/${encodeURIComponent(id)}`, { method: "DELETE" });
  return res.ok ? { ok: true } : { ok: false, error: await errorDetail(res) };
}
