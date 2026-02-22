"use client";

import { API_BASE_URL } from "@/lib/constants";
import type {
    Task,
    TaskCreate,
    TelemetryMetrics,
    AgentLeaderboardEntry,
    PRRiskScore,
    CoverageReport,
    RepoHealthReport,
    NextBestAction,
} from "@/lib/types";

// ── Generic fetch wrapper ──────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        headers: { "Content-Type": "application/json", ...init?.headers },
        ...init,
    });
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`API error ${res.status}: ${body}`);
    }
    return res.json() as Promise<T>;
}

// ── Task endpoints ─────────────────────────────────────────────────────────

export async function getTasks(): Promise<Task[]> {
    return apiFetch<Task[]>("/tasks/");
}

export async function getTask(id: string): Promise<Task> {
    return apiFetch<Task>(`/tasks/${id}`);
}

export async function createTask(data: TaskCreate): Promise<Task> {
    return apiFetch<Task>("/tasks/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

export async function cancelTask(id: string): Promise<{ status: string }> {
    return apiFetch<{ status: string }>(`/tasks/${id}`, { method: "DELETE" });
}

export async function suspendTask(id: string): Promise<{ status: string }> {
    return apiFetch<{ status: string }>(`/tasks/${id}/suspend`, { method: "POST" });
}

export async function resumeTask(id: string): Promise<{ status: string }> {
    return apiFetch<{ status: string }>(`/tasks/${id}/resume`, { method: "POST" });
}

export async function injectPrompt(id: string, prompt: string): Promise<{ status: string }> {
    return apiFetch<{ status: string }>(`/tasks/${id}/inject?prompt=${encodeURIComponent(prompt)}`, {
        method: "POST",
    });
}

// ── Metrics endpoints ──────────────────────────────────────────────────────

export async function getRadarMetrics(): Promise<TelemetryMetrics> {
    return apiFetch<TelemetryMetrics>("/metrics/radar");
}

export async function getLeaderboard(): Promise<AgentLeaderboardEntry[]> {
    return apiFetch<AgentLeaderboardEntry[]>("/metrics/leaderboard");
}

// ── Control-plane endpoints ────────────────────────────────────────────────

export async function getPRScores(): Promise<PRRiskScore[]> {
    return apiFetch<PRRiskScore[]>("/control-plane/prs");
}

export async function getCoverage(): Promise<CoverageReport> {
    return apiFetch<CoverageReport>("/control-plane/coverage");
}

export async function getRepoHealth(): Promise<RepoHealthReport> {
    return apiFetch<RepoHealthReport>("/control-plane/health");
}

export async function getActions(): Promise<NextBestAction[]> {
    return apiFetch<NextBestAction[]>("/control-plane/actions");
}
