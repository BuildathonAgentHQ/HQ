/**
 * frontend/src/lib/types.ts — TypeScript interfaces mirroring shared/schemas.py.
 *
 * FROZEN — These types are the frontend counterpart of the Pydantic models in
 * shared/schemas.py.  Every field name, type, and literal union MUST match
 * exactly.  No breaking changes without team approval.
 *
 * NOTE: Python `datetime` fields are serialised as ISO-8601 strings over JSON,
 * so they are typed as `string` here.
 */

// ═══════════════════════════════════════════════════════════════════════════════
//  1. TaskCreate — Frontend → Backend (POST /api/tasks)
// ═══════════════════════════════════════════════════════════════════════════════

/** Payload the frontend sends to create a new agent task. */
export interface TaskCreate {
    task: string;
    engine: "claude-code" | "cursor-cli" | "gemini-cli" | "codex";
    agent_type:
    | "general"
    | "test_writer"
    | "refactor"
    | "doc"
    | "reviewer"
    | "release_notes";
    budget_limit: number; // default 2.0
    context_sources: string[]; // default []
}

// ═══════════════════════════════════════════════════════════════════════════════
//  2. Task — Full server-side task record
// ═══════════════════════════════════════════════════════════════════════════════

/** Complete task object stored and managed by the backend. */
export interface Task {
    id: string; // UUID v4
    task: string;
    engine: string;
    agent_type: string;
    status: "pending" | "running" | "success" | "failed" | "suspended";
    budget_limit: number;
    budget_used: number;
    created_at: string; // ISO-8601
    updated_at: string; // ISO-8601
    exit_code: number | null;
    token_count: number;
    strike_count: number; // consecutive Janitor failures
}

// ═══════════════════════════════════════════════════════════════════════════════
//  3. RawStreamEvent — Subprocess stdout / stderr capture
// ═══════════════════════════════════════════════════════════════════════════════

/** Raw line of output from the agent subprocess, before Nemotron translation. */
export interface RawStreamEvent {
    task_id: string;
    stream_type: "stdout" | "stderr";
    raw_content: string;
    timestamp: string; // ISO-8601
}

// ═══════════════════════════════════════════════════════════════════════════════
//  4. TranslatedEvent — Nemotron's human-readable interpretation
// ═══════════════════════════════════════════════════════════════════════════════

/** Plain-English interpretation of raw agent output, produced by Nemotron. */
export interface TranslatedEvent {
    task_id: string;
    status: string; // one-sentence non-technical description
    is_error: boolean;
    severity: "info" | "warning" | "error";
    category:
    | "setup"
    | "coding"
    | "testing"
    | "debugging"
    | "deploying"
    | "waiting"
    | "completed";
}

// ═══════════════════════════════════════════════════════════════════════════════
//  5. WebSocketEvent — Universal WS envelope to the frontend
// ═══════════════════════════════════════════════════════════════════════════════

/** Top-level envelope for every message sent over the WebSocket. */
export interface WebSocketEvent {
    task_id: string;
    event_type:
    | "status_update"
    | "error"
    | "approval_required"
    | "budget_exceeded"
    | "debate"
    | "guardrail"
    | "task_lifecycle"
    | "repo_added"
    | "repo_analyzed"
    | "pr_reviewed"
    | "swarm_started"
    | "swarm_agent_started"
    | "swarm_agent_completed"
    | "swarm_completed"
    | "fix_proposed"
    | "fix_applied";
    payload: Record<string, unknown>;
    timestamp: string; // ISO-8601
}

// ═══════════════════════════════════════════════════════════════════════════════
//  6. GuardrailEvent — Janitor Protocol check result
// ═══════════════════════════════════════════════════════════════════════════════

