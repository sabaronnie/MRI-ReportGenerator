"use client";

import { useEffect } from "react";
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

/**
 * Shows live processing progress. Polls by calling router.refresh() on an interval, which re-runs
 * the server component (reading the same store/EEP that owns the case) and re-passes an advanced `job`.
 * When the case reaches "ready", the server component renders the report instead and this unmounts.
 */
export function ProcessingStatus({ job }: { job: Job }) {
  const router = useRouter();

  useEffect(() => {
    const t = setInterval(() => router.refresh(), 1200);
    return () => clearInterval(t);
  }, [router]);

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
