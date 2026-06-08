"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ROLES, ROLE_LABEL } from "@/lib/auth/users";
import { createUserAction } from "@/app/(app)/admin/actions";

const SELECT =
  "h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

export function CreateUserDialog() {
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    start(async () => {
      const res = await createUserAction(fd);
      if (res.ok) {
        toast.success("User created");
        setOpen(false);
        form.reset();
      } else {
        toast.error(res.error ?? "Could not create user");
      }
    });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button size="sm" />}>
        <UserPlus />
        Create user
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="cu-name">Name</Label>
            <Input id="cu-name" name="name" required autoComplete="off" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cu-email">Email</Label>
            <Input id="cu-email" name="email" type="email" required autoComplete="off" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cu-role">Role</Label>
            <select id="cu-role" name="role" defaultValue="radiologist" className={SELECT}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cu-pw">Initial password</Label>
            <Input id="cu-pw" name="password" type="password" minLength={8} required autoComplete="new-password" />
            <p className="text-xs text-muted-foreground">At least 8 characters.</p>
          </div>
          <DialogFooter>
            <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
            <Button type="submit" disabled={pending}>
              {pending ? "Creating…" : "Create user"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
