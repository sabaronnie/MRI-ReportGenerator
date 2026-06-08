"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { addAddendumAction } from "@/lib/actions/workflow";
import type { Addendum } from "@/lib/api/workflow";

function fmt(iso: string): string {
  return iso.replace("T", " ").slice(0, 16) + " UTC";
}

/** Report addenda: timestamped notes appended after the report (typically post
 * sign-off). Radiologists can add; everyone sees the trail. */
export function AddendaSection({
  caseId,
  addenda,
  canAdd,
}: {
  caseId: string;
  addenda: Addendum[];
  canAdd: boolean;
}) {
  const [text, setText] = useState("");
  const [pending, start] = useTransition();

  function submit() {
    const t = text.trim();
    if (!t) return;
    start(async () => {
      const res = await addAddendumAction(caseId, t);
      if (res.ok) {
        toast.success("Addendum added");
        setText("");
      } else {
        toast.error(res.error ?? "Could not add addendum");
      }
    });
  }

  if (!addenda.length && !canAdd) return null;

  return (
    <section className="mt-6">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Addenda
      </h2>
      <div className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm">
        {addenda.length ? (
          addenda.map((a) => (
            <div key={a.id} className="border-l-2 border-primary/40 pl-3">
              <p className="text-sm text-foreground">{a.text}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {a.author_name} · {fmt(a.created_at)}
              </p>
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">No addenda yet.</p>
        )}
        {canAdd ? (
          <div className="space-y-2 border-t border-border pt-3">
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Add an addendum to this report…"
              rows={2}
            />
            <div className="flex justify-end">
              <Button size="sm" disabled={pending || !text.trim()} onClick={submit}>
                {pending ? "Adding…" : "Add addendum"}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
