import { listCases } from "@/lib/api/client";
import { CaseTable } from "@/components/worklist/case-table";

export const metadata = { title: "Worklist · Cervical MRI" };

export default async function WorklistPage() {
  const cases = await listCases();
  return (
    <div className="mx-auto w-full max-w-6xl">
      <p className="mb-4 text-sm text-muted-foreground">
        {cases.length} {cases.length === 1 ? "case" : "cases"} · cervical-spine MRI
      </p>
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <CaseTable cases={cases} />
      </div>
    </div>
  );
}
