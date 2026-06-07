import { Button, buttonVariants } from "@/components/ui/button";
import { TriageBadge } from "@/components/worklist/triage-badge";
import { StatusPill } from "@/components/worklist/status-pill";
import type { CaseEnvelope } from "@/lib/api/contract";
import { signOffAction } from "@/app/cases/[id]/actions";

export function CaseHeader({ data, canSign }: { data: CaseEnvelope; canSign: boolean }) {
  const { case: c, report } = data;
  const meta = report.metadata;
  const exports = report.exports;
  const signed = meta?.status === "signed";
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold tracking-tight text-foreground">{c.case_id}</h1>
          <TriageBadge triage={c.triage_badge} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
          <StatusPill status={c.status} />
          <span aria-hidden>·</span>
          <span>{c.modality}</span>
          {meta?.status ? (
            <>
              <span aria-hidden>·</span>
              <span>report {meta.status}</span>
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
        {signed ? (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden>
              <path d="M20 6 9 17l-5-5" />
            </svg>
            Signed
          </span>
        ) : canSign ? (
          <form action={signOffAction}>
            <input type="hidden" name="caseId" value={c.case_id} />
            <Button size="sm" type="submit">
              Sign off
            </Button>
          </form>
        ) : null}
      </div>
    </div>
  );
}
