"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LogOutIcon } from "lucide-react";
import { logout } from "@/lib/auth/actions";
import { ROLE_LABEL } from "@/lib/auth/users";
import type { Role } from "@/lib/api/contract";

type NavUserProps = { user: { name: string; email?: string; role: Role } };

export function NavUser({ user }: NavUserProps) {
  const initial = user.name.charAt(0).toUpperCase();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            aria-label="Account menu"
            className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          />
        }
      >
        <Avatar className="size-8 cursor-pointer ring-1 ring-inset ring-border transition-shadow hover:ring-primary/40">
          <AvatarFallback className="bg-accent text-xs font-semibold text-accent-foreground">
            {initial}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <div className="flex items-center gap-3 px-2 py-1.5">
          <Avatar className="size-9">
            <AvatarFallback className="bg-accent text-sm font-semibold text-accent-foreground">
              {initial}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <div className="truncate font-medium text-foreground">{user.name}</div>
            <div className="text-xs text-muted-foreground">{ROLE_LABEL[user.role]}</div>
          </div>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          className="cursor-pointer"
          onClick={() => logout()}
        >
          <LogOutIcon />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
