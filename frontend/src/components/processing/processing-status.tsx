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
 * Live processing progress. Polls by calling router.refresh() on an interval, which re-runs the
 * server component (reading the store/EEP that owns the case) and re-passes an advanced `job`.
 * When the case reaches "ready", the server renders the report instead and this unmounts.
 */
export function ProcessingStatus({ job }: { job: Job }) {
  const router = useRouter();

  useEffect(() => {
    const t = setInterval(() => router.refresh(), 1200);
    return () => clearInterval(t);
  }, [router]);

  const stages = job.stages?.length
    ? job.stages
    : ["queued", "segmenting", "measuring", "interpreting", "ready"];
  const currentIdx = stages.indexOf(job.stage);
  const pct = Math.round((job.progress ?? 0) * 100);

  return (
    <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
      <div className="flex items-center gap-3">
        <span className="relative grid h-9 w-9 place-items-center">
          <span className="absolute inset-0 animate-ping rounded-full bg-primary/20" />
          <span className="grid h-9 w-9 place-items-center rounded-full bg-accent text-accent-foreground">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="animate-spin"
              style={{ animationDuration: "1.4s" }}
              aria-hidden
            >
              <path d="M21 12a9 9 0 1 1-6.22-8.56" />
            </svg>
          </span>
        </span>
        <div>
          <h2 className="font-serif text-lg font-semibold tracking-tight">Analyzing scan</h2>
          <p className="text-sm text-muted-foreground">Segmentation → measurement → interpretation</p>
        </div>
      </div>

      <div className="mt-5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>

      <ol className="mt-5 grid gap-2 text-sm sm:grid-cols-5">
        {stages.map((s, i) => {
          const done = i < currentIdx;
          const active = i === currentIdx;
          return (
            <li
              key={s}
              className={`flex items-center gap-2 rounded-md px-2 py-1.5 ${
                active
                  ? "bg-accent/60 font-medium text-foreground"
                  : done
                    ? "text-muted-foreground"
                    : "text-muted-foreground/50"
              }`}
            >
              <span
                className={`grid h-4 w-4 shrink-0 place-items-center rounded-full text-[10px] ${
                  done
                    ? "bg-emerald-500 text-white"
                    : active
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                }`}
              >
                {done ? "✓" : active ? "•" : ""}
              </span>
              {STAGE_LABEL[s] ?? s}
            </li>
          );
        })}
      </ol>

      <p className="mt-4 text-xs text-muted-foreground">Updates automatically — no refresh needed.</p>
    </div>
  );
}
