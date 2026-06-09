import { AlertTriangle, Clock, FileSignature, ListChecks } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Stats } from "@/lib/api/workflow";

const TONE: Record<string, string> = {
  teal: "text-primary",
  rose: "text-rose-600",
  amber: "text-amber-600",
  emerald: "text-emerald-600",
};

export function StatCards({ stats }: { stats: Stats }) {
  const awaiting = stats.by_status.ready ?? 0;
  const cards = [
    { label: "Total cases", value: stats.total, hint: "in the worklist", icon: ListChecks, tone: "teal" },
    { label: "Urgent", value: stats.by_triage.urgent ?? 0, hint: "flagged for review", icon: AlertTriangle, tone: "rose" },
    {
      label: "Awaiting sign-off",
      value: awaiting,
      hint: stats.avg_open_tat_hours ? `avg ${stats.avg_open_tat_hours} h open` : "ready to read",
      icon: Clock,
      tone: "amber",
    },
    { label: "Signed", value: stats.signed, hint: "completed reports", icon: FileSignature, tone: "emerald" },
  ];

  return (
    <>
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <Card key={c.label}>
            <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
              <CardTitle className="text-xs font-normal text-muted-foreground">{c.label}</CardTitle>
              <Icon className={`size-4 ${TONE[c.tone]}`} />
            </CardHeader>
            <CardContent>
              <div className="font-serif text-3xl font-semibold tracking-tight tabular-nums">{c.value}</div>
              <p className="mt-1 text-xs text-muted-foreground">{c.hint}</p>
            </CardContent>
          </Card>
        );
      })}
    </>
  );
}
