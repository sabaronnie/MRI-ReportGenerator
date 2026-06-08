"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { KeyRound, Trash2, UserCheck, UserX } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { ROLES, ROLE_LABEL, type ManagedUser } from "@/lib/auth/users";
import type { Role } from "@/lib/api/contract";
import {
  deleteUserAction,
  resetPasswordAction,
  setActiveAction,
  setRoleAction,
} from "@/app/(app)/admin/actions";

const HEAD = "text-xs font-medium uppercase tracking-wider text-muted-foreground";
const SELECT =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50";

export function UsersTable({ users }: { users: ManagedUser[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className={HEAD}>Name</TableHead>
            <TableHead className={HEAD}>Email</TableHead>
            <TableHead className={HEAD}>Role</TableHead>
            <TableHead className={HEAD}>Status</TableHead>
            <TableHead className={`${HEAD} text-right`}>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((u) => (
            <UserRow key={u.id} user={u} />
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function UserRow({ user }: { user: ManagedUser }) {
  const [pending, start] = useTransition();

  function run(fn: () => Promise<{ ok: boolean; error?: string }>, ok: string) {
    start(async () => {
      const res = await fn();
      if (res.ok) toast.success(ok);
      else toast.error(res.error ?? "Action failed");
    });
  }

  return (
    <TableRow className={user.active ? "" : "opacity-60"}>
      <TableCell className="font-medium">{user.name}</TableCell>
      <TableCell className="font-mono text-xs text-muted-foreground">{user.email}</TableCell>
      <TableCell>
        <select
          aria-label={`Role for ${user.name}`}
          className={SELECT}
          defaultValue={user.role}
          disabled={pending}
          onChange={(e) => run(() => setRoleAction(user.id, e.target.value as Role), "Role updated")}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABEL[r]}
            </option>
          ))}
        </select>
      </TableCell>
      <TableCell>
        {user.active ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
            <span className="size-1.5 rounded-full bg-emerald-500" /> Active
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-muted-foreground/50" /> Disabled
          </span>
        )}
      </TableCell>
      <TableCell>
        <div className="flex items-center justify-end gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            disabled={pending}
            onClick={() =>
              run(() => setActiveAction(user.id, !user.active), user.active ? "User disabled" : "User enabled")
            }
          >
            {user.active ? <UserX /> : <UserCheck />}
            {user.active ? "Disable" : "Enable"}
          </Button>
          <ResetPasswordDialog user={user} />
          <DeleteUserButton user={user} />
        </div>
      </TableCell>
    </TableRow>
  );
}

function ResetPasswordDialog({ user }: { user: ManagedUser }) {
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const password = String(new FormData(form).get("password") ?? "");
    start(async () => {
      const res = await resetPasswordAction(user.id, password);
      if (res.ok) {
        toast.success("Password reset");
        setOpen(false);
        form.reset();
      } else {
        toast.error(res.error ?? "Could not reset password");
      }
    });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="ghost" size="sm" aria-label={`Reset password for ${user.name}`} />}>
        <KeyRound />
      </DialogTrigger>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Reset password</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Set a new password for <span className="font-medium text-foreground">{user.name}</span>.
          </p>
          <div className="space-y-1.5">
            <Label htmlFor={`pw-${user.id}`}>New password</Label>
            <Input id={`pw-${user.id}`} name="password" type="password" minLength={8} required autoComplete="new-password" />
          </div>
          <DialogFooter>
            <DialogClose render={<Button type="button" variant="outline" />}>Cancel</DialogClose>
            <Button type="submit" disabled={pending}>
              {pending ? "Saving…" : "Reset password"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function DeleteUserButton({ user }: { user: ManagedUser }) {
  const [pending, start] = useTransition();
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={
          <Button variant="ghost" size="sm" className="text-destructive" aria-label={`Delete ${user.name}`} />
        }
      >
        <Trash2 />
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete {user.name}?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently removes the account ({user.email}). This cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={pending}
            onClick={() =>
              start(async () => {
                const res = await deleteUserAction(user.id);
                if (res.ok) toast.success("User deleted");
                else toast.error(res.error ?? "Could not delete user");
              })
            }
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
