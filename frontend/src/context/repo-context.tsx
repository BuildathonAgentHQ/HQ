"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { API_BASE_URL } from "@/lib/constants";
import type { Repository } from "@/lib/types";

interface RepoContextValue {
    repos: Repository[];
    selectedRepo: Repository | null;
    selectedRepoId: string | null;
    setSelectedRepo: (repo: Repository) => void;
    loading: boolean;
    refresh: () => Promise<void>;
}

const RepoContext = createContext<RepoContextValue | null>(null);

export function RepoProvider({ children }: { children: ReactNode }) {
    const [repos, setRepos] = useState<Repository[]>([]);
    const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchRepos = useCallback(async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE_URL}/repos`);
            if (res.ok) {
                const data: Repository[] = await res.json();
                setRepos(data);
                // Auto-select first repo if none selected or current selection no longer valid
                if (data.length > 0) {
                    setSelectedRepo((prev) => {
                        if (prev && data.find((r) => r.id === prev.id)) return prev;
                        return data[0];
                    });
                } else {
                    setSelectedRepo(null);
                }
            }
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchRepos();
    }, [fetchRepos]);

    return (
        <RepoContext.Provider
            value={{
                repos,
                selectedRepo,
                selectedRepoId: selectedRepo?.id ?? null,
                setSelectedRepo,
                loading,
                refresh: fetchRepos,
            }}
        >
            {children}
        </RepoContext.Provider>
    );
}

export function useRepo() {
    const ctx = useContext(RepoContext);
    if (!ctx) throw new Error("useRepo must be used within <RepoProvider>");
    return ctx;
}
