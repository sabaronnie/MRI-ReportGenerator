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
  return key
    .replace(/_/g, " ")
    .replace(/\bap\b/gi, "AP")
    .replace(/\bsac\b/gi, "SAC")
    .replace(/\bvb\b/gi, "VB")
    .replace(/\bdhi\b/gi, "DHI");
}

function fmtValue(m: InterpretedMeasurement): string {
  if (m.value === null || m.value === undefined) return "—";
  return `${Math.round(m.value * 100) / 100} ${m.unit}`;
}

const LEVEL_ORDER = ["C3", "C4", "C5", "C6", "C7"];
const levelRank = (l: string) => {
  const i = LEVEL_ORDER.indexOf(l);
  return i === -1 ? 99 : i;
};
const HEAD = "text-xs font-medium uppercase tracking-wider text-muted-foreground";

export function FindingsTable({ interpretations }: { interpretations: Interpretations }) {
  const rows = [...interpretations.measurements].sort(
    (a, b) =>
      levelRank(a.level) - levelRank(b.level) ||
      a.level.localeCompare(b.level) ||
      a.measurement.localeCompare(b.measurement),
  );

  if (rows.length === 0) {
    return <p className="p-6 text-sm text-muted-foreground">No measurements available.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className={HEAD}>Measurement</TableHead>
          <TableHead className={HEAD}>Level</TableHead>
          <TableHead className={`text-right ${HEAD}`}>Value</TableHead>
          <TableHead className={HEAD}>Status</TableHead>
          <TableHead className={HEAD}>Notes</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((m, i) => (
          <TableRow
            key={`${m.measurement}-${m.level}-${i}`}
            className={m.flag ? "bg-rose-50/60 hover:bg-rose-50" : "hover:bg-accent/30"}
          >
            <TableCell className="font-medium capitalize">{humanize(m.measurement)}</TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground">{m.level}</TableCell>
            <TableCell className="text-right font-mono tabular-nums">{fmtValue(m)}</TableCell>
            <TableCell>
              <StatusBadge status={m.status} />
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">
              {m.severity ? <span className="capitalize">{m.severity.replace(/_/g, " ")}</span> : null}
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
