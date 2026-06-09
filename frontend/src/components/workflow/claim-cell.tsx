"use client";

import { useTransition } from "react";
import { toast } from "sonner";
import { UserPlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { claimAction, releaseAction } from "@/lib/actions/workflow";
import type { Assignment } from "@/lib/api/workflow";

/** Worklist/case assignee control: shows the assignee (with a Release if it's you)
 * or a Claim button when unassigned. Live-mode only — hidden otherwise. */
export function ClaimCell({
  caseId,
  assignment,
  meId,
}: {
  caseId: string;
  assignment: Assignment | null;
  meId: string;
}) {
  const [pending, start] = useTransition();

  function act(fn: () => Promise<{ ok: boolean; error?: string }>, ok: string) {
    start(async () => {
      const res = await fn();
      if (res.ok) toast.success(ok);
      else toast.error(res.error ?? "Action failed");
    });
  }

  if (!assignment) {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={pending}
        onClick={() => act(() => claimAction(caseId), "Case claimed")}
      >
        <UserPlus />
        Claim
      </Button>
    );
  }

  const mine = assignment.assignee_id === meId;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="grid size-6 place-items-center rounded-full bg-accent text-[11px] font-semibold text-accent-foreground">
        {assignment.assignee_name.charAt(0)}
      </span>
      <span className={`text-sm ${mine ? "font-medium text-foreground" : "text-muted-foreground"}`}>
        {mine ? "You" : assignment.assignee_name}
      </span>
      {mine ? (
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label="Release case"
          disabled={pending}
          onClick={() => act(() => releaseAction(caseId), "Case released")}
        >
          <X />
        </Button>
      ) : null}
    </span>
  );
}
