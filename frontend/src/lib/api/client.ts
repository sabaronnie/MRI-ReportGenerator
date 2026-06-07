/**
 * Typed API client — the single seam between the UI and the data source.
 *
 * MODE=mock (default): serve the vendored contract fixtures from an in-memory store.
 * MODE=live: fetch the real EEP at NEXT_PUBLIC_EEP_URL.
 * Components call these functions and never know which mode is active — that is what lets
 * us build the whole UI now and swap to the real EEP later with no component changes.
 */
import type { CaseEnvelope, CaseSummary, Job } from "./contract";
import healthy from "@/mocks/fixtures/case-healthy.json";
import stenosis from "@/mocks/fixtures/case-stenosis.json";
import fracture from "@/mocks/fixtures/case-fracture.json";

const MODE = process.env.NEXT_PUBLIC_API_MODE ?? "mock";
const EEP_URL = process.env.NEXT_PUBLIC_EEP_URL ?? "";

// ── mock store (cloned so sign-off mutations don't corrupt the imported fixtures) ──
const FIXTURES = [healthy, stenosis, fracture] as unknown as CaseEnvelope[];
const mockStore = new Map<string, CaseEnvelope>(
  FIXTURES.map((c) => [c.case.case_id, structuredClone(c)]),
);

function toSummary(c: CaseEnvelope): CaseSummary {
  const { case_id, status, triage_badge, modality, uploader, created_at, updated_at } = c.case;
  return { case_id, status, triage_badge, modality, uploader, created_at, updated_at };
}

async function eep<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${EEP_URL}${path}`, init);
  if (!res.ok) throw new Error(`EEP ${path} → ${res.status}`);
  return (await res.json()) as T;
}

/** Worklist: every case, newest first. */
export async function listCases(): Promise<CaseSummary[]> {
  if (MODE === "mock") {
    return [...mockStore.values()]
      .map(toSummary)
      .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
  }
  return eep<CaseSummary[]>("/cases");
}

/** Full case envelope for the detail/report view. */
export async function getCase(id: string): Promise<CaseEnvelope> {
  if (MODE === "mock") {
    const c = mockStore.get(id);
    if (!c) throw new Error(`case ${id} not found`);
    return structuredClone(c);
  }
  return eep<CaseEnvelope>(`/cases/${encodeURIComponent(id)}`);
}

/** Processing status (polled while a case is being analyzed). */
export async function getJob(id: string): Promise<Job> {
  if (MODE === "mock") return (await getCase(id)).job;
  return eep<Job>(`/cases/${encodeURIComponent(id)}/job`);
}

/** Radiologist sign-off → report becomes "signed", case becomes "reviewed". */
export async function signOffCase(id: string, signedBy: string): Promise<CaseEnvelope> {
  if (MODE === "mock") {
    const c = mockStore.get(id);
    if (!c) throw new Error(`case ${id} not found`);
    const now = new Date().toISOString();
    c.report.metadata = {
      generated_at: c.report.metadata?.generated_at ?? now,
      schema_version: c.report.metadata?.schema_version ?? "report-0.1",
      reporting_version: c.report.metadata?.reporting_version,
      status: "signed",
      signed_by: signedBy,
      signed_at: now,
    };
    c.case.status = "reviewed";
    return structuredClone(c);
  }
  return eep<CaseEnvelope>(`/cases/${encodeURIComponent(id)}/sign-off`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ signed_by: signedBy }),
  });
}
