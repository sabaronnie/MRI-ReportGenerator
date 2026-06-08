"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const INPUT =
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
          className={`${INPUT} w-44 pl-8`}
          aria-label="Search cases"
        />
      </div>

      <Select
        value={sp.get("sort") ?? "priority"}
        onValueChange={(v) => setParam("sort", v === "priority" ? null : v)}
      >
        <SelectTrigger size="sm" className="w-32" aria-label="Sort">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="priority">Priority</SelectItem>
          <SelectItem value="newest">Newest</SelectItem>
          <SelectItem value="oldest">Oldest</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={sp.get("triage") ?? "all"}
        onValueChange={(v) => setParam("triage", v === "all" ? null : v)}
      >
        <SelectTrigger size="sm" className="w-32" aria-label="Filter by triage">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All triage</SelectItem>
          <SelectItem value="urgent">Urgent</SelectItem>
          <SelectItem value="review">Review</SelectItem>
          <SelectItem value="none">No flags</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={sp.get("status") ?? "all"}
        onValueChange={(v) => setParam("status", v === "all" ? null : v)}
      >
        <SelectTrigger size="sm" className="w-32" aria-label="Filter by status">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All status</SelectItem>
          <SelectItem value="ready">Ready</SelectItem>
          <SelectItem value="processing">Processing</SelectItem>
          <SelectItem value="queued">Queued</SelectItem>
          <SelectItem value="reviewed">Reviewed</SelectItem>
        </SelectContent>
      </Select>

      {live ? (
        <Button variant={mine ? "default" : "outline"} size="sm" onClick={() => setParam("mine", mine ? null : "1")}>
          My cases
        </Button>
      ) : null}
    </div>
  );
}
