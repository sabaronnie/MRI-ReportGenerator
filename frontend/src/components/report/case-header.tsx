import { Button, buttonVariants } from "@/components/ui/button";
import { TriageBadge } from "@/components/worklist/triage-badge";
import { StatusPill } from "@/components/worklist/status-pill";
import type { CaseEnvelope } from "@/lib/api/contract";

export function CaseHeader({ data }: { data: CaseEnvelope }) {
  const { case: c, report } = data;
  const meta = report.metadata;
  const exports = report.exports;
  const signed = meta?.status === "signed";
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
          {meta?.status ? (
            <>
              <span>·</span>
              <span>report: {meta.status}</span>
            </>
          ) : null}
          {signed && meta?.signed_by ? <span>· signed by {meta.signed_by}</span> : null}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {exports?.pdf_url ? (
          <a className={buttonVariants({ variant: "outline", size: "sm" })} href={exports.pdf_url}>
            PDF
          </a>
        ) : null}
        {exports?.docx_url ? (
          <a className={buttonVariants({ variant: "outline", size: "sm" })} href={exports.docx_url}>
            DOCX
          </a>
        ) : null}
        {/* Sign-off action is wired in the auth/roles milestone (radiologist only). */}
        <Button size="sm" disabled={signed} title="Wired with auth (radiologist only)">
          {signed ? "Signed" : "Sign off"}
        </Button>
      </div>
    </div>
  );
}
