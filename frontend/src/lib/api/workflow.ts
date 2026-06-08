/**
 * Workflow data layer (radiologist features A–D): worklist enrichment + claim/assign
 * + addenda. LIVE mode hits the EEP /workflow/* API; MOCK mode synthesises the same
 * shapes locally (TAT computed client-side; assignment/addenda are live-only).
 */
import { redirect } from "next/navigation";
import { getToken } from "@/lib/auth/session";
import { listCases } from "@/lib/api/client";
import type { CaseSummary } from "./contract";

const MODE = process.env.NEXT_PUBLIC_API_MODE ?? "mock";
const EEP_URL = process.env.NEXT_PUBLIC_EEP_URL ?? "";
export const WORKFLOW_LIVE = MODE === "live" && !!EEP_URL;

const TAT_TARGET_HOURS = 24;

export type Assignment = { assignee_id: string; assignee_name: string; claimed_at: string };
export type TatStatus = "on_track" | "warning" | "breach" | "signed" | "unknown";
export type Tat = { age_hours: number | null; tat_status: TatStatus; target_hours: number };
export type Addendum = {
  id: string;
  case_id: string;
  author_id: string;
  author_name: string;
  text: string;
  created_at: string;
};
export type WorklistRow = CaseSummary & { assignment: Assignment | null; tat: Tat };
export type CaseWorkflow = { case_id: string; assignment: Assignment | null; tat: Tat; addenda: Addendum[] };

export type WorklistParams = {
  status?: string;
  triage?: string;
  mine?: boolean;
  assignee?: string;
  q?: string;
  sort?: string;
};

function jsTat(createdAt: string, status: string): Tat {
  const created = Date.parse(createdAt);
  const ageHours = Number.isNaN(created) ? null : Math.round(((Date.now() - created) / 3.6e6) * 10) / 10;
  let tat_status: TatStatus;
  if (status === "reviewed" || status === "signed") tat_status = "signed";
  else if (ageHours === null) tat_status = "unknown";
  else if (ageHours >= TAT_TARGET_HOURS) tat_status = "breach";
  else if (ageHours >= 0.75 * TAT_TARGET_HOURS) tat_status = "warning";
  else tat_status = "on_track";
  return { age_hours: ageHours, tat_status, target_hours: TAT_TARGET_HOURS };
}

async function authed<T>(path: string): Promise<T> {
  const token = await getToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${EEP_URL}${path}`, { headers, cache: "no-store" });
  if (res.status === 401) redirect("/api/session/expired");
  if (!res.ok) throw new Error(`EEP ${path} → ${res.status}`);
  return (await res.json()) as T;
}

const TRIAGE_RANK: Record<string, number> = { urgent: 0, review: 1, none: 2 };

export async function getWorklist(params: WorklistParams = {}): Promise<WorklistRow[]> {
  if (WORKFLOW_LIVE) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "" && v !== false) qs.set(k, String(v));
    }
    const query = qs.toString();
    return authed<WorklistRow[]>(`/workflow/worklist${query ? `?${query}` : ""}`);
  }
  // mock: enrich + filter + sort locally (assignment is live-only → null)
  let rows: WorklistRow[] = (await listCases()).map((c) => ({
    ...c,
    assignment: null,
    tat: jsTat(c.created_at, c.status),
  }));
  if (params.status) rows = rows.filter((r) => r.status === params.status);
  if (params.triage) rows = rows.filter((r) => r.triage_badge === params.triage);
  if (params.q) rows = rows.filter((r) => r.case_id.toLowerCase().includes(params.q!.toLowerCase()));
  if (params.sort === "oldest") rows.sort((a, b) => (a.created_at < b.created_at ? -1 : 1));
  else if (params.sort === "newest") rows.sort((a, b) => (a.created_at > b.created_at ? -1 : 1));
  else
    rows.sort((a, b) => {
      const t = (TRIAGE_RANK[a.triage_badge] ?? 3) - (TRIAGE_RANK[b.triage_badge] ?? 3);
      return t !== 0 ? t : a.created_at < b.created_at ? -1 : 1;
    });
  return rows;
}

export type Stats = {
  total: number;
  by_status: Record<string, number>;
  by_triage: Record<string, number>;
  flagged_cases: number;
  signed: number;
  avg_open_tat_hours: number;
  flags_by_group: Record<string, number>;
  by_day: Record<string, number>;
};

export async function getStats(): Promise<Stats> {
  if (WORKFLOW_LIVE) return authed<Stats>("/workflow/stats");
  // mock: aggregate from the worklist summaries (no per-case flag detail available)
  const cases = await listCases();
  const by_status: Record<string, number> = {};
  const by_triage: Record<string, number> = {};
  const by_day: Record<string, number> = {};
  for (const c of cases) {
    by_status[c.status] = (by_status[c.status] ?? 0) + 1;
    by_triage[c.triage_badge] = (by_triage[c.triage_badge] ?? 0) + 1;
    const d = c.created_at.slice(0, 10);
    by_day[d] = (by_day[d] ?? 0) + 1;
  }
  return {
    total: cases.length,
    by_status,
    by_triage,
    flagged_cases: by_triage.urgent ?? 0,
    signed: by_status.reviewed ?? 0,
    avg_open_tat_hours: 0,
    flags_by_group: {},
    by_day,
  };
}

export async function getCaseWorkflow(id: string): Promise<CaseWorkflow> {
  if (WORKFLOW_LIVE) return authed<CaseWorkflow>(`/workflow/cases/${encodeURIComponent(id)}`);
  return { case_id: id, assignment: null, tat: { age_hours: null, tat_status: "unknown", target_hours: TAT_TARGET_HOURS }, addenda: [] };
}
