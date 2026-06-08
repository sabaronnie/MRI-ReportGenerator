import type { ReactNode } from "react";
import { ListChecks, ShieldCheck } from "lucide-react";
import type { Role } from "@/lib/api/contract";

export type SidebarNavItem = {
  title: string;
  path: string;
  icon: ReactNode;
  /** If set, only these roles see the item. */
  roles?: Role[];
};

/** Primary navigation. "Upload scan" is the prominent CTA in the sidebar, so it
 * is intentionally not duplicated here. */
export const navItems: SidebarNavItem[] = [
  { title: "Worklist", path: "/worklist", icon: <ListChecks /> },
  { title: "Admin", path: "/admin", icon: <ShieldCheck />, roles: ["admin"] },
];

/** Human title for the current route, shown in the app header. */
export function pageTitleFor(pathname: string): string {
  if (pathname.startsWith("/worklist")) return "Worklist";
  if (pathname.startsWith("/cases")) return "Case report";
  if (pathname.startsWith("/upload")) return "Upload scan";
  if (pathname.startsWith("/admin")) return "Admin";
  return "Cervical MRI";
}
