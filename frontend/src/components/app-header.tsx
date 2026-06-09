"use client";

import { usePathname } from "next/navigation";
import { Separator } from "@/components/ui/separator";
import { CustomSidebarTrigger } from "@/components/custom-sidebar-trigger";
import { NavUser } from "@/components/nav-user";
import { pageTitleFor } from "@/components/app-shared";
import type { Role } from "@/lib/api/contract";

type AppHeaderProps = { user: { name: string; email?: string; role: Role } };

export function AppHeader({ user }: AppHeaderProps) {
  const pathname = usePathname();
  const title = pageTitleFor(pathname);
  return (
    <header className="mb-6 flex h-10 items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <CustomSidebarTrigger />
        <Separator
          orientation="vertical"
          className="mr-1 h-4 data-[orientation=vertical]:self-center"
        />
        <span className="font-serif text-base font-semibold tracking-tight text-foreground">
          {title}
        </span>
      </div>
      <NavUser user={user} />
    </header>
  );
}
