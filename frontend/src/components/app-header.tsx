import Link from "next/link";

export function AppHeader() {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link href="/worklist" className="flex items-center gap-2 font-semibold">
          <span className="inline-block h-5 w-5 rounded bg-foreground" aria-hidden />
          Cervical&nbsp;MRI
          <span className="font-normal text-muted-foreground">· Worklist</span>
        </Link>
        {/* Placeholder identity — replaced by real auth/role in the auth milestone. */}
        <span className="text-sm text-muted-foreground">Dr. Demo · Radiologist</span>
      </div>
    </header>
  );
}
