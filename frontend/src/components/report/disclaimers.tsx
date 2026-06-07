import { TriangleAlert } from "lucide-react";

/** Mandatory medical-AI disclaimers — always rendered with the report. Calm, not alarming. */
export function Disclaimers({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="rounded-xl border border-amber-200/70 bg-amber-50/50 p-5">
      <div className="flex items-center gap-2 text-amber-800">
        <TriangleAlert className="h-[15px] w-[15px]" />
        <span className="text-xs font-semibold uppercase tracking-wider">Important — research use</span>
      </div>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-xs leading-relaxed text-amber-900/80">
        {items.map((d, i) => (
          <li key={i}>{d}</li>
        ))}
      </ul>
    </div>
  );
}
