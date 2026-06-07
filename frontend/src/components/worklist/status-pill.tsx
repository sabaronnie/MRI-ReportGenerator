import type { CaseStatus } from "@/lib/api/contract";

const MAP: Record<CaseStatus, { label: string; dot: string }> = {
  queued: { label: "Queued", dot: "bg-zinc-400" },
  processing: { label: "Processing", dot: "bg-blue-500 animate-pulse" },
  ready: { label: "Ready", dot: "bg-emerald-500" },
  error: { label: "Error", dot: "bg-red-500" },
  reviewed: { label: "Reviewed", dot: "bg-zinc-500" },
};

export function StatusPill({ status }: { status: CaseStatus }) {
  const m = MAP[status] ?? MAP.queued;
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <span className={`h-2 w-2 rounded-full ${m.dot}`} aria-hidden />
      {m.label}
    </span>
  );
}
