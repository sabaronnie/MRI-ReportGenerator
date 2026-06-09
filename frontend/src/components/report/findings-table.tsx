import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Assessements, AssessedMeasurement } from "@/lib/api/contract";
import { StatusBadge } from "./status-cell";

function humanize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\bap\b/gi, "AP")
    .replace(/\bsac\b/gi, "SAC")
    .replace(/\bvb\b/gi, "VB")
    .replace(/\bdhi\b/gi, "DHI");
}

function fmtValue(m: AssessedMeasurement): string {
  if (m.value === null || m.value === undefined) return "—";
  const unit = m.unit && m.unit !== "unknown" ? ` ${m.unit}` : "";
  return `${Math.round(m.value * 100) / 100}${unit}`;
}

/** Order head-to-toe, keep all measurements at one level together, and slot adjacent
 * disc/segmental pairs (C4-C5) just below their upper body; global spans sort last. */
const levelKey = (l: string): [number, number] => {
  const nums = (l?.match(/C(\d+)/g) ?? []).map((s) => parseInt(s.slice(1), 10));
  if (nums.length === 0) return [99, 0];
  if (nums.length === 1) return [nums[0], 0];
  const [a, b] = nums;
  if (b - a === 1) return [a, 1];
  return [98, a];
};
const HEAD = "text-xs font-medium uppercase tracking-wider text-muted-foreground";

// Clinically-reportable keys (mirror of services/reporting/pdf_report.py). The pipeline
// emits many intermediate/QC rows; the report shows these + any flagged row.
const CLINICAL_KEYS = new Set([
  "canal_AP", "dural_sac_AP_min", "SAC", "cord_AP",
  "DHI", "posterior_bulge_mm", "disc_vb_ap_ratio", "pfirrmann_grade",
  "vb_hahp_ratio", "Cobb_C3_C7", "spondy_slip_mm",
]);

export function FindingsTable({ assessements }: { assessements: Assessements }) {
  const rows = assessements.measurements
    .filter((m) => CLINICAL_KEYS.has(m.measurement) || m.flag)
    .sort((a, b) => {
    const ka = levelKey(a.level);
    const kb = levelKey(b.level);
    return ka[0] - kb[0] || ka[1] - kb[1] || a.measurement.localeCompare(b.measurement);
  });

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
