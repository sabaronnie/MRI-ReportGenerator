import type { Report } from "@/lib/api/contract";
import { StatusBadge } from "./status-cell";

export function Impressions({ impression }: { impression: Report["impression"] }) {
  if (!impression?.length) {
    return <p className="text-sm text-muted-foreground">No impressions generated.</p>;
  }
  return (
    <ul className="space-y-2.5">
      {impression.map((imp, i) => (
        <li key={i} className="flex gap-3 rounded-lg border border-border bg-card p-3.5 shadow-sm">
          <StatusBadge status={imp.status} />
          <div className="min-w-0">
            <p className="text-sm leading-relaxed text-foreground">{imp.text}</p>
            {imp.traceable_to?.length ? (
              <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                based on: {imp.traceable_to.join(", ").replace(/_/g, " ")}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
