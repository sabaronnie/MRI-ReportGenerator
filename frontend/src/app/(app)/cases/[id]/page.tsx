import { notFound } from "next/navigation";
import { BackButton } from "@/components/back-button";
import { getCase, getViewerSources } from "@/lib/api/client";
import { requireSession } from "@/lib/auth/session";
import { CaseHeader } from "@/components/report/case-header";
import { Impressions } from "@/components/report/impressions";
import { FindingsTable } from "@/components/report/findings-table";
import { Disclaimers } from "@/components/report/disclaimers";
import { NiivueViewer } from "@/components/viewer/niivue-viewer";
import { ProcessingStatus } from "@/components/processing/processing-status";

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const user = await requireSession();
  const data = await getCase(id).catch(() => null);
  if (!data) notFound();
  const viewer = getViewerSources(id);
  const processing = data.job.stage !== "ready";

  return (
    <div className="mx-auto w-full max-w-6xl">
      <BackButton label="Worklist" />

      <div className="mt-3">
        <CaseHeader data={data} canSign={user.role === "radiologist"} />
      </div>

      {processing ? (
        <ProcessingStatus job={data.job} />
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
            <section>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Imaging
              </h2>
              <NiivueViewer volumeUrl={viewer.volumeUrl} maskUrl={viewer.maskUrl} />
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
        </>
      )}
    </div>
  );
}
