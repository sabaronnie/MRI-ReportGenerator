"use server";

import { revalidatePath } from "next/cache";
import { requireRole } from "@/lib/auth/session";
import { signOffCase } from "@/lib/api/client";

/** Radiologist-only: sign off a case's report. Guarded server-side. */
export async function signOffAction(formData: FormData) {
  const user = await requireRole(["radiologist"]);
  const id = String(formData.get("caseId") ?? "");
  if (!id) return;
  await signOffCase(id, user.name);
  revalidatePath(`/cases/${id}`);
}
