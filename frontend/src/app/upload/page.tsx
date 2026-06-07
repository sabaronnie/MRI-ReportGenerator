import { Upload } from "lucide-react";
import { requireRole } from "@/lib/auth/session";
import { uploadAction } from "./actions";
import { Button } from "@/components/ui/button";
import { BackButton } from "@/components/back-button";

export const metadata = { title: "Upload · Cervical MRI" };

export default async function UploadPage() {
  await requireRole(["radiologist", "technologist", "admin"]);
  return (
    <div className="mx-auto max-w-xl px-6 py-10">
      <div className="mb-4">
        <BackButton label="Worklist" />
      </div>
      <h1 className="font-serif text-[28px] font-semibold tracking-tight">Upload a scan</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Sagittal T2 cervical MRI — DICOM series (.zip) or NIfTI (.nii.gz).
      </p>
      <form action={uploadAction} className="mt-6 rounded-xl border border-border bg-card p-6 shadow-sm">
        <label
          htmlFor="file"
          className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-muted/30 px-6 py-10 text-center transition-colors hover:border-primary/40 hover:bg-accent/30"
        >
          <Upload className="h-6 w-6 text-muted-foreground" strokeWidth={1.6} />
          <span className="text-sm font-medium text-foreground">Choose a file</span>
          <span className="font-mono text-xs text-muted-foreground">.zip · .nii · .nii.gz</span>
          <input
            id="file"
            type="file"
            name="file"
            accept=".zip,.nii,.nii.gz,application/gzip"
            className="mt-2 block w-full text-xs file:mr-3 file:rounded file:border-0 file:bg-muted file:px-3 file:py-1"
          />
        </label>
        <div className="mt-5 flex items-center justify-between gap-4">
          <p className="max-w-xs text-xs text-muted-foreground">
            Demo: the file isn&apos;t stored — a sample case runs through the simulated pipeline.
          </p>
          <Button type="submit">Upload &amp; analyze</Button>
        </div>
      </form>
    </div>
  );
}
