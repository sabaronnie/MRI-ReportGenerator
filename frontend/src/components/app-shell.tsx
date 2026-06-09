import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { AppHeader } from "@/components/app-header";
import { AppSidebar } from "@/components/app-sidebar";
import type { Role } from "@/lib/api/contract";

type AppShellProps = {
  user: { name: string; email?: string; role: Role };
  children: React.ReactNode;
};

export function AppShell({ user, children }: AppShellProps) {
  return (
    <SidebarProvider>
      <AppSidebar role={user.role} />
      <SidebarInset className="p-4 md:p-6">
        <AppHeader user={user} />
        <div className="flex flex-1 flex-col gap-4">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
