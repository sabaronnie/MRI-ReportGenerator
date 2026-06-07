/** Mandatory medical-AI disclaimers — always rendered with the report. */
export function Disclaimers({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-4 text-xs text-amber-900">
      <p className="mb-1 font-semibold uppercase tracking-wide">Important</p>
      <ul className="list-disc space-y-1 pl-4">
        {items.map((d, i) => (
          <li key={i}>{d}</li>
        ))}
      </ul>
    </div>
  );
}
