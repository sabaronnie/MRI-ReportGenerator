/** Mandatory medical-AI disclaimers — always rendered with the report. Calm, not alarming. */
export function Disclaimers({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="rounded-xl border border-amber-200/70 bg-amber-50/50 p-5">
      <div className="flex items-center gap-2 text-amber-800">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
          <path d="M12 9v4M12 17h.01" />
        </svg>
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
