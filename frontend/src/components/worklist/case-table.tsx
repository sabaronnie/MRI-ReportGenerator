import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CaseSummary } from "@/lib/api/contract";
import { TriageBadge } from "./triage-badge";
import { StatusPill } from "./status-pill";

/** Deterministic UTC formatting (avoids server/client locale hydration mismatches). */
function fmt(iso: string): string {
  return iso.replace("T", " ").slice(0, 16) + " UTC";
}

const HEAD = "text-xs font-medium uppercase tracking-wider text-muted-foreground";

export function CaseTable({ cases }: { cases: CaseSummary[] }) {
  if (cases.length === 0) {
    return (
      <div className="flex flex-col items-center gap-1 p-14 text-center">
        <p className="text-sm font-medium text-foreground">No cases yet</p>
        <p className="text-sm text-muted-foreground">Upload a scan to start a report.</p>
      </div>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className={HEAD}>Case</TableHead>
          <TableHead className={HEAD}>Study</TableHead>
          <TableHead className={HEAD}>Uploaded</TableHead>
          <TableHead className={HEAD}>Status</TableHead>
          <TableHead className={`text-right ${HEAD}`}>Auto-screen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cases.map((c) => (
          <TableRow key={c.case_id} className="group transition-colors hover:bg-accent/40">
            <TableCell>
              <Link
                href={`/cases/${c.case_id}`}
                className="font-mono text-[13px] font-medium text-foreground underline-offset-4 group-hover:text-primary group-hover:underline"
              >
                {c.case_id}
              </Link>
            </TableCell>
            <TableCell className="text-muted-foreground">{c.modality}</TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground">{fmt(c.created_at)}</TableCell>
            <TableCell>
              <StatusPill status={c.status} />
            </TableCell>
            <TableCell className="text-right">
              <TriageBadge triage={c.triage_badge} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
