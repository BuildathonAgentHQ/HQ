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
    return apiFetch<Task[]>("/api/tasks/");
}

export async function getTask(id: string): Promise<Task> {
    return apiFetch<Task>(`/api/tasks/${id}`);
}

export async function createTask(data: TaskCreate): Promise<Task> {
    return apiFetch<Task>("/api/tasks/", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

// ── Metrics endpoints ──────────────────────────────────────────────────────

export async function getRadarMetrics(): Promise<TelemetryMetrics> {
    return apiFetch<TelemetryMetrics>("/api/metrics/radar");
}

export async function getLeaderboard(): Promise<AgentLeaderboardEntry[]> {
    return apiFetch<AgentLeaderboardEntry[]>("/api/metrics/leaderboard");
}

// ── Control-plane endpoints ────────────────────────────────────────────────

export async function getPRScores(): Promise<PRRiskScore[]> {
    return apiFetch<PRRiskScore[]>("/api/control-plane/prs");
}

export async function getCoverage(): Promise<CoverageReport> {
    return apiFetch<CoverageReport>("/api/control-plane/coverage");
}

export async function getRepoHealth(): Promise<RepoHealthReport> {
    return apiFetch<RepoHealthReport>("/api/control-plane/health");
}

export async function getActions(): Promise<NextBestAction[]> {
    return apiFetch<NextBestAction[]>("/api/control-plane/actions");
}
