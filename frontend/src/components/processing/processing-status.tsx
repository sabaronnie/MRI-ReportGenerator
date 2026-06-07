"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Job } from "@/lib/api/contract";

const STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  segmenting: "Segmenting",
  measuring: "Measuring",
  interpreting: "Interpreting",
  ready: "Ready",
  error: "Error",
};

/** Polls the job endpoint while a case processes; refreshes the page (→ report) when ready. */
export function ProcessingStatus({ caseId, initial }: { caseId: string; initial: Job }) {
  const router = useRouter();
  const [job, setJob] = useState<Job>(initial);

  useEffect(() => {
    if (job.stage === "ready" || job.stage === "error") {
      router.refresh();
      return;
    }
    const t = setInterval(async () => {
      try {
        const res = await fetch(`/api/cases/${encodeURIComponent(caseId)}/job`, { cache: "no-store" });
        if (!res.ok) return;
        const next: Job = await res.json();
        setJob(next);
        if (next.stage === "ready" || next.stage === "error") {
          clearInterval(t);
          router.refresh();
        }
      } catch {
        /* transient — keep polling */
      }
    }, 1200);
    return () => clearInterval(t);
  }, [caseId, job.stage, router]);

  const stages = job.stages?.length ? job.stages : ["queued", "segmenting", "measuring", "interpreting", "ready"];
  const currentIdx = stages.indexOf(job.stage);

  return (
    <div className="rounded-lg border p-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Processing</h2>
      <div className="mt-3 h-2 w-full overflow-hidden rounded bg-muted">
        <div
          className="h-full bg-foreground transition-all duration-500"
          style={{ width: `${Math.round((job.progress ?? 0) * 100)}%` }}
        />
      </div>
      <ol className="mt-4 space-y-1 text-sm">
        {stages.map((s, i) => (
          <li
            key={s}
            className={
              i < currentIdx
                ? "text-muted-foreground"
                : i === currentIdx
                  ? "font-medium"
                  : "text-muted-foreground/50"
            }
          >
            {i < currentIdx ? "✓" : i === currentIdx ? "▸" : "·"} {STAGE_LABEL[s] ?? s}
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-muted-foreground">Updates automatically — no refresh needed.</p>
    </div>
  );
}
