"""
Coverage Analyzer for Agent HQ Control Plane.

Analyses feature-level test coverage across ALL PRs (open, closed, merged).
A "feature" is any PR that introduces source code.  A feature counts as
"tested" if test files exist for its source files — either within the same
PR or in any other PR in the repo.

    coverage = tested_features / total_features
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from backend.app.config import Settings
from backend.app.control_plane.github_connector import GitHubConnector
from shared.schemas import (
    CoverageReport,
    PRFeatureCoverage,
    UntestableDiff,
)

logger = logging.getLogger(__name__)

_TEST_PATTERNS = ("test", "spec", "__tests__", "tests/", "test/")
_SOURCE_EXTS = (".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".java", ".rs")


def _is_test_file(path: str) -> bool:
    low = path.lower()
    return any(p in low for p in _TEST_PATTERNS)


def _is_source_file(path: str) -> bool:
    return any(path.endswith(ext) for ext in _SOURCE_EXTS) and not _is_test_file(path)


def _stem(path: str) -> str:
    """Return the bare module name stripped of dirs, extensions, and test prefixes.

    ``tests/test_multiply.js`` → ``multiply``
    ``src/multiply.js``        → ``multiply``
    """
    base = path.rsplit("/", 1)[-1]
    name = base.rsplit(".", 1)[0]
    for prefix in ("test_", "test.", "spec.", "spec_"):
        if name.lower().startswith(prefix):
            name = name[len(prefix):]
    for suffix in (".test", ".spec", "_test", "_spec"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
    return name.lower()


class CoverageAnalyzer:
    """Analyses feature-level test coverage for the connected repository."""

    def __init__(self, github: GitHubConnector, settings: Settings):
        self.github = github
        self.settings = settings
        self._cache: CoverageReport | None = None

    async def analyze_coverage(self) -> CoverageReport:
        """Fetch ALL PRs → identify features → cross-match tests → report."""
        if self._cache is not None:
            return self._cache

        all_prs = await self.github.get_all_prs()
        logger.info("Coverage: analysing %d PRs (open + closed)", len(all_prs))

        pr_file_tasks = [self._fetch_pr_files(pr) for pr in all_prs]
        pr_file_results = await asyncio.gather(*pr_file_tasks, return_exceptions=True)

        pr_data: list[dict[str, Any]] = []
        global_test_stems: set[str] = set()

        for pr, result in zip(all_prs, pr_file_results):
            if isinstance(result, Exception):
                logger.warning("Failed to fetch files for PR #%s: %s", pr.get("number"), result)
                continue

            source_files, test_files = result
            entry = {
                "pr": pr,
                "source_files": source_files,
                "test_files": test_files,
            }
            pr_data.append(entry)

            for tf in test_files:
                global_test_stems.add(_stem(tf))

        pr_features: list[PRFeatureCoverage] = []
        all_untested: list[UntestableDiff] = []
        module_coverage: dict[str, float] = {}
        total_features = 0
        tested_features = 0

        for entry in pr_data:
            pr = entry["pr"]
            source_files: list[str] = entry["source_files"]
            test_files: list[str] = entry["test_files"]

            is_feature = len(source_files) > 0
            if not is_feature:
                continue

            total_features += 1
            pr_number = pr["number"]
            title = pr.get("title", f"PR #{pr_number}")
            author = pr.get("user", {}).get("login", "unknown")
            state = pr.get("state", "open")

            has_own_tests = len(test_files) > 0
            source_stems = {_stem(sf) for sf in source_files}
            has_cross_tests = bool(source_stems & global_test_stems)
            is_tested = has_own_tests or has_cross_tests

            if is_tested:
                tested_features += 1

            if is_tested and has_own_tests:
                status = "covered"
            elif is_tested:
                status = "partial"
            else:
                status = "uncovered"

            feat = PRFeatureCoverage(
                pr_number=pr_number,
                title=f"{title} [{state}]",
                author=author,
                total_files=len(source_files) + len(test_files),
                source_files=len(source_files),
                test_files=len(test_files),
                has_tests=is_tested,
                coverage_status=status,
            )
            pr_features.append(feat)

            mod_label = title.split(":")[0].split("(")[0].strip()[:35] or f"PR #{pr_number}"
            module_coverage[mod_label] = 100.0 if is_tested else 0.0

            if not is_tested:
                for sf in source_files:
                    additions = 0
                    for f in entry.get("_raw_files", []):
                        if f.get("filename") == sf:
                            additions = f.get("additions", 0)
                            break
                    if additions == 0:
                        additions = 1

                    if "auth" in sf.lower() or "security" in sf.lower():
                        risk = "critical — security module"
                    elif "server" in sf.lower() or "api" in sf.lower() or "app" in sf.lower():
                        risk = "high — core logic"
                    else:
                        risk = "medium — new feature code"

                    all_untested.append(UntestableDiff(
                        file_path=sf,
                        lines_uncovered=additions,
                        risk=risk,
                        pr_number=pr_number,
                        pr_title=title,
                    ))

        coverage_pct = round((tested_features / total_features) * 100, 1) if total_features else 0.0

        if coverage_pct > 70:
            trend = "improving"
        elif coverage_pct < 40:
            trend = "declining"
        else:
            trend = "stable"

        report = CoverageReport(
            total_coverage_pct=coverage_pct,
            module_coverage=module_coverage,
            untested_diffs=all_untested,
            trend=trend,
            pr_features=pr_features,
            total_prs=total_features,
            prs_with_tests=tested_features,
        )
        self._cache = report
        logger.info(
            "Coverage: %d/%d features tested (%.1f%%)",
            tested_features, total_features, coverage_pct,
        )
        return report

    async def _fetch_pr_files(
        self, pr: dict[str, Any]
    ) -> tuple[list[str], list[str]]:
        """Return (source_files, test_files) for a PR."""
        files = await self.github.get_pr_files(pr["number"])
        source: list[str] = []
        tests: list[str] = []
        for f in files:
            fname = f.get("filename", "")
            if _is_test_file(fname):
                tests.append(fname)
            elif _is_source_file(fname):
                source.append(fname)
        return source, tests
