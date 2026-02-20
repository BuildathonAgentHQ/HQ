"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    Terminal,
    GitPullRequest,
    Shield,
    HeartPulse,
    DollarSign,
    Zap,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
    { label: "Dashboard", href: "/", icon: LayoutDashboard },
    { label: "Agent Console", href: "/console", icon: Terminal },
    { label: "PR Radar", href: "/pr-radar", icon: GitPullRequest },
    { label: "Coverage", href: "/coverage", icon: Shield },
    { label: "Repo Health", href: "/repo-health", icon: HeartPulse },
    { label: "FinOps", href: "/finops", icon: DollarSign },
] as const;

interface ConnectionDotProps {
    connected: boolean;
}

function ConnectionDot({ connected }: ConnectionDotProps) {
    return (
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
            <span
                className={cn(
                    "inline-block h-2 w-2 rounded-full",
                    connected
                        ? "bg-emerald-500 shadow-[0_0_6px_theme(colors.emerald.500)]"
                        : "bg-red-500 shadow-[0_0_6px_theme(colors.red.500)]"
                )}
            />
            {connected ? "Connected" : "Disconnected"}
        </span>
    );
}

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border/40 bg-[#0B1120]">
            {/* ── Brand ────────────────────────────────────────────── */}
            <div className="flex items-center gap-3 px-6 py-5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-400">
                    <Zap className="h-5 w-5 text-white" />
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
                                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                            )}
                        >
                            <Icon className="h-4 w-4 shrink-0" />
                            {label}
                        </Link>
                    );
                })}
            </nav>

            {/* ── Footer ───────────────────────────────────────────── */}
            <div className="border-t border-border/30 px-6 py-4 space-y-2">
                <ConnectionDot connected={false} />
                <p className="text-[10px] text-muted-foreground/60">v0.1.0</p>
            </div>
        </aside>
    );
}
