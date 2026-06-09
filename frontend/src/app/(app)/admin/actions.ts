"use server";

import { revalidatePath } from "next/cache";
import { requireRole } from "@/lib/auth/session";
import * as admin from "@/lib/api/admin";
import type { Role } from "@/lib/api/contract";
import { ROLES } from "@/lib/auth/users";

type ActionResult = { ok: boolean; error?: string };

function parseRole(value: unknown): Role | null {
  return typeof value === "string" && (ROLES as string[]).includes(value) ? (value as Role) : null;
}

export async function createUserAction(formData: FormData): Promise<ActionResult> {
  await requireRole(["admin"]);
  const email = String(formData.get("email") ?? "").trim();
  const name = String(formData.get("name") ?? "").trim();
  const role = parseRole(formData.get("role"));
  const password = String(formData.get("password") ?? "");
  if (!email || !name || !role) return { ok: false, error: "Email, name and role are required." };
  if (password.length < 8) return { ok: false, error: "Password must be at least 8 characters." };

  const res = await admin.createUser({ email, name, role, password });
  if (!res.ok) return { ok: false, error: res.error };
  revalidatePath("/admin");
  return { ok: true };
}

export async function setRoleAction(id: string, role: Role): Promise<ActionResult> {
  await requireRole(["admin"]);
  const res = await admin.updateUser(id, { role });
  if (!res.ok) return { ok: false, error: res.error };
  revalidatePath("/admin");
  return { ok: true };
}

export async function setActiveAction(id: string, active: boolean): Promise<ActionResult> {
  await requireRole(["admin"]);
  const res = await admin.updateUser(id, { active });
  if (!res.ok) return { ok: false, error: res.error };
  revalidatePath("/admin");
  return { ok: true };
}

export async function resetPasswordAction(id: string, password: string): Promise<ActionResult> {
  await requireRole(["admin"]);
  if (password.length < 8) return { ok: false, error: "Password must be at least 8 characters." };
  const res = await admin.resetPassword(id, password);
  if (!res.ok) return { ok: false, error: res.error };
  return { ok: true };
}

export async function deleteUserAction(id: string): Promise<ActionResult> {
  await requireRole(["admin"]);
  const res = await admin.deleteUser(id);
  if (!res.ok) return { ok: false, error: res.error };
  revalidatePath("/admin");
  return { ok: true };
}
