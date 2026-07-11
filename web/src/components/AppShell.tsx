"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  FileSearch,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import clsx from "clsx";
import { User } from "@/lib/api";
import { getStoredUser, logout } from "@/lib/auth";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/extract", label: "Extract", icon: FileSearch },
  { href: "/prompts", label: "AI prompts", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setUser(getStoredUser());
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const NavLinks = ({ onNavigate }: { onNavigate?: () => void }) => (
    <>
      {nav.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={clsx(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition",
              active ? "bg-white/15 text-white" : "text-indigo-100 hover:bg-white/10"
            )}
          >
            <Icon className="h-4 w-4" />
            {item.label}
          </Link>
        );
      })}
    </>
  );

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="hidden w-64 flex-shrink-0 flex-col bg-brand-900 text-white md:flex">
        <div className="flex items-center gap-3 border-b border-white/10 px-6 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600">
            <Mail className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold">Email Agent</p>
            <p className="text-xs text-indigo-200">AI moving quotes</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-4">
          <NavLinks />
        </nav>
        <div className="border-t border-white/10 p-4">
          <p className="truncate text-sm font-medium" suppressHydrationWarning>
            {user?.name || user?.email || "…"}
          </p>
          <p className="truncate text-xs text-indigo-200" suppressHydrationWarning>
            {user?.email || ""}
          </p>
          <button
            onClick={logout}
            className="mt-3 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-indigo-100 hover:bg-white/10"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-surface-border bg-white px-4 py-3 md:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
              <Mail className="h-4 w-4" />
            </div>
            <span className="text-sm font-semibold text-slate-900">Email Agent</span>
          </div>
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Menu"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </header>

        {mobileOpen ? (
          <div className="border-b border-surface-border bg-brand-900 p-3 md:hidden">
            <nav className="space-y-1">
              <NavLinks onNavigate={() => setMobileOpen(false)} />
            </nav>
          </div>
        ) : null}

        <main className="flex-1 overflow-auto">
          <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">{children}</div>
        </main>
      </div>
    </div>
  );
}
