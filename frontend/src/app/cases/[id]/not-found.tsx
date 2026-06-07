import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <h1 className="text-xl font-semibold">Case not found</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        This case does not exist or is not available to you.
      </p>
      <Link href="/worklist" className="mt-3 inline-block text-sm underline">
        ← Back to worklist
      </Link>
    </div>
  );
}
