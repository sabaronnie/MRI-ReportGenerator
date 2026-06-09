import type { ReactNode } from "react";
import { LayoutDashboard, ListChecks, ShieldCheck, Upload } from "lucide-react";
import type { Role } from "@/lib/api/contract";

export type SidebarNavItem = {
  title: string;
  path: string;
  icon: ReactNode;
  /** If set, only these roles see the item. */
  roles?: Role[];
};

/** Primary navigation. */
export const navItems: SidebarNavItem[] = [
  { title: "Dashboard", path: "/dashboard", icon: <LayoutDashboard /> },
  { title: "Worklist", path: "/worklist", icon: <ListChecks /> },
  {
    title: "Upload",
    path: "/upload",
    icon: <Upload />,
    roles: ["radiologist", "technologist", "admin"],
  },
  { title: "Admin", path: "/admin", icon: <ShieldCheck />, roles: ["admin"] },
];

/** Human title for the current route, shown in the app header. */
export function pageTitleFor(pathname: string): string {
  if (pathname.startsWith("/dashboard")) return "Dashboard";
  if (pathname.startsWith("/worklist")) return "Worklist";
  if (pathname.startsWith("/cases")) return "Case report";
  if (pathname.startsWith("/upload")) return "Upload scan";
  if (pathname.startsWith("/admin")) return "Admin";
  return "Cervical MRI";
}
