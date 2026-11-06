"use client";

import { LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { ThemeToggle } from "@/components/common/ThemeToggle";
import { NotificationBell } from "@/features/notifications/components/NotificationBell";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import type { NavItem } from "@/lib/navigation";
import { ROLE_LABELS } from "@/lib/roles";
import { cn } from "@/lib/utils";

function NavLinks({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="space-y-1 p-3">
      {items.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden /> {label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Responsive shell: fixed sidebar on md+, slide-over drawer on mobile. Phase 12 refines the visual design. */
export function AppShell({ title, nav, children }: { title: string; nav: NavItem[]; children: ReactNode }) {
  const { user, can, logout } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const items = nav.filter((item) => !item.permission || can(item.permission));

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 border-r bg-card md:block">
        <div className="flex h-14 items-center border-b px-4 font-semibold tracking-tight">
          <span className="truncate">{title}</span>
        </div>
        <NavLinks items={items} />
      </aside>

      {drawerOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button type="button" aria-label="Close menu" className="absolute inset-0 bg-black/50" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-64 bg-card shadow-lg">
            <div className="flex h-14 items-center justify-between border-b px-4 font-semibold tracking-tight">
              <span className="truncate">{title}</span>
              <Button variant="ghost" size="icon" aria-label="Close menu" onClick={() => setDrawerOpen(false)}>
                <X className="size-4" />
              </Button>
            </div>
            <NavLinks items={items} onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      ) : null}

      <div className="md:pl-60">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b bg-card/95 px-4 backdrop-blur">
          <Button variant="outline" size="icon" className="md:hidden" aria-label="Open menu" onClick={() => setDrawerOpen(true)}>
            <Menu className="size-4" />
          </Button>
          <div className="ml-auto flex items-center gap-3">
            {user ? (
              <div className="hidden text-right text-sm leading-tight sm:block">
                <div className="font-medium">
                  {user.first_name} {user.last_name}
                </div>
                <div className="text-muted-foreground">{ROLE_LABELS[user.role]}</div>
              </div>
            ) : null}
            {user && user.role !== "SUPER_ADMIN" ? <NotificationBell /> : null}
            <ThemeToggle />
            <Button variant="outline" size="sm" onClick={() => void logout()}>
              <LogOut className="size-4" /> <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </header>
        <main className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
