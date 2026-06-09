import Link from "next/link";
import { AlertTriangle, ChevronRight, ListChecks, ShieldCheck, Upload } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Item, ItemContent, ItemActions, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item";
import type { Role } from "@/lib/api/contract";

export function QuickActions({ role }: { role: Role }) {
  const actions = [
    { title: "Upload scan", description: "Start a new analysis", href: "/upload", icon: Upload, show: role !== "viewer" },
    { title: "Review urgent", description: "Cases flagged urgent", href: "/worklist?triage=urgent&sort=priority", icon: AlertTriangle, show: true },
    { title: "Open worklist", description: "All cervical-spine cases", href: "/worklist", icon: ListChecks, show: true },
    { title: "User management", description: "Manage accounts", href: "/admin", icon: ShieldCheck, show: role === "admin" },
  ].filter((a) => a.show);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Quick actions</CardTitle>
        <CardDescription>Jump straight to the common tasks.</CardDescription>
      </CardHeader>
      <CardContent>
        <ItemGroup className="gap-1">
          {actions.map((a) => {
            const Icon = a.icon;
            return (
              <Item
                key={a.href}
                render={<Link href={a.href} />}
                className="rounded-lg transition-colors hover:bg-accent/50"
              >
                <ItemMedia variant="icon">
                  <Icon />
                </ItemMedia>
                <ItemContent>
                  <ItemTitle>{a.title}</ItemTitle>
                  <ItemDescription>{a.description}</ItemDescription>
                </ItemContent>
                <ItemActions>
                  <ChevronRight className="size-4 text-muted-foreground" />
                </ItemActions>
              </Item>
            );
          })}
        </ItemGroup>
      </CardContent>
    </Card>
  );
}
