"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brand } from "@/components/brand";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { navItems } from "@/components/app-shared";
import type { Role } from "@/lib/api/contract";

export function AppSidebar({ role }: { role: Role }) {
  const pathname = usePathname();
  const isActive = (path: string) =>
    path === "/worklist"
      ? pathname.startsWith("/worklist") || pathname.startsWith("/cases")
      : pathname.startsWith(path);

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader className="h-14 justify-center">
        <Link
          href="/worklist"
          className="flex items-center px-1 group-data-[collapsible=icon]:justify-center"
        >
          <Brand size={30} className="group-data-[collapsible=icon]:[&>span:last-child]:hidden" />
        </Link>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            {navItems
              .filter((i) => !i.roles || i.roles.includes(role))
              .map((item) => (
                <SidebarMenuItem key={item.path}>
                  <SidebarMenuButton
                    isActive={isActive(item.path)}
                    tooltip={item.title}
                    render={<Link href={item.path} />}
                  >
                    {item.icon}
                    <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <div className="px-2 py-1 text-[10px] text-muted-foreground group-data-[collapsible=icon]:hidden">
          Cervical MRI Reporting · demo
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
