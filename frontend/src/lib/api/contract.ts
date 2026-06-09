/**
 * Typed mirror of the FROZEN data + report contract.
 * Source of truth: docs/contracts/data-contract-v0.1.md + report-contract-v0.1.md.
 *
 * Both the MSW mock and the real EEP responses conform to these shapes.
 * Rules baked in from the contract:
 *  - read thresholds/citations FROM the response, never hardcode;
 *  - treat every measurement/flag key as OPTIONAL (a component can error → key absent);
 *  - `report.figure` may be null.
 */

// ── levels & keys ──────────────────────────────────────────────────────────
export type Level = "C3" | "C4" | "C5" | "C6" | "C7";
export const LEVELS: Level[] = ["C3", "C4", "C5", "C6", "C7"];
/** Adjacent pair like "C3-C4", or a span like "C3-C7". */
export type LevelKey = string; // level OR pair OR span — keep loose, values keyed by string

// ── frozen core: measurements / flags / components ───────────────────────────
/** `{ measurement_key: { level_or_pair: number } }` — every key optional. */
export type MeasurementMap = Record<string, Record<LevelKey, number>>;
/** `{ flag_key: { level_or_pair: boolean } }`. */
export type FlagMap = Record<string, Record<LevelKey, boolean>>;

export type ComponentStatus = "ok" | "error";
export interface ComponentResult {
  status: ComponentStatus;
  duration_s: number;
  error?: string;
  metadata?: Record<string, unknown>;
}
export type Components = Record<string, ComponentResult>;

// ── frozen assessement layer (the most useful object for the UI) ──────────
/** Standardized 4-value vocabulary (FROZEN). */
export type AssessementStatus =
  | "within_reference"
  | "outside_reference"
  | "review_only"
  | "not_assessable";

export interface AssessedMeasurement {
  measurement: string;
  level: LevelKey;
  value: number | null;
  unit: string;
  status: AssessementStatus;
  /** per-measurement label (vocabulary differs by measurement) or null. */
  severity: string | null;
  /** true ⇔ status === "outside_reference". */
  flag: boolean;
  demographics_used: Record<string, unknown>;
  quality_flags: string[];
  caveat: string | null;
}
export interface Assessements {
  measurements: AssessedMeasurement[];
}

/** A flag/quality_flag is "quality/caution" (not a patient abnormality) if its name contains any marker. */
export const QUALITY_FLAG_MARKERS = [
  "low_confidence",
  "misaligned",
  "approximate",
  "resolution",
  "warning",
  "outlier",
  "unreliable",
] as const;
export const isQualityFlag = (name: string): boolean =>
  QUALITY_FLAG_MARKERS.some((m) => name.includes(m));

// ── case envelope (EEP) ──────────────────────────────────────────────────────
export type CaseStatus = "queued" | "processing" | "ready" | "error" | "reviewed";
export type TriageBadge = "none" | "review" | "urgent";

export interface CaseMeta {
  case_id: string;
  status: CaseStatus;
  modality: string;
  series_description: string;
  study_date: string | null;
  uploader: string;
  triage_badge: TriageBadge;
  patient: { sex: string | null; age: number | null };
  created_at: string;
  updated_at: string;
  levels_measured: Level[];
  segmenters_used: Record<string, string>;
}

export type JobStage =
  | "queued"
  | "segmenting"
  | "measuring"
  | "assessing"
  | "ready"
  | "error";
export interface Job {
  stage: JobStage;
  stages: string[];
  progress: number; // 0..1
  error: string | null;
}

// ── report object (Ronnie produces, EEP serves public URLs, frontend renders) ─
export interface Impression {
  text: string;
  traceable_to: string[];
  status: AssessementStatus;
  severity?: string | null;
}
export type ReportFigure = {
  kind: "png";
  annotated_png_url: string;
  caption?: string;
} | null;
export interface ReportExports {
  pdf_url: string;
  docx_url: string;
  generated_at: string;
}
export type ReportMetadataStatus = "draft" | "final" | "signed";
export interface ReportMetadata {
  generated_at: string;
  schema_version: string;
  reporting_version?: string;
  status: ReportMetadataStatus;
  signed_by: string | null;
  signed_at: string | null;
}
export interface Report {
  schema_version?: string;
  impression: Impression[];
  disclaimers: string[];
  // Everything below is 🟡/⚪ in the contract — the reporting service is still a scaffold,
  // so current pipeline output omits these. Treat as optional (see data-contract §10).
  findings_by_level?: { source: string; order: Level[]; highlight?: string[] };
  figure?: ReportFigure;
  exports?: ReportExports;
  metadata?: ReportMetadata;
}

/** The full object returned by `GET /cases/{id}`. */
export interface CaseEnvelope {
  schema_version: string;
  case: CaseMeta;
  job: Job;
  measurements: MeasurementMap;
  flags: FlagMap;
  components: Components;
  assessements: Assessements;
  report: Report;
}

/** Worklist row (`GET /cases`) — a lightweight projection of the case. */
export interface CaseSummary {
  case_id: string;
  status: CaseStatus;
  triage_badge: TriageBadge;
  modality: string;
  uploader: string;
  created_at: string;
  updated_at: string;
}

// ── standard error shape (PROPOSED, used everywhere) ─────────────────────────
export type FailedStage =
  | "upload"
  | "segmenting"
  | "measuring"
  | "assessing"
  | "reporting";
export interface ApiError {
  code: string;
  message: string;
  failed_stage: FailedStage;
  retryable: boolean;
}

// ── roles (RBAC) ─────────────────────────────────────────────────────────────
export type Role = "admin" | "radiologist" | "technologist" | "viewer";
