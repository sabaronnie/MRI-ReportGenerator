"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  volumeUrl: string;
  maskUrl?: string;
};

type LoadState = "loading" | "ready" | "error";

/**
 * Interactive cervical-MRI viewer (NiiVue / WebGL).
 * - Loads the base T2 volume + the TotalSpineSeg multi-label mask overlay (mock /samples or EEP routes).
 * - Volume and mask load INDEPENDENTLY, so the viewer renders whatever is available (graceful degradation).
 * - Native interactions: scroll = slice, drag = pan/contrast, wheel = zoom. NiiVue reads the affine from the header.
 * - Per-label colormap (amber vertebrae / blue discs / cord-canal) is a polish-pass item; first pass uses
 *   a categorical colormap. NiiVue is imported lazily inside the effect so it never runs during SSR.
 */
export function NiivueViewer({ volumeUrl, maskUrl }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nvRef = useRef<any>(null);
  const maskIdxRef = useRef<number>(-1);
  const [state, setState] = useState<LoadState>("loading");
  const [hasOverlay, setHasOverlay] = useState(false);
  const [showOverlay, setShowOverlay] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { Niivue, NVImage } = await import("@niivue/niivue");
        if (cancelled || !canvasRef.current) return;
        const nv = new Niivue({ backColor: [0, 0, 0, 1], show3Dcrosshair: true, dragAndDropEnabled: false });
        nvRef.current = nv;
        maskIdxRef.current = -1;
        await nv.attachToCanvas(canvasRef.current);

        let loaded = 0;
        try {
          nv.addVolume(await NVImage.loadFromUrl({ url: volumeUrl }));
          loaded++;
        } catch (e) {
          console.warn("NiiVue: base volume not loaded", e);
        }
        if (maskUrl) {
          try {
            nv.addVolume(await NVImage.loadFromUrl({ url: maskUrl, colormap: "actc", opacity: 0.5 }));
            maskIdxRef.current = nv.volumes.length - 1;
            loaded++;
            if (!cancelled) setHasOverlay(true);
          } catch (e) {
            console.warn("NiiVue: segmentation mask not loaded", e);
          }
        }
        if (cancelled) return;
        if (loaded === 0) {
          setState("error");
          return;
        }
        nv.setSliceType(nv.sliceTypeMultiplanar);
        setState("ready");
      } catch (err) {
        console.error("NiiVue init failed:", err);
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [volumeUrl, maskUrl]);

  useEffect(() => {
    const nv = nvRef.current;
    if (nv && maskIdxRef.current >= 0) {
      try {
        nv.setOpacity(maskIdxRef.current, showOverlay ? 0.5 : 0);
      } catch {
        /* older API — ignore */
      }
    }
  }, [showOverlay]);

  const setView = (view: "sag" | "multi" | "render") => {
    const nv = nvRef.current;
    if (!nv) return;
    const t =
      view === "sag" ? nv.sliceTypeSagittal : view === "render" ? nv.sliceTypeRender : nv.sliceTypeMultiplanar;
    if (t !== undefined) nv.setSliceType(t);
  };

  return (
    <div className="space-y-2">
      <div className="relative aspect-square overflow-hidden rounded-lg border bg-black">
        <canvas ref={canvasRef} className="h-full w-full" />
        {state === "loading" && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-zinc-400">
            Loading volume…
          </div>
        )}
        {state === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 p-4 text-center text-sm text-zinc-400">
            <p>Volume not available.</p>
            <p className="text-xs">
              Add a <code>.nii.gz</code> to <code>public/samples/</code> (mock) or wire the EEP{" "}
              <code>/volume</code> route.
            </p>
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button className="rounded-md border border-border px-2.5 py-1.5 transition-all hover:-translate-y-px hover:bg-muted active:scale-95" onClick={() => setView("sag")}>
          Sagittal
        </button>
        <button className="rounded-md border border-border px-2.5 py-1.5 transition-all hover:-translate-y-px hover:bg-muted active:scale-95" onClick={() => setView("multi")}>
          Multiplanar
        </button>
        <button className="rounded-md border border-border px-2.5 py-1.5 transition-all hover:-translate-y-px hover:bg-muted active:scale-95" onClick={() => setView("render")}>
          3D
        </button>
        {hasOverlay && (
          <button
            className="ml-auto rounded-md border border-border px-2.5 py-1.5 transition-all hover:-translate-y-px hover:bg-muted active:scale-95"
            onClick={() => setShowOverlay((v) => !v)}
          >
            {showOverlay ? "Hide" : "Show"} segmentation
          </button>
        )}
      </div>
    </div>
  );
}
