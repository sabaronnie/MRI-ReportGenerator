import type { TriageBadge as Triage } from "@/lib/api/contract";

const MAP: Record<Triage, { label: string; cls: string; dot: string }> = {
  urgent: { label: "Urgent", cls: "bg-rose-50 text-rose-700 ring-rose-200", dot: "bg-rose-500" },
  review: { label: "Review", cls: "bg-amber-50 text-amber-700 ring-amber-200", dot: "bg-amber-500" },
  none: { label: "No flags", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-emerald-500" },
};

export function TriageBadge({ triage }: { triage: Triage }) {
  const m = MAP[triage] ?? MAP.none;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${m.cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} aria-hidden />
      {m.label}
    </span>
  );
}
