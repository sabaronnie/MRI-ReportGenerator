import Link from "next/link";
import { Activity, FileSignature, ShieldCheck, Upload } from "lucide-react";
import { Header } from "@/components/header";
import { FloatingPaths } from "@/components/floating-paths";
import { Reveal, Stagger, StaggerItem } from "@/components/motion/reveal";
import { buttonVariants } from "@/components/ui/button";

export const metadata = {
  title: "Cervical MRI Reporting — automated cervical-spine MRI analysis",
  description: "Sagittal cervical-spine MRI in, structured measurements + triage + a signed report out.",
};

const STEPS = [
  { icon: Upload, title: "Upload a scan", body: "Drop a sagittal T2 cervical MRI (DICOM or NIfTI). Segmentation runs upstream." },
  { icon: Activity, title: "Measure & screen", body: "Vertebra, disc, canal, and cord geometry measured, then screened against cited thresholds." },
  { icon: FileSignature, title: "Review & sign off", body: "A radiologist reviews the structured report, adds addenda, and signs — exportable as PDF." },
];

export default function LandingPage() {
  return (
    <div className="flex min-h-svh flex-col px-3 pb-16">
      <Header />

      {/* Hero */}
      <section id="overview" className="relative mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center py-20 text-center">
        <div className="pointer-events-none absolute inset-0 -z-10 opacity-50">
          <FloatingPaths position={1} />
          <FloatingPaths position={-1} />
        </div>
        <Reveal>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-primary" /> Cervical-spine MRI analysis
          </span>
        </Reveal>
        <Reveal className="mt-5">
          <h1 className="mx-auto max-w-2xl font-serif text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            From cervical MRI to a structured, signed report — in seconds.
          </h1>
        </Reveal>
        <Reveal className="mt-4">
          <p className="mx-auto max-w-xl text-base text-muted-foreground">
            Automated vertebral, disc, canal, and cord measurements with threshold-based triage —
            every finding flagged for physician review, never a diagnosis.
          </p>
        </Reveal>
        <Reveal className="mt-7">
          <div className="flex items-center justify-center gap-3">
            <Link href="/login" className={buttonVariants({ size: "lg" })}>
              Sign in
            </Link>
            <a href="#how" className={buttonVariants({ size: "lg", variant: "outline" })}>
              How it works
            </a>
          </div>
        </Reveal>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto w-full max-w-4xl py-12">
        <h2 className="text-center font-serif text-2xl font-semibold tracking-tight">How it works</h2>
        <Stagger className="mt-8 grid gap-4 sm:grid-cols-3">
          {STEPS.map((s, i) => {
            const Icon = s.icon;
            return (
              <StaggerItem key={s.title}>
                <div className="h-full rounded-xl border border-border bg-card p-5 shadow-sm">
                  <span className="grid size-10 place-items-center rounded-lg bg-accent text-primary">
                    <Icon className="size-5" />
                  </span>
                  <h3 className="mt-4 font-medium text-foreground">
                    {i + 1}. {s.title}
                  </h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{s.body}</p>
                </div>
              </StaggerItem>
            );
          })}
        </Stagger>
      </section>

      {/* Safety */}
      <section id="safety" className="mx-auto w-full max-w-3xl py-12">
        <div className="rounded-xl border border-border bg-muted/40 p-6">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 size-5 shrink-0 text-primary" />
            <div>
              <h2 className="font-serif text-lg font-semibold tracking-tight">Research-use, clinician-in-the-loop</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Outputs are structured screens flagged for physician review — not a diagnosis. Every
                measurement carries its cited threshold and caveats, and a radiologist signs off on the
                final report. Clinical correlation is always required.
              </p>
            </div>
          </div>
        </div>
      </section>

      <footer className="mx-auto mt-auto w-full max-w-4xl border-t border-border pt-6 text-center text-xs text-muted-foreground">
        Cervical MRI Reporting · EECE503N · research-use structured interpretation, not a medical device.
      </footer>
    </div>
  );
}
