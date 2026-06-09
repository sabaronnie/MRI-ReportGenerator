import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { WorklistRow } from "@/lib/api/workflow";
import { TriageBadge } from "./triage-badge";
import { StatusPill } from "./status-pill";
import { TatBadge } from "@/components/workflow/tat-badge";
import { ClaimCell } from "@/components/workflow/claim-cell";

const HEAD = "text-xs font-medium uppercase tracking-wider text-muted-foreground";

export function CaseTable({
  rows,
  meId,
  live,
}: {
  rows: WorklistRow[];
  meId: string;
  live: boolean;
}) {
  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center gap-1 p-14 text-center">
        <p className="text-sm font-medium text-foreground">No cases match</p>
        <p className="text-sm text-muted-foreground">Adjust the filters or upload a scan.</p>
      </div>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className={HEAD}>Case</TableHead>
          <TableHead className={HEAD}>Study</TableHead>
          <TableHead className={HEAD}>Age</TableHead>
          <TableHead className={HEAD}>Status</TableHead>
          {live ? <TableHead className={HEAD}>Assignee</TableHead> : null}
          <TableHead className={`text-right ${HEAD}`}>Auto-screen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((c) => (
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
            <TableCell>
              <TatBadge tat={c.tat} />
            </TableCell>
            <TableCell>
              <StatusPill status={c.status} />
            </TableCell>
            {live ? (
              <TableCell>
                <ClaimCell caseId={c.case_id} assignment={c.assignment} meId={meId} />
              </TableCell>
            ) : null}
            <TableCell className="text-right">
              <TriageBadge triage={c.triage_badge} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
