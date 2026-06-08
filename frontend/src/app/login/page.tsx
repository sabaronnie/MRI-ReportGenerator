import { AuthPage } from "@/components/auth-page";

export const metadata = { title: "Sign in · Cervical MRI" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  return <AuthPage error={Boolean(error)} />;
}
