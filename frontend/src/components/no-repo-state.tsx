"use client";

import Link from "next/link";
import { GitFork, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function NoRepoState() {
    return (
        <div className="flex flex-col items-center justify-center py-32 text-center animate-in fade-in duration-500">
            <div className="h-20 w-20 bg-indigo-500/10 rounded-2xl flex items-center justify-center mb-6">
                <GitFork className="h-10 w-10 text-indigo-400" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">No repository connected</h2>
            <p className="text-sm text-muted-foreground mb-6 max-w-md">
                Connect a GitHub repository to start monitoring, analyzing, and deploying agents.
            </p>
            <Link href="/repos">
                <Button className="bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white shadow-lg shadow-indigo-500/20">
                    <GitFork className="h-4 w-4 mr-2" />
                    Connect Repository
                    <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
            </Link>
        </div>
    );
}
