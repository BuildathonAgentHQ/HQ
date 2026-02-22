"use client";

import type { LucideIcon } from "lucide-react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRepo } from "@/context/repo-context";
import { GitFork, ChevronDown } from "lucide-react";
import { useState } from "react";

interface PageHeaderProps {
    icon: LucideIcon;
    title: string;
    description?: string;
    onRefresh?: () => void;
    refreshing?: boolean;
}

export function PageHeader({ icon: Icon, title, description, onRefresh, refreshing }: PageHeaderProps) {
    const { repos, selectedRepo, setSelectedRepo } = useRepo();
    const [open, setOpen] = useState(false);

    return (
        <div className="flex items-center justify-between shrink-0 mb-6">
            <div>
                <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <Icon className="h-7 w-7 text-indigo-400" />
                    {title}
                </h1>
                {description && (
                    <p className="text-sm text-muted-foreground mt-1">{description}</p>
                )}
            </div>
            <div className="flex items-center gap-3">
                {/* Repo Selector */}
                {repos.length > 0 && (
                    <div className="relative">
                        <button
                            onClick={() => setOpen(!open)}
                            className="inline-flex items-center gap-2 rounded-lg border border-border/40 bg-card/60 backdrop-blur px-3 py-1.5 text-sm font-medium text-slate-200 hover:bg-white/10 hover:text-white transition-colors min-w-[180px]"
                        >
                            <GitFork className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                            <span className="truncate max-w-[200px]">
                                {selectedRepo?.full_name ?? "Select repo"}
                            </span>
                            <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground ml-auto transition-transform ${open ? "rotate-180" : ""}`} />
                        </button>
                        {open && (
                            <div className="absolute top-full right-0 mt-1 z-50 min-w-[240px] rounded-lg border border-border/40 bg-[#0d1117] shadow-xl shadow-black/40 py-1 animate-fade-in">
                                {repos.map((repo) => (
                                    <button
                                        key={repo.id}
                                        onClick={() => {
                                            setSelectedRepo(repo);
                                            setOpen(false);
                                        }}
                                        className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors ${repo.id === selectedRepo?.id
                                            ? "bg-indigo-500/15 text-indigo-300"
                                            : "text-slate-300 hover:bg-white/5 hover:text-white"
                                            }`}
                                    >
                                        <GitFork className="h-3 w-3 shrink-0 text-muted-foreground" />
                                        <span className="truncate flex-1">{repo.full_name}</span>
                                        {repo.health_score !== null && (
                                            <span className={`text-[10px] font-bold tabular-nums ${repo.health_score > 80 ? "text-emerald-400" : repo.health_score > 50 ? "text-amber-400" : "text-red-400"
                                                }`}>
                                                {repo.health_score}
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Refresh Button */}
                {onRefresh && (
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onRefresh}
                        disabled={refreshing}
                        className="h-8 px-2.5 text-muted-foreground hover:text-white"
                    >
                        <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                    </Button>
                )}
            </div>
        </div>
    );
}
