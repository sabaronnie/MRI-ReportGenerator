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

export function CaseTable({ cases }: { cases: CaseSummary[] }) {
  if (cases.length === 0) {
    return (
      <div className="p-10 text-center text-sm text-muted-foreground">
        No cases yet. Upload a scan to get started.
      </div>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Case</TableHead>
          <TableHead>Study</TableHead>
          <TableHead>Uploaded</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="text-right">Auto-screen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cases.map((c) => (
          <TableRow key={c.case_id} className="hover:bg-muted/50">
            <TableCell>
              <Link
                href={`/cases/${c.case_id}`}
                className="font-medium hover:underline"
              >
                {c.case_id}
              </Link>
            </TableCell>
            <TableCell className="text-muted-foreground">{c.modality}</TableCell>
            <TableCell className="text-muted-foreground">{fmt(c.created_at)}</TableCell>
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
