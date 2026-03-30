"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Video, Bot, Key, Webhook, BarChart3,
  Settings, LogOut, Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview",  icon: LayoutDashboard },
  { href: "/rooms",     label: "Rooms",     icon: Video },
  { href: "/agents",    label: "Agents",    icon: Bot },
  { href: "/keys",      label: "API Keys",  icon: Key },
  { href: "/webhooks",  label: "Webhooks",  icon: Webhook },
  { href: "/usage",     label: "Usage",     icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();

  function handleLogout() {
    document.cookie = "sense_api_key=; path=/; max-age=0";
    window.location.href = "/login";
  }

  return (
    <aside className="w-60 flex-shrink-0 bg-gray-950 flex flex-col h-screen fixed left-0 top-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-gray-800">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-sense-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-white font-semibold text-sm leading-tight">Sense Console</div>
            <div className="text-gray-500 text-xs">Developer Dashboard</div>
          </div>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-sense-600 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800",
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom actions */}
      <div className="px-3 py-4 border-t border-gray-800 space-y-0.5">
        <Link
          href="/settings"
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
        >
          <Settings className="w-4 h-4" />
          Settings
        </Link>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-gray-800 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
