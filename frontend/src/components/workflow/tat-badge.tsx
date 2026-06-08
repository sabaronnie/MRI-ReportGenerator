import type { Tat } from "@/lib/api/workflow";

const STYLE: Record<string, { cls: string; dot: string }> = {
  on_track: { cls: "bg-emerald-50 text-emerald-700 ring-emerald-200", dot: "bg-emerald-500" },
  warning: { cls: "bg-amber-50 text-amber-700 ring-amber-200", dot: "bg-amber-500" },
  breach: { cls: "bg-rose-50 text-rose-700 ring-rose-200", dot: "bg-rose-500" },
  signed: { cls: "bg-muted text-muted-foreground ring-border", dot: "bg-primary" },
  unknown: { cls: "bg-muted text-muted-foreground ring-border", dot: "bg-muted-foreground/40" },
};

function ageLabel(hours: number | null): string {
  if (hours === null) return "—";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

/** Turnaround-time pill: shows case age, colored by SLA status. */
export function TatBadge({ tat }: { tat: Tat }) {
  const s = STYLE[tat.tat_status] ?? STYLE.unknown;
  const label = tat.tat_status === "signed" ? "Signed" : ageLabel(tat.age_hours);
  return (
    <span
      title={
        tat.tat_status === "breach"
          ? `Over the ${tat.target_hours}h turnaround target`
          : `Turnaround target ${tat.target_hours}h`
      }
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} aria-hidden />
      {label}
    </span>
  );
}
