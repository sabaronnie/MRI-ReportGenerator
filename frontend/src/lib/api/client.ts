/**
 * Typed API client — the single seam between the UI and the data source.
 *
 * MODE=mock (default): serve the vendored contract fixtures from an in-memory store.
 * MODE=live: fetch the real EEP at NEXT_PUBLIC_EEP_URL.
 * Components call these functions and never know which mode is active — that is what lets
 * us build the whole UI now and swap to the real EEP later with no component changes.
 */
import { redirect } from "next/navigation";
import type { CaseEnvelope, CaseSummary, Job, JobStage } from "./contract";
import { getToken } from "@/lib/auth/session";
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

// ── simulated processing (mock upload → queued → … → ready, driven by elapsed time) ──
const simStart = new Map<string, number>();
const SIM_TOTAL_MS = 8000;
const SIM_STEPS: { stage: JobStage; until: number }[] = [
  { stage: "queued", until: 1500 },
  { stage: "segmenting", until: 4000 },
  { stage: "measuring", until: 6500 },
  { stage: "assessing", until: 8000 },
];
const STAGE_ORDER = ["queued", "segmenting", "measuring", "assessing", "ready"];

/** Advance a simulated (uploaded) case's job/status from elapsed time. No-op for the fixtures. */
function advance(c: CaseEnvelope): void {
  const start = simStart.get(c.case.case_id);
  if (start === undefined) return;
  const elapsed = Date.now() - start;
  let stage: JobStage = "ready";
  for (const s of SIM_STEPS) {
    if (elapsed < s.until) {
      stage = s.stage;
      break;
    }
  }
  c.job = { stage, stages: STAGE_ORDER, progress: Math.min(1, elapsed / SIM_TOTAL_MS), error: null };
  c.case.status = stage === "ready" ? "ready" : "processing";
}

/** Server-side EEP fetch. Forwards the session JWT as a Bearer token; an expired/
 * invalid token (401) bounces the user to login. */
async function eep<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${EEP_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (res.status === 401) redirect("/api/session/expired");
  if (!res.ok) throw new Error(`EEP ${path} → ${res.status}`);
  return (await res.json()) as T;
}

/** Worklist: every case, newest first. */
export async function listCases(): Promise<CaseSummary[]> {
  if (MODE === "mock") {
    const all = [...mockStore.values()];
    all.forEach(advance);
    return all.map(toSummary).sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1));
  }
  return eep<CaseSummary[]>("/cases");
}

/** Full case envelope for the detail/report view. */
export async function getCase(id: string): Promise<CaseEnvelope> {
  if (MODE === "mock") {
    const c = mockStore.get(id);
    if (!c) throw new Error(`case ${id} not found`);
    advance(c);
    return structuredClone(c);
  }
  return eep<CaseEnvelope>(`/cases/${encodeURIComponent(id)}`);
}

/** Mock upload: clone a baseline case as a new "queued" case and start the simulated pipeline. */
export async function createCase(
  filename: string,
  uploader: string,
  file?: File | Blob,
): Promise<{ case_id: string }> {
  if (MODE === "mock") {
    const baseline = mockStore.get("demo-healthy-0001");
    const base = structuredClone(baseline ?? FIXTURES[0]);
    const now = new Date();
    const id = `upload-${now.getTime().toString(36)}`;
    base.case.case_id = id;
    base.case.status = "queued";
    base.case.triage_badge = "none";
    base.case.uploader = uploader;
    base.case.created_at = now.toISOString();
    base.case.updated_at = now.toISOString();
    base.case.series_description = filename;
    base.job = { stage: "queued", stages: STAGE_ORDER, progress: 0, error: null };
    mockStore.set(id, base);
    simStart.set(id, Date.now());
    return { case_id: id };
  }
  // live: forward the actual file as multipart to the EEP's POST /cases (it validates
  // type/size and returns {case_id, status}). The upload bytes stand in for the scan; the
  // EEP runs measurements off the mounted stand-in segmentation in this demo deployment.
  const form = new FormData();
  form.append("file", file ?? new Blob([], { type: "application/gzip" }), filename);
  form.append("uploader", uploader);
  return eep<{ case_id: string }>("/cases", { method: "POST", body: form });
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

/** Viewer image sources (NiiVue). Mock: vendored /samples files. Live: EEP volume + TSS mask routes. */
export function getViewerSources(id: string): { volumeUrl: string; maskUrl?: string } {
  if (MODE === "mock") {
    return {
      volumeUrl: "/samples/sample_volume_T2.nii.gz",
      maskUrl: "/samples/sample_mask_tss.nii.gz",
    };
  }
  // Same-origin Next.js proxy routes that attach the Bearer token server-side
  // (the browser can't read the httpOnly token, and the EEP now guards /cases).
  return {
    volumeUrl: `/api/cases/${encodeURIComponent(id)}/volume`,
    maskUrl: `/api/cases/${encodeURIComponent(id)}/mask`,
  };
}

/** URL of the rendered clinical report (reporting IEP). Live only — proxied
 * through Next.js so the Bearer token is attached. Mock has no HTML report. */
export function getReportHtmlUrl(id: string): string | null {
  if (MODE === "mock" || !EEP_URL) return null;
  return `/api/cases/${encodeURIComponent(id)}/report`;
}

/** URL of the branded clinical report PDF (reporting IEP). Live only, proxied. */
export function getReportPdfUrl(id: string): string | null {
  if (MODE === "mock" || !EEP_URL) return null;
  return `/api/cases/${encodeURIComponent(id)}/report-pdf`;
}
