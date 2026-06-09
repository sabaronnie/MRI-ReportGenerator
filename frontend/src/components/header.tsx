"use client";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Brand } from "@/components/brand";
import { useScroll } from "@/hooks/use-scroll";
import { Button } from "@/components/ui/button";
import { MobileNav } from "@/components/mobile-nav";

export const navLinks = [
  { label: "Overview", href: "#overview" },
  { label: "How it works", href: "#how" },
  { label: "Safety", href: "#safety" },
];

export function Header() {
  const scrolled = useScroll(10);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 mx-auto w-full max-w-5xl border-transparent border-b md:rounded-xl md:border md:transition-all md:ease-out",
        {
          "border-border bg-background/90 backdrop-blur-sm supports-backdrop-filter:bg-background/60 md:top-2 md:max-w-4xl md:shadow-sm":
            scrolled,
        },
      )}
    >
      <nav
        className={cn(
          "flex h-16 w-full items-center justify-between px-4 md:transition-all md:ease-out",
          { "md:px-3": scrolled },
        )}
      >
        <Link href="/" className="rounded-md p-1">
          <Brand size={32} />
        </Link>
        <div className="hidden items-center gap-1 md:flex">
          {navLinks.map((link) => (
            <Button
              key={link.label}
              size="sm"
              variant="ghost"
              render={<a href={link.href} />}
              nativeButton={false}
            >
              {link.label}
            </Button>
          ))}
          <Button size="sm" className="ml-2" render={<Link href="/login" />} nativeButton={false}>
            Sign in
          </Button>
        </div>
        <MobileNav />
      </nav>
    </header>
  );
}
