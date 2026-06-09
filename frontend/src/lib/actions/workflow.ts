"use server";

import { revalidatePath } from "next/cache";
import { getToken, requireSession } from "@/lib/auth/session";
import { WORKFLOW_LIVE } from "@/lib/api/workflow";

const EEP_URL = process.env.NEXT_PUBLIC_EEP_URL ?? "";
type Result = { ok: boolean; error?: string };

async function post(path: string, body?: unknown): Promise<Result> {
  if (!WORKFLOW_LIVE) return { ok: false, error: "Workflow actions require live mode." };
  const token = await getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (body) headers.set("Content-Type", "application/json");
  const res = await fetch(`${EEP_URL}${path}`, {
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (res.ok) return { ok: true };
  let error = `request failed (${res.status})`;
  try {
    const b = await res.json();
    if (typeof b?.detail === "string") error = b.detail;
  } catch {
    /* ignore */
  }
  return { ok: false, error };
}

function refresh(id: string) {
  revalidatePath("/worklist");
  revalidatePath(`/cases/${id}`);
}

export async function claimAction(id: string): Promise<Result> {
  await requireSession();
  const r = await post(`/workflow/cases/${encodeURIComponent(id)}/claim`);
  if (r.ok) refresh(id);
  return r;
}

export async function releaseAction(id: string): Promise<Result> {
  await requireSession();
  const r = await post(`/workflow/cases/${encodeURIComponent(id)}/release`);
  if (r.ok) refresh(id);
  return r;
}

export async function assignAction(id: string, assigneeId: string): Promise<Result> {
  await requireSession();
  const r = await post(`/workflow/cases/${encodeURIComponent(id)}/assign`, { assignee_id: assigneeId });
  if (r.ok) refresh(id);
  return r;
}

export async function addAddendumAction(id: string, text: string): Promise<Result> {
  await requireSession();
  if (!text.trim()) return { ok: false, error: "Addendum text is required." };
  const r = await post(`/workflow/cases/${encodeURIComponent(id)}/addendum`, { text });
  if (r.ok) revalidatePath(`/cases/${id}`);
  return r;
}
