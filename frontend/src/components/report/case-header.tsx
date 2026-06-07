import { Button, buttonVariants } from "@/components/ui/button";
import { TriageBadge } from "@/components/worklist/triage-badge";
import { StatusPill } from "@/components/worklist/status-pill";
import type { CaseEnvelope } from "@/lib/api/contract";

export function CaseHeader({ data }: { data: CaseEnvelope }) {
  const { case: c, report } = data;
  const signed = report.metadata.status === "signed";
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{c.case_id}</h1>
          <TriageBadge triage={c.triage_badge} />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <StatusPill status={c.status} />
          <span>·</span>
          <span>{c.modality}</span>
          <span>·</span>
          <span>report: {report.metadata.status}</span>
          {signed && report.metadata.signed_by ? <span>· signed by {report.metadata.signed_by}</span> : null}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <a className={buttonVariants({ variant: "outline", size: "sm" })} href={report.exports.pdf_url}>
          PDF
        </a>
        <a className={buttonVariants({ variant: "outline", size: "sm" })} href={report.exports.docx_url}>
          DOCX
        </a>
        {/* Sign-off action is wired in the auth/roles milestone (radiologist only). */}
        <Button size="sm" disabled={signed} title="Wired with auth (radiologist only)">
          {signed ? "Signed" : "Sign off"}
        </Button>
      </div>
    </div>
  );
}
