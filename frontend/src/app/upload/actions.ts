"use server";

import { redirect } from "next/navigation";
import { requireRole } from "@/lib/auth/session";
import { createCase } from "@/lib/api/client";

/** Upload a scan (radiologist / technologist / admin), create a case, go to its processing view. */
export async function uploadAction(formData: FormData) {
  const user = await requireRole(["radiologist", "technologist", "admin"]);
  const file = formData.get("file");
  const filename = file instanceof File && file.name ? file.name : "uploaded-study.nii.gz";
  const { case_id } = await createCase(filename, user.name);
  redirect(`/cases/${case_id}`);
}
