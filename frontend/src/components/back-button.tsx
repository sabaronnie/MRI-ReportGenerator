"use client";

import { useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";

/** Browser-history back, styled. Used at the top of sub-pages. */
export function BackButton({ label = "Back" }: { label?: string }) {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => router.back()}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <ChevronLeft className="h-4 w-4" />
      {label}
    </button>
  );
}
