import { requireRole } from "@/lib/auth/session";
import { DEMO_USERS, ROLE_LABEL } from "@/lib/auth/users";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { BackButton } from "@/components/back-button";

export const metadata = { title: "Admin · Cervical MRI" };
const HEAD = "text-xs font-medium uppercase tracking-wider text-muted-foreground";

export default async function AdminPage() {
  await requireRole(["admin"]);
  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-4">
        <BackButton label="Worklist" />
      </div>
      <h1 className="font-serif text-[28px] font-semibold tracking-tight">User management</h1>
      <p className="mt-2 text-sm text-muted-foreground">Demo directory — wired to a real user store later.</p>
      <div className="mt-6 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className={HEAD}>Name</TableHead>
              <TableHead className={HEAD}>Email</TableHead>
              <TableHead className={HEAD}>Role</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {DEMO_USERS.map((u) => (
              <TableRow key={u.email} className="hover:bg-accent/30">
                <TableCell className="font-medium">{u.name}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{u.email}</TableCell>
                <TableCell>
                  <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                    {ROLE_LABEL[u.role]}
                  </span>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
