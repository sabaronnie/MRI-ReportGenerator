import { requireRole } from "@/lib/auth/session";
import { uploadAction } from "./actions";
import { Button } from "@/components/ui/button";

export const metadata = { title: "Upload · Cervical MRI" };

export default async function UploadPage() {
  await requireRole(["radiologist", "technologist", "admin"]);
  return (
    <div className="mx-auto max-w-xl px-6 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Upload a scan</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Sagittal T2 cervical MRI — DICOM series (.zip) or NIfTI (.nii.gz).
      </p>
      <form action={uploadAction} className="mt-6 space-y-4">
        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium">File</span>
          <input
            type="file"
            name="file"
            accept=".zip,.nii,.nii.gz,application/gzip"
            className="rounded-md border px-3 py-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-muted file:px-3 file:py-1"
          />
        </label>
        <Button type="submit">Upload &amp; analyze</Button>
        <p className="text-xs text-muted-foreground">
          Demo: the file isn&apos;t stored — a sample case is generated and run through the simulated
          segmentation → measurement → interpretation pipeline.
        </p>
      </form>
    </div>
  );
}
