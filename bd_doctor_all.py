#!/usr/bin/env python3
"""
bd_doctor_all.py — Run bd doctor on every ~/src repo that has a .beads dir.

Safe auto-fixes applied per repo:
  • bd doctor --fix   (stale locks, gitignore, untrack last-touched)
  • bd config set beads.role maintainer   (when role is missing)

Git-state issues (dirty tree, ahead of upstream, conflicts) are surfaced
to the user and NEVER touched automatically.
"""

import os
import re
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────────
SRC_DIR = Path.home() / "src"
LOG_DIR = Path.home() / "src" / "logs"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"bd_doctor_{TIMESTAMP}.log"

# Issues in doctor output that we attempt to auto-fix
FIXABLE_PATTERNS = [
    r"Stale lock|stale lock",
    r"Outdated .beads/.gitignore",
    r"last-touched file is tracked",
    r"Sync Branch Gitignore",
]

ROLE_PATTERN = r"beads\.role not configured"
GIT_DIRTY_PATTERN = r"Git Working Tree: Uncommitted changes"
GIT_AHEAD_PATTERN = r"Git Upstream: Ahead of upstream"
GIT_CONFLICT_PATTERN = r"conflict|CONFLICT|merge conflict"
FRESH_CLONE_PATTERN = r"Fresh clone detected"


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def find_beads_repos() -> list[Path]:
    repos = []
    for entry in sorted(SRC_DIR.iterdir()):
        if entry.is_dir() and (entry / ".beads").is_dir():
            repos.append(entry)
    return repos


def parse_doctor_output(output: str) -> dict:
    """Extract key signals from bd doctor stdout."""
    combined = output  # strip is done per pattern
    return {
        "has_fixable":    any(re.search(p, combined) for p in FIXABLE_PATTERNS),
        "needs_role":     bool(re.search(ROLE_PATTERN, combined)),
        "git_dirty":      bool(re.search(GIT_DIRTY_PATTERN, combined)),
        "git_ahead":      bool(re.search(GIT_AHEAD_PATTERN, combined)),
        "git_conflict":   bool(re.search(GIT_CONFLICT_PATTERN, combined, re.I)),
        "fresh_clone":    bool(re.search(FRESH_CLONE_PATTERN, combined)),
        "warnings":       len(re.findall(r"⚠", combined)),
        "errors":         len(re.findall(r"✖\s+\d+\s+error", combined)),
    }


def git_status(repo: Path) -> str:
    _, out, _ = run(["git", "status", "--short"], repo)
    return out.strip()


def check_git_conflicts(repo: Path) -> list[str]:
    _, out, _ = run(["git", "status", "--short"], repo)
    conflicts = [line for line in out.splitlines() if line.startswith("UU") or "CONFLICT" in line]
    return conflicts


class Logger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(path, "w")
        self.path = path

    def _write(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] [{level}] {msg}"
        print(line)
        self.fh.write(line + "\n")
        self.fh.flush()

    def info(self, msg):  self._write("INFO ", msg)
    def warn(self, msg):  self._write("WARN ", msg)
    def error(self, msg): self._write("ERROR", msg)
    def section(self, msg):
        sep = "─" * 70
        self._write("─────", f"\n{sep}\n  {msg}\n{sep}")

    def raw(self, text: str):
        """Write raw text to log only (not stdout)."""
        self.fh.write(text + "\n")
        self.fh.flush()

    def close(self):
        self.fh.close()


