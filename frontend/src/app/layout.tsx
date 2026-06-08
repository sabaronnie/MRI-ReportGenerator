import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Serif, IBM_Plex_Mono } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
const plexSerif = IBM_Plex_Serif({
  variable: "--font-plex-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Cervical MRI — Worklist",
  description: "Cervical-spine MRI triage and structured reporting.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${plexSans.variable} ${plexSerif.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-svh bg-background text-foreground antialiased">
        <TooltipProvider>{children}</TooltipProvider>
        <Toaster richColors position="top-center" toastOptions={{ style: { fontFamily: "var(--font-plex-sans)" } }} />
      </body>
    </html>
  );
}
