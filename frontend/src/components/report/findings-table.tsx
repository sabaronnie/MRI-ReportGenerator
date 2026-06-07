import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Interpretations, InterpretedMeasurement } from "@/lib/api/contract";
import { StatusBadge } from "./status-cell";

function humanize(key: string): string {
  return key.replace(/_/g, " ").replace(/\bap\b/i, "AP").replace(/\bsac\b/i, "SAC");
}

function fmtValue(m: InterpretedMeasurement): string {
  if (m.value === null || m.value === undefined) return "—";
  const rounded = Math.round(m.value * 100) / 100;
  return `${rounded} ${m.unit}`;
}

const LEVEL_ORDER = ["C3", "C4", "C5", "C6", "C7"];
function levelRank(level: string): number {
  const i = LEVEL_ORDER.indexOf(level);
  return i === -1 ? 99 : i;
}

export function FindingsTable({ interpretations }: { interpretations: Interpretations }) {
  const rows = [...interpretations.measurements].sort(
    (a, b) =>
      levelRank(a.level) - levelRank(b.level) ||
      a.level.localeCompare(b.level) ||
      a.measurement.localeCompare(b.measurement),
  );

  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No measurements available.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Measurement</TableHead>
          <TableHead>Level</TableHead>
          <TableHead>Value</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Notes</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((m, i) => (
          <TableRow key={`${m.measurement}-${m.level}-${i}`} className={m.flag ? "bg-red-50" : undefined}>
            <TableCell className="font-medium capitalize">{humanize(m.measurement)}</TableCell>
            <TableCell>{m.level}</TableCell>
            <TableCell className="tabular-nums">{fmtValue(m)}</TableCell>
            <TableCell>
              <StatusBadge status={m.status} />
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">
              {m.severity ? <span>{m.severity.replace(/_/g, " ")}</span> : null}
              {m.quality_flags?.length ? (
                <span className="ml-1 italic">· {m.quality_flags.join(", ").replace(/_/g, " ")}</span>
              ) : null}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
