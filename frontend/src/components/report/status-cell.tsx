import type { InterpretationStatus } from "@/lib/api/contract";

const MAP: Record<InterpretationStatus, { label: string; className: string }> = {
  within_reference: { label: "Normal", className: "bg-emerald-100 text-emerald-800" },
  outside_reference: { label: "Flagged", className: "bg-red-100 text-red-800" },
  review_only: { label: "Review", className: "bg-amber-100 text-amber-800" },
  not_interpretable: { label: "N/A", className: "bg-zinc-100 text-zinc-600" },
};

/** Renders an InterpretedMeasurement.status as a colored pill. Never implies a diagnosis. */
export function StatusBadge({ status }: { status: InterpretationStatus }) {
  const m = MAP[status] ?? MAP.not_interpretable;
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${m.className}`}>
      {m.label}
    </span>
  );
}