def main():
    log = Logger(LOG_FILE)
    log.info(f"bd_doctor_all starting — log: {LOG_FILE}")

    repos = find_beads_repos()
    log.info(f"Found {len(repos)} repos with .beads dirs")

    summary: dict[str, dict] = {}
    conflicts_found: list[tuple[Path, list[str]]] = []
    git_issues: list[tuple[Path, dict]] = []   # repos with dirty/ahead issues

    # ── Phase 1: run bd doctor on every repo ─────────────────────────────────
    log.section("Phase 1 — bd doctor scan")

    for repo in repos:
        log.info(f"Scanning {repo.name} …")

        # Hard-stop: git conflicts before we do anything
        conflicts = check_git_conflicts(repo)
        if conflicts:
            log.error(f"  GIT CONFLICTS in {repo.name}: {conflicts}")
            conflicts_found.append((repo, conflicts))
            summary[repo.name] = {"status": "CONFLICT", "conflicts": conflicts}
            continue

        rc, out, err = run(["bd", "doctor"], repo)
        combined = out + err
        signals = parse_doctor_output(combined)
        signals["rc"] = rc

        # Log full doctor output to file only (can be long)
        log.raw(f"\n{'='*70}\n[DOCTOR OUTPUT] {repo.name}\n{'='*70}")
        log.raw(combined)

        status_line = (
            f"  warnings={signals['warnings']}  errors={signals['errors']}"
            f"  fresh_clone={'yes' if signals['fresh_clone'] else 'no'}"
            f"  git_dirty={'yes' if signals['git_dirty'] else 'no'}"
            f"  git_ahead={'yes' if signals['git_ahead'] else 'no'}"
        )
        log.info(status_line)
        summary[repo.name] = signals

        if signals["git_dirty"] or signals["git_ahead"]:
            git_status_out = git_status(repo)
            git_issues.append((repo, {"signals": signals, "git_status": git_status_out}))

    if conflicts_found:
        log.section("STOPPING — git conflicts detected (see below)")
        for repo, c in conflicts_found:
            log.error(f"  {repo}: {c}")
        log.close()
        print(f"\nLog saved to: {LOG_FILE}")
        _report_conflicts(conflicts_found)
        sys.exit(1)

    # ── Phase 2: apply safe fixes ─────────────────────────────────────────────
    log.section("Phase 2 — safe auto-fixes")

    fix_applied: list[str] = []
    fix_skipped: list[str] = []

    for repo in repos:
        sigs = summary.get(repo.name, {})
        if sigs.get("status") == "CONFLICT":
            continue

        applied_anything = False

        # Fix: bd doctor --fix (stale locks, .gitignore, untrack last-touched)
        if sigs.get("has_fixable"):
            log.info(f"  {repo.name}: running 'bd doctor --fix' …")
            rc, out, err = run(["bd", "doctor", "--fix"], repo)
            log.raw(f"[FIX OUTPUT] {repo.name} bd doctor --fix\n{out}{err}")
            if rc == 0:
                log.info(f"    ✓ bd doctor --fix succeeded")
                fix_applied.append(f"{repo.name}: bd doctor --fix")
                applied_anything = True
            else:
                log.warn(f"    ⚠ bd doctor --fix exited {rc}")

        # Fix: set beads.role = maintainer
        if sigs.get("needs_role"):
            log.info(f"  {repo.name}: setting beads.role = maintainer …")
            rc, out, err = run(["bd", "config", "set", "beads.role", "maintainer"], repo)
            log.raw(f"[FIX OUTPUT] {repo.name} bd config set beads.role maintainer\n{out}{err}")
            if rc == 0:
                log.info(f"    ✓ beads.role set")
                fix_applied.append(f"{repo.name}: bd config set beads.role maintainer")
                applied_anything = True
            else:
                log.warn(f"    ⚠ bd config set exited {rc}")

        if not applied_anything:
            fix_skipped.append(repo.name)

    # ── Phase 3: summary ──────────────────────────────────────────────────────
    log.section("Phase 3 — summary")

    fresh_clones    = [r for r, s in summary.items() if s.get("fresh_clone")]
    git_dirty_repos = [(r, d) for r, d in git_issues if d["signals"].get("git_dirty")]
    git_ahead_repos = [(r, d) for r, d in git_issues if d["signals"].get("git_ahead")]

    log.info(f"Repos scanned:       {len(repos)}")
    log.info(f"Fixes applied:       {len(fix_applied)}")
    log.info(f"Fresh clones (need bd init): {len(fresh_clones)}")
    log.info(f"Repos with dirty git tree:   {len(git_dirty_repos)}")
    log.info(f"Repos ahead of upstream:     {len(git_ahead_repos)}")

    if fresh_clones:
        log.warn("Fresh clones — run 'bd init' manually:")
        for r in fresh_clones:
            log.warn(f"  cd ~/src/{r} && bd init")

    if git_dirty_repos:
        log.warn("Repos with uncommitted changes (review manually):")
        for repo, info in git_dirty_repos:
            log.warn(f"  {repo.name}:")
            for line in info["git_status"].splitlines():
                log.warn(f"    {line}")

    if git_ahead_repos:
        log.warn("Repos ahead of upstream (push when ready):")
        for repo, info in git_ahead_repos:
            log.warn(f"  {repo.name}: git -C ~/src/{repo.name} push")

    # machine-readable summary
    summary_path = LOG_DIR / f"bd_doctor_{TIMESTAMP}_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "timestamp": TIMESTAMP,
            "fixes_applied": fix_applied,
            "fresh_clones": fresh_clones,
            "git_dirty": [r.name for r, _ in git_dirty_repos],
            "git_ahead": [r.name for r, _ in git_ahead_repos],
            "per_repo": {k: {kk: v for kk, v in vv.items() if isinstance(v, (bool, int, str))}
                         for k, vv in summary.items()},
        }, f, indent=2)

    log.info(f"Summary JSON: {summary_path}")
    log.info(f"Full log:     {LOG_FILE}")
    log.close()


def _report_conflicts(conflicts: list[tuple[Path, list[str]]]):
    print("\n" + "="*70)
    print("  GIT CONFLICTS DETECTED — manual resolution required")
    print("="*70)
    for repo, lines in conflicts:
        print(f"\n  Repository: {repo}")
        for line in lines:
            print(f"    {line}")
    print("\nResolve conflicts, then re-run this script.")


if __name__ == "__main__":
    main()
