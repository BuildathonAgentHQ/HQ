"use client";

import { RepoProvider } from "@/context/repo-context";

export function Providers({ children }: { children: React.ReactNode }) {
    return <RepoProvider>{children}</RepoProvider>;
}
