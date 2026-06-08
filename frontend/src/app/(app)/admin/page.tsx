import { requireRole } from "@/lib/auth/session";
import { listUsers } from "@/lib/api/admin";
import { UsersTable } from "@/components/admin/users-table";
import { CreateUserDialog } from "@/components/admin/create-user-dialog";

export const metadata = { title: "Admin · Cervical MRI" };

export default async function AdminPage() {
  await requireRole(["admin"]);
  const users = await listUsers();
  return (
    <div className="mx-auto w-full max-w-4xl">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-[28px] font-semibold tracking-tight">User management</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {users.length} {users.length === 1 ? "user" : "users"} · create accounts, set roles, reset passwords.
          </p>
        </div>
        <CreateUserDialog />
      </div>
      <UsersTable users={users} />
    </div>
  );
}
