import { AppShell } from "@/components/app-shell";
import { requireSession } from "@/lib/auth/session";

/** Layout for all authenticated pages: guards the session and renders the
 * sidebar app shell around the page content. */
export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireSession();
  return <AppShell user={user}>{children}</AppShell>;
}
