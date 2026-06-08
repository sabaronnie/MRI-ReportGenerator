"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";

const SELECT =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function WorklistFilters({ live }: { live: boolean }) {
  const router = useRouter();
  const sp = useSearchParams();

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(sp.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`/worklist${next.toString() ? `?${next}` : ""}`, { scroll: false });
  }

  const mine = sp.get("mine") === "1";

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          placeholder="Search case…"
          defaultValue={sp.get("q") ?? ""}
          onChange={(e) => setParam("q", e.target.value.trim() || null)}
          className={`${SELECT} w-44 pl-8`}
          aria-label="Search cases"
        />
      </div>

      <select
        className={SELECT}
        defaultValue={sp.get("sort") ?? "priority"}
        onChange={(e) => setParam("sort", e.target.value === "priority" ? null : e.target.value)}
        aria-label="Sort"
      >
        <option value="priority">Priority</option>
        <option value="newest">Newest</option>
        <option value="oldest">Oldest</option>
      </select>

      <select
        className={SELECT}
        defaultValue={sp.get("triage") ?? ""}
        onChange={(e) => setParam("triage", e.target.value || null)}
        aria-label="Filter by triage"
      >
        <option value="">All triage</option>
        <option value="urgent">Urgent</option>
        <option value="review">Review</option>
        <option value="none">No flags</option>
      </select>

      <select
        className={SELECT}
        defaultValue={sp.get("status") ?? ""}
        onChange={(e) => setParam("status", e.target.value || null)}
        aria-label="Filter by status"
      >
        <option value="">All status</option>
        <option value="ready">Ready</option>
        <option value="processing">Processing</option>
        <option value="queued">Queued</option>
        <option value="reviewed">Reviewed</option>
      </select>

      {live ? (
        <Button
          variant={mine ? "default" : "outline"}
          size="sm"
          onClick={() => setParam("mine", mine ? null : "1")}
        >
          My cases
        </Button>
      ) : null}
    </div>
  );
}
