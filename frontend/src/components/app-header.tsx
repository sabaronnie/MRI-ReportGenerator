import { getSession } from "@/lib/auth/session";
import { HeaderNav } from "./header-nav";

export async function AppHeader() {
  const session = await getSession();
  const items = session
    ? [
        { href: "/worklist", label: "Worklist" },
        ...(session.role !== "viewer" ? [{ href: "/upload", label: "Upload" }] : []),
        ...(session.role === "admin" ? [{ href: "/admin", label: "Admin" }] : []),
      ]
    : [];
  return <HeaderNav user={session ? { name: session.name, role: session.role } : null} items={items} />;
}
