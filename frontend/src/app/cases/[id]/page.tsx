import Link from "next/link";
import { notFound } from "next/navigation";
import { getCase } from "@/lib/api/client";
import { CaseHeader } from "@/components/report/case-header";
import { Impressions } from "@/components/report/impressions";
import { FindingsTable } from "@/components/report/findings-table";
import { Disclaimers } from "@/components/report/disclaimers";

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await getCase(id).catch(() => null);
  if (!data) notFound();

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <Link href="/worklist" className="text-sm text-muted-foreground hover:underline">
        ← Worklist
      </Link>

      <div className="mt-3">
        <CaseHeader data={data} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Imaging
          </h2>
          <div className="flex aspect-square items-center justify-center rounded-lg border bg-muted/30 text-sm text-muted-foreground">
            Interactive viewer — next milestone
          </div>
        </section>

        <section className="space-y-6">
          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Impressions
            </h2>
            <Impressions impression={data.report.impression} />
          </div>
          <div>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Findings
            </h2>
            <div className="overflow-hidden rounded-lg border">
              <FindingsTable interpretations={data.interpretations} />
            </div>
          </div>
        </section>
      </div>

      <div className="mt-6">
        <Disclaimers items={data.report.disclaimers} />
      </div>
    </div>
  );
}
