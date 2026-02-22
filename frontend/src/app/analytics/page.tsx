"use client";

import { useEffect, useState, useMemo } from "react";
import { format } from "date-fns";
import { API_BASE_URL } from "@/lib/constants";
import type { Task } from "@/lib/types";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { Activity, TerminalSquare, Clock, Zap, CheckCircle2, XCircle, DollarSign, TrendingUp } from "lucide-react";

async function fetchTasks(): Promise<Task[]> {
  const res = await fetch(`${API_BASE_URL}/metrics/analytics/tasks`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function fetchTaskLogs(taskId: string): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/metrics/analytics/logs/${taskId}`);
  if (!res.ok) throw new Error(`Failed to fetch logs`);
  const data = await res.json();
  return data.logs || "No logs available.";
}

export default function AnalyticsDashboardPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [taskLogs, setTaskLogs] = useState<string>("");
  const [isLogModalOpen, setIsLogModalOpen] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [finops, setFinops] = useState<{ today_spend: number; monthly_spend: number; avg_cost_per_task: number; projected_burn: number } | null>(null);
  const [showCount, setShowCount] = useState(5);

  useEffect(() => {
    fetchTasks().then(setTasks).catch(() => setTasks([]));
    fetch(`${API_BASE_URL}/finops`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setFinops(d))
      .catch(() => { });
  }, []);

  const openLogs = async (task: Task) => {
    setSelectedTask(task);
    setIsLogModalOpen(true);
    setLoadingLogs(true);
    setTaskLogs("");
    try {
      const logs = await fetchTaskLogs(task.id);
      setTaskLogs(logs);
    } catch {
      setTaskLogs("Failed to load task logs from MLflow.");
    } finally {
      setLoadingLogs(false);
    }
  };

  const engineStats = useMemo(() => {
    if (!tasks) return [];
    const counts: Record<string, number> = {};
    tasks.forEach((t) => {
      counts[t.engine] = (counts[t.engine] || 0) + 1;
    });
    return Object.entries(counts).map(([name, count]) => ({ name, count }));
  }, [tasks]);

  const costOverTime = useMemo(() => {
    if (!tasks) return [];
    // Sort tasks by date oldest to newest
    const sorted = [...tasks]
      .filter((t) => t.created_at)
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

    // Cumulative cost
    let cumulative = 0;
    return sorted.map((t) => {
      cumulative += t.budget_used || 0;
      return {
        date: format(new Date(t.created_at), "MMM dd HH:mm"),
        cost: t.budget_used || 0,
        cumulative: Number(cumulative.toFixed(4)),
      };
    });
  }, [tasks]);

  const successRate = useMemo(() => {
    if (!tasks || tasks.length === 0) return 0;
    const success = tasks.filter((t) => t.status === "success").length;
    return Math.round((success / tasks.length) * 100);
  }, [tasks]);

  return (
    <div className="space-y-6">
      {/* ── Header ──────────────────────────────────────────── */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
          <Zap className="h-6 w-6 text-indigo-400" />
          Analytics
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Agent insights, cost tracking & task outputs
        </p>
      </div>

      {/* ── FinOps Cost Stats ──────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Today's Spend", value: finops ? `$${finops.today_spend.toFixed(2)}` : "—", icon: DollarSign, color: "text-emerald-400", bg: "bg-emerald-500/10" },
          { label: "Monthly Spend", value: finops ? `$${finops.monthly_spend.toFixed(2)}` : "—", icon: TrendingUp, color: "text-amber-400", bg: "bg-amber-500/10" },
          { label: "Avg Cost/Task", value: finops ? `$${finops.avg_cost_per_task.toFixed(4)}` : "—", icon: Activity, color: "text-indigo-400", bg: "bg-indigo-500/10" },
          { label: "Projected Burn", value: finops ? `$${finops.projected_burn.toFixed(2)}/mo` : "—", icon: Clock, color: "text-red-400", bg: "bg-red-500/10" },
        ].map((stat) => (
          <Card key={stat.label} className="border-border/40 bg-card/60 backdrop-blur">
            <CardContent className="p-4">
              <div className="flex items-center gap-3">
                <div className={`h-9 w-9 ${stat.bg} rounded-lg flex items-center justify-center`}>
                  <stat.icon className={`h-4 w-4 ${stat.color}`} />
                </div>
                <div>
                  <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">{stat.label}</p>
                  <p className={`text-lg font-bold ${stat.color}`}>{stat.value}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Summary Stats ────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-border/40 bg-card/60 backdrop-blur">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Total Tasks Tracked</p>
                <h3 className="text-3xl font-bold text-white">{tasks ? tasks.length : "-"}</h3>
              </div>
              <div className="h-12 w-12 bg-indigo-500/10 rounded-full flex items-center justify-center">
                <Activity className="h-6 w-6 text-indigo-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-card/60 backdrop-blur">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Global Success Rate</p>
                <h3 className="text-3xl font-bold text-emerald-400">{tasks ? `${successRate}%` : "-"}</h3>
              </div>
              <div className="h-12 w-12 bg-emerald-500/10 rounded-full flex items-center justify-center">
                <CheckCircle2 className="h-6 w-6 text-emerald-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-card/60 backdrop-blur">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground mb-1">Total Budget Used</p>
                <h3 className="text-3xl font-bold text-amber-400">
                  ${tasks ? tasks.reduce((acc, t) => acc + (t.budget_used || 0), 0).toFixed(4) : "-"}
                </h3>
              </div>
              <div className="h-12 w-12 bg-amber-500/10 rounded-full flex items-center justify-center">
                <Clock className="h-6 w-6 text-amber-400" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Charts ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Engine Distribution */}
        <Card className="border-border/40 bg-card/60 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-base text-white">Tasks by Engine</CardTitle>
            <CardDescription>Distribution of tools used across all tasks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full">
              {!tasks ? (
                <Skeleton className="h-full w-full" />
              ) : engineStats.length === 0 ? (
                <div className="h-full flex items-center justify-center text-muted-foreground">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={engineStats} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                      cursor={{ fill: "#1e293b" }}
                      contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "8px" }}
                    />
                    <Bar dataKey="count" fill="#818cf8" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Cost Over Time */}
        <Card className="border-border/40 bg-card/60 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-base text-white">Cumulative Cost Over Time</CardTitle>
            <CardDescription>Aggregate budget spend across tasks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full">
              {!tasks ? (
                <Skeleton className="h-full w-full" />
              ) : costOverTime.length === 0 ? (
                <div className="h-full flex items-center justify-center text-muted-foreground">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={costOverTime} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                    <XAxis dataKey="date" stroke="#94a3b8" fontSize={10} tickLine={false} axisLine={false} />
                    <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155", borderRadius: "8px" }}
                    />
                    <Line type="monotone" dataKey="cumulative" stroke="#34d399" strokeWidth={3} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Task Logs List ───────────────────────────────────── */}
      <Card className="border-border/40 bg-card/60 backdrop-blur">
        <CardHeader>
          <CardTitle className="text-base text-white">Task Run History</CardTitle>
          <CardDescription>Click on a task to view the full MLflow text artifact log.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
            {!tasks ? (
              Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)
            ) : tasks.length === 0 ? (
              <p className="text-sm text-muted-foreground/60 text-center py-6">No tasks found.</p>
            ) : (
              <>
                {tasks.slice(0, showCount).map((task) => (
                  <div
                    key={task.id}
                    onClick={() => openLogs(task)}
                    className="group flex flex-col md:flex-row items-start md:items-center justify-between gap-3 p-3 rounded-lg border border-border/20 bg-black/20 hover:border-indigo-500/40 hover:bg-white/5 cursor-pointer transition-all"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono text-muted-foreground">
                          {task.id.split("-")[0]}
                        </span>
                        <Badge variant="outline" className="text-[10px] bg-white/5">
                          {task.engine}
                        </Badge>
                        {task.status === "success" && <Badge className="text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/20">Success</Badge>}
                        {task.status === "failed" && <Badge className="text-[10px] bg-red-500/10 text-red-400 border-red-500/20">Failed</Badge>}
                        {task.status === "running" && <Badge className="text-[10px] bg-blue-500/10 text-blue-400 border-blue-500/20 animate-pulse">Running</Badge>}
                      </div>
                      <p className="text-sm text-white truncate max-w-[500px]">{task.task}</p>
                    </div>

                    <div className="flex items-center gap-4 shrink-0 text-xs text-muted-foreground mr-2">
                      <div className="flex items-center gap-1">
                        <TerminalSquare className="h-3.5 w-3.5" />
                        View Logs
                      </div>
                    </div>
                  </div>
                ))}
                {showCount < tasks.length && (
                  <div className="text-center pt-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs text-muted-foreground hover:text-white"
                      onClick={() => setShowCount((c) => c + 10)}
                    >
                      Show more ({tasks.length - showCount} remaining)
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ── Log View Modal ───────────────────────────────────── */}
      <Dialog open={isLogModalOpen} onOpenChange={setIsLogModalOpen}>
        <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col p-0 gap-0 bg-[#0B1120] border-border/40">
          <DialogHeader className="px-6 py-4 border-b border-border/20 bg-white/5 shrink-0">
            <DialogTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-white">
                <TerminalSquare className="h-5 w-5 text-indigo-400" />
                Raw Agent Output
              </div>
              {selectedTask && (
                <Badge variant="outline" className="text-xs mr-6">
                  {selectedTask.id.split("-")[0]}
                </Badge>
              )}
            </DialogTitle>
          </DialogHeader>

          <div className="flex-1 overflow-auto p-4 bg-black/40">
            {loadingLogs ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-3/4 bg-white/5" />
                <Skeleton className="h-4 w-1/2 bg-white/5" />
                <Skeleton className="h-4 w-5/6 bg-white/5" />
              </div>
            ) : (
              <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap break-words font-[family-name:ibm-plex-mono,monospace]">
                {taskLogs}
              </pre>
            )}
          </div>

          <div className="px-6 py-3 border-t border-border/20 bg-white/5 shrink-0 flex items-center justify-between">
            <p className="text-[10px] text-muted-foreground">
              Fetched directly from Databricks MLflow artifacts
            </p>
            <Button size="sm" variant="outline" onClick={() => setIsLogModalOpen(false)}>
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
