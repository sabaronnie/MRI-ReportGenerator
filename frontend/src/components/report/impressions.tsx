import type { Report } from "@/lib/api/contract";
import { StatusBadge } from "./status-cell";

export function Impressions({ impression }: { impression: Report["impression"] }) {
  if (!impression?.length) {
    return <p className="text-sm text-muted-foreground">No impressions generated.</p>;
  }
  return (
    <ul className="space-y-3">
      {impression.map((imp, i) => (
        <li key={i} className="flex gap-3">
          <StatusBadge status={imp.status} />
          <div>
            <p className="text-sm">{imp.text}</p>
            {imp.traceable_to?.length ? (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Based on: {imp.traceable_to.join(", ").replace(/_/g, " ")}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}