/** Emitted every time the Janitor Protocol runs a guardrail check. */
export interface GuardrailEvent {
    task_id: string;
    file_path: string;
    check_type: "lint" | "security" | "destructive_action";
    passed: boolean;
    error_msg: string;
    strike_count: number;
    auto_fixed: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  7. ApprovalRequest — Human-in-the-loop gate
// ═══════════════════════════════════════════════════════════════════════════════

/** Sent to the frontend when a destructive or contentious action is detected. */
export interface ApprovalRequest {
    task_id: string;
    action_type: "destructive_cmd" | "budget_overrun" | "debate_resolution";
    command: string | null;
    description: string;
    options: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
//  8. TelemetryMetrics — Radar chart endpoint payload
// ═══════════════════════════════════════════════════════════════════════════════

/** Normalised 0-100 scores powering the /api/metrics/radar endpoint. */
export interface TelemetryMetrics {
    security: number; // 0-100
    stability: number; // 0-100
    quality: number; // 0-100
    speed: number; // 0-100
    timestamp: string; // ISO-8601
}

// ═══════════════════════════════════════════════════════════════════════════════
//  9. AgentLeaderboardEntry — Efficiency leaderboard row
// ═══════════════════════════════════════════════════════════════════════════════

/** A single row in the agent efficiency leaderboard. */
export interface AgentLeaderboardEntry {
    engine: string;
    tasks_completed: number;
    success_rate: number; // 0-1
    avg_duration_seconds: number;
    avg_cost_dollars: number;
    total_tokens: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  10. PRRiskScore — Control Plane PR risk analysis
// ═══════════════════════════════════════════════════════════════════════════════

/** Breakdown of individual risk signals contributing to a PR's risk score. */
export interface PRRiskFactors {
    diff_size: number;
    core_files_changed: boolean;
    missing_tests: boolean;
    churn_score: number;
    has_dependency_overlap: boolean;
}

/** Full risk assessment for a single pull request. */
export interface PRRiskScore {
    pr_id: string;
    pr_number: number;
    title: string;
    author: string;
    risk_score: number; // 0-100
    risk_level: "low" | "medium" | "high" | "critical";
    factors: PRRiskFactors;
    reviewers_suggested: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
//  11. CoverageReport — Test coverage snapshot
// ═══════════════════════════════════════════════════════════════════════════════

/** A file diff that lacks test coverage. */
export interface UntestableDiff {
    file_path: string;
    lines_uncovered: number;
    risk: string;
}

/** Aggregated test-coverage data for the repository. */
export interface CoverageReport {
    total_coverage_pct: number; // 0-100
    module_coverage: Record<string, number>; // module name → coverage %
    untested_diffs: UntestableDiff[];
    trend: "improving" | "stable" | "declining";
}

// ═══════════════════════════════════════════════════════════════════════════════
//  12. RepoHealthReport — Aggregate repository health
// ═══════════════════════════════════════════════════════════════════════════════

/** A frequently-changed file. */
export interface HotFile {
    path: string;
    change_count_30d: number;
    last_changed: string; // ISO-8601
}

/** A tracked technical-debt item. */
export interface TechDebtItem {
    description: string;
    age_days: number;
    severity: string;
}

/** Overall repository health snapshot. */
export interface RepoHealthReport {
    ci_status: "passing" | "failing" | "unknown";
    flaky_tests: string[];
    hot_files: HotFile[];
    tech_debt_items: TechDebtItem[];
}

// ═══════════════════════════════════════════════════════════════════════════════
//  13. NextBestAction — Recommended action for the user
// ═══════════════════════════════════════════════════════════════════════════════

/** An actionable recommendation surfaced by the control plane. */
export interface NextBestAction {
    action_type:
    | "add_tests"
    | "split_pr"
    | "fix_flaky"
    | "refactor"
    | "update_docs";
    description: string;
    target: string; // file path or PR number
    priority: "high" | "medium" | "low";
    estimated_effort: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  14. ContextPayload — What the context layer feeds to agents
// ═══════════════════════════════════════════════════════════════════════════════

/** A reusable skill / recipe from the learning layer. */
export interface SkillRecipe {
    name: string;
    steps: string[];
    success_rate: number; // 0-1
    last_used: string; // ISO-8601
}

/** Bundle of context injected into agent prompts before execution. */
export interface ContextPayload {
    architectural_context: string;
    dependencies: string[];
    relevant_skills: SkillRecipe[];
    business_requirements: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
//  15. DebateResult — Multi-agent disagreement resolution
// ═══════════════════════════════════════════════════════════════════════════════

/** A single option surfaced during a multi-agent debate. */
export interface DebateOption {
    label: string;
    description: string;
    recommended_by: string;
}

/** Summary of a multi-agent debate when agents disagree on approach. */
export interface DebateResult {
    task_id: string;
    agent_a_position: string;
    agent_b_position: string;
    summary: string; // plain English from Nemotron
    options: DebateOption[];
}

// ═══════════════════════════════════════════════════════════════════════════════
//  16. Repository — A connected GitHub repository
// ═══════════════════════════════════════════════════════════════════════════════

/** A GitHub repository connected to Agent HQ for analysis and monitoring. */
export interface Repository {
    id: string; // UUID v4
    owner: string;
    name: string;
    full_name: string; // owner/name
    url: string;
    default_branch: string; // default "main"
    added_at: string; // ISO-8601
    last_analyzed: string | null;
    analysis_summary: string | null;
    tech_stack: string[];
    health_score: number | null; // 0-100
}

// ═══════════════════════════════════════════════════════════════════════════════
//  17. CodeIssue — A single issue found by Claude analysis
// ═══════════════════════════════════════════════════════════════════════════════

/** A code issue discovered by Claude during repo or PR analysis. */
export interface CodeIssue {
    id: string; // UUID v4
    repo_id: string;
    pr_number: number | null;
    file_path: string;
    line_number: number | null;
    issue_type:
    | "bug"
    | "security"
    | "performance"
    | "error_handling"
    | "testing"
    | "style"
    | "breaking"
    | "refactor";
    severity: "critical" | "high" | "medium" | "low";
    description: string;
    suggestion: string;
    status: "open" | "fixing" | "fixed" | "dismissed";
    assigned_agent: string | null;
    fix_pr_url: string | null;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  18. FixProposal — A proposed code fix from a swarm agent
// ═══════════════════════════════════════════════════════════════════════════════

/** A concrete code fix proposed by a swarm agent. */
export interface FixProposal {
    id: string; // UUID v4
    issue_id: string;
    repo_id: string;
    agent_type: string;
    file_path: string;
    original_code: string;
    fixed_code: string;
    explanation: string;
    test_code: string | null;
    status: "proposed" | "approved" | "applied" | "rejected";
    created_at: string; // ISO-8601
}

// ═══════════════════════════════════════════════════════════════════════════════
//  19. SwarmTask — A unit of work for the agent swarm
// ═══════════════════════════════════════════════════════════════════════════════

/** A single task assigned to one swarm agent. */
export interface SwarmTask {
    id: string; // UUID v4
    repo_id: string;
    pr_number: number | null;
    agent_type:
    | "coordinator"
    | "reviewer"
    | "test_writer"
    | "refactor"
    | "security_auditor"
    | "doc_writer"
    | "fix_generator";
    task_description: string;
    target_files: string[];
    depends_on: string[]; // SwarmTask IDs
    status: "pending" | "running" | "success" | "failed";
    result: Record<string, unknown> | null;
    tokens_used: number;
    cost: number;
    started_at: string | null; // ISO-8601
    completed_at: string | null; // ISO-8601
}

// ═══════════════════════════════════════════════════════════════════════════════
//  20. SwarmPlan — Execution plan for a swarm operation
// ═══════════════════════════════════════════════════════════════════════════════

/** A coordinated execution plan for multiple swarm agents. */
export interface SwarmPlan {
    id: string; // UUID v4
    repo_id: string;
    pr_number: number | null;
    trigger: "pr_review" | "repo_audit" | "fix_issues" | "manual";
    plan_summary: string;
    tasks: SwarmTask[];
    status: "planning" | "executing" | "completed" | "failed";
    total_issues_found: number;
    total_fixes_proposed: number;
    total_fixes_applied: number;
    created_at: string; // ISO-8601
}

// ═══════════════════════════════════════════════════════════════════════════════
//  21. PRReview — Enhanced PR review from Claude
// ═══════════════════════════════════════════════════════════════════════════════

/** Comprehensive PR review powered by Claude. */
export interface PRReview {
    id: string; // UUID v4
    repo_id: string;
    pr_number: number;
    pr_title: string;
    pr_author: string;
    summary: string;
    risk_level: "low" | "medium" | "high" | "critical";
    verdict: "approve" | "request_changes" | "needs_discussion";
    issues: CodeIssue[];
    missing_tests: Array<{ file: string; description: string }>;
    praise: string[];
    fix_plan: SwarmPlan | null;
    reviewed_at: string; // ISO-8601
}
