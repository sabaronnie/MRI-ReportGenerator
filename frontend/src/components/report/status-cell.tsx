import type { InterpretationStatus } from "@/lib/api/contract";

const MAP: Record<InterpretationStatus, { label: string; cls: string }> = {
  within_reference: { label: "Normal", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  outside_reference: { label: "Flagged", cls: "bg-rose-50 text-rose-700 ring-rose-200" },
  review_only: { label: "Review", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
  not_interpretable: { label: "N/A", cls: "bg-zinc-100 text-zinc-500 ring-zinc-200" },
};

/** Renders an InterpretedMeasurement.status as a colored pill. Never implies a diagnosis. */
export function StatusBadge({ status }: { status: InterpretationStatus }) {
  const m = MAP[status] ?? MAP.not_interpretable;
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${m.cls}`}
    >
      {m.label}
    </span>
  );
}
