"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE_URL } from "@/lib/constants";
import type { Repository } from "@/lib/types";
import { GitFork, ChevronDown } from "lucide-react";

interface RepoSelectorProps {
    selectedRepoId: string | null;
    onRepoChange: (repoId: string, repo: Repository) => void;
}

export function RepoSelector({ selectedRepoId, onRepoChange }: RepoSelectorProps) {
    const [repos, setRepos] = useState<Repository[]>([]);
    const [open, setOpen] = useState(false);

    useEffect(() => {
        fetch(`${API_BASE_URL}/repos`)
            .then((r) => r.json())
            .then((data: Repository[]) => {
                setRepos(data);
                // Auto-select first repo if none selected
                if (!selectedRepoId && data.length > 0) {
                    onRepoChange(data[0].id, data[0]);
                }
            })
            .catch(() => { });
    }, []);  // eslint-disable-line react-hooks/exhaustive-deps

    const selected = repos.find((r) => r.id === selectedRepoId);

    if (repos.length === 0) return null;

    return (
        <div className="relative">
            <button
                onClick={() => setOpen(!open)}
                className="inline-flex items-center gap-2 rounded-lg border border-border/40 bg-card/60 backdrop-blur px-3 py-1.5 text-sm font-medium text-slate-200 hover:bg-white/10 hover:text-white transition-colors min-w-[180px]"
            >
                <GitFork className="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                <span className="truncate max-w-[200px]">
                    {selected?.full_name ?? "Select repo"}
                </span>
                <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground ml-auto transition-transform ${open ? "rotate-180" : ""}`} />
            </button>

            {open && (
                <div className="absolute top-full left-0 mt-1 z-50 min-w-[240px] rounded-lg border border-border/40 bg-[#0d1117] shadow-xl shadow-black/40 py-1 animate-fade-in">
                    {repos.map((repo) => (
                        <button
                            key={repo.id}
                            onClick={() => {
                                onRepoChange(repo.id, repo);
                                setOpen(false);
                            }}
                            className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 transition-colors ${repo.id === selectedRepoId
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
    );
}
