"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Terminal,
  GitPullRequest,
  GitFork,
  Shield,
  HeartPulse,
  DollarSign,
  Zap,
  Settings,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { KnowledgeSidebar } from "@/components/knowledge-sidebar";
import { cn } from "@/lib/utils";
import { useWebSocket } from "@/hooks/use-websocket";
import { WS_URL, API_BASE_URL } from "@/lib/constants";

const NAV_ITEMS = [
  { label: "Repositories", href: "/repos", icon: GitFork },
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Agent Console", href: "/console", icon: Terminal },
  { label: "PR Reviews", href: "/pr-radar", icon: GitPullRequest },
  { label: "Coverage Map", href: "/coverage", icon: Shield },
  { label: "Repo Health", href: "/repo-health", icon: HeartPulse },
  { label: "FinOps", href: "/finops", icon: DollarSign },
] as const;

interface RepoConfig {
  repo_name: string;
  repo_url: string;
  repo_owner: string;
}

export function Sidebar() {
  const pathname = usePathname();
  const { isConnected } = useWebSocket(WS_URL);
  const [repo, setRepo] = useState<RepoConfig | null>(null);

  useEffect(() => {
    fetch(`${API_BASE_URL}/config/repo`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => data && setRepo(data))
      .catch(() => { });
  }, []);

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border/40 bg-[#0B1120]">
      {/* ── Brand ────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 px-6 py-5">
        <div className="h-10 w-10 rounded-lg overflow-hidden shadow-lg shadow-indigo-500/20 shrink-0">
          <Image
            src="/logo.png"
            alt="Agent HQ"
            width={80}
            height={80}
            className="h-full w-full object-cover scale-[1.8]"
          />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white">
            Agent HQ
          </h1>
          <p className="text-[11px] text-muted-foreground">Command Centre</p>
        </div>
      </div>

      <Separator className="opacity-20" />

      {/* ── Navigation ───────────────────────────────────────── */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const isActive = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
                isActive
                  ? "bg-indigo-500/15 text-indigo-400"
                  : "text-slate-400 hover:bg-white/5 hover:text-white",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}

        <Separator className="opacity-10 my-2" />

        {/* Knowledge Base — opens Sheet */}
        <KnowledgeSidebar />
      </nav>

      {/* ── Footer ───────────────────────────────────────────── */}
      <div className="border-t border-border/30 px-6 py-4 space-y-3">
        {/* ── Target repo link ────────── */}

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span
            className={cn(
              "inline-block h-2 w-2 rounded-full",
              isConnected
                ? "bg-emerald-500 shadow-[0_0_6px_theme(colors.emerald.500)]"
                : "bg-red-500 shadow-[0_0_6px_theme(colors.red.500)]",
            )}
          />
          {isConnected ? "Connected" : "Disconnected"}
        </div>
        <div className="flex items-center justify-between">
          <p className="text-[10px] text-muted-foreground/60">v0.1.0</p>
          <Settings className="h-3.5 w-3.5 text-muted-foreground/40 cursor-pointer hover:text-white transition-colors" />
        </div>
      </div>
    </aside>
  );
}
