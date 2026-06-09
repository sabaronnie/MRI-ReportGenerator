"use client";

import { useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { signOffAction } from "@/app/(app)/cases/[id]/actions";

export function SignOffButton({ caseId }: { caseId: string }) {
  const [pending, start] = useTransition();
  return (
    <Button
      size="sm"
      disabled={pending}
      onClick={() =>
        start(async () => {
          const fd = new FormData();
          fd.set("caseId", caseId);
          await signOffAction(fd);
          toast.success("Report signed off", { description: "Case marked as reviewed." });
        })
      }
    >
      {pending ? "Signing…" : "Sign off"}
    </Button>
  );
}
