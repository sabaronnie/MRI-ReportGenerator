import { requireSession } from "@/lib/auth/session";
import { getWorklist, WORKFLOW_LIVE } from "@/lib/api/workflow";
import { CaseTable } from "@/components/worklist/case-table";
import { WorklistFilters } from "@/components/worklist/worklist-filters";

export const metadata = { title: "Worklist · Cervical MRI" };

export default async function WorklistPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const user = await requireSession();
  const sp = await searchParams;
  const rows = await getWorklist({
    status: sp.status,
    triage: sp.triage,
    q: sp.q,
    sort: sp.sort,
    mine: sp.mine === "1",
  });
  return (
    <div className="mx-auto w-full max-w-6xl">
      <p className="mb-4 text-sm text-muted-foreground">
        {rows.length} {rows.length === 1 ? "case" : "cases"} · cervical-spine MRI
      </p>
      <WorklistFilters live={WORKFLOW_LIVE} />
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <CaseTable rows={rows} meId={user.id} live={WORKFLOW_LIVE} />
      </div>
    </div>
  );
}
