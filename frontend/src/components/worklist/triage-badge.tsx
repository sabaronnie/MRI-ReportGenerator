import { Badge } from "@/components/ui/badge";
import type { TriageBadge as Triage } from "@/lib/api/contract";

const MAP: Record<Triage, { label: string; className: string }> = {
  urgent: { label: "Urgent", className: "bg-red-600 text-white border-transparent" },
  review: { label: "Review", className: "bg-amber-500 text-white border-transparent" },
  none: { label: "No flags", className: "bg-emerald-600 text-white border-transparent" },
};

export function TriageBadge({ triage }: { triage: Triage }) {
  const m = MAP[triage] ?? MAP.none;
  return <Badge className={m.className}>{m.label}</Badge>;
}
