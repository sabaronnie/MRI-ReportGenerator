import { redirect } from "next/navigation";
import { AuthPage } from "@/components/auth-page";
import { getSession } from "@/lib/auth/session";

export const metadata = { title: "Sign in · Cervical MRI" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  // Already signed in → skip the login page entirely (this is what was showing
  // the app header on top of the login screen).
  if (await getSession()) redirect("/worklist");
  const { error } = await searchParams;
  return <AuthPage error={Boolean(error)} />;
}
