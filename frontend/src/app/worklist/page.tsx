import { listCases } from "@/lib/api/client";
import { CaseTable } from "@/components/worklist/case-table";

export const metadata = { title: "Worklist · Cervical MRI" };

export default async function WorklistPage() {
  const cases = await listCases();
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6 flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Worklist</h1>
          <p className="text-sm text-muted-foreground">
            {cases.length} {cases.length === 1 ? "case" : "cases"}
          </p>
        </div>
      </div>
      <div className="overflow-hidden rounded-lg border">
        <CaseTable cases={cases} />
      </div>
    </div>
  );
}
