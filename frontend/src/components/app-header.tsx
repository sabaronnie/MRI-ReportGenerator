import { getSession } from "@/lib/auth/session";
import { HeaderNav } from "./header-nav";

export async function AppHeader() {
  const session = await getSession();
  // No session ⇒ the login page (all protected routes redirect there). Hide the
  // global header so the auth page can render full-screen.
  if (!session) return null;
  const items = [
    { href: "/worklist", label: "Worklist" },
    ...(session.role !== "viewer" ? [{ href: "/upload", label: "Upload" }] : []),
    ...(session.role === "admin" ? [{ href: "/admin", label: "Admin" }] : []),
  ];
  return <HeaderNav user={{ name: session.name, role: session.role }} items={items} />;
}
