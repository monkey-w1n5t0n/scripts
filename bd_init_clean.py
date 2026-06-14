#!/usr/bin/env python3
"""
bd_init_clean.py — Run 'bd init --from-jsonl' on repos that have a clean
git working tree (no uncommitted changes), then apply safe post-init fixes.

Repos with dirty working trees are surfaced to the user unchanged.

Usage:
  python3 bd_init_clean.py [--dry-run]
"""

import os
import re
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path

DRY_RUN = "--dry-run" in sys.argv

SRC_DIR = Path.home() / "src"
LOG_DIR = Path.home() / "src" / "logs"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"bd_init_{TIMESTAMP}.log"

# Prefix derived from first issue ID (.rsplit('-',1)[0]) in each repo's JSONL.
# Verified manually; repos with empty JSONL are skipped.
PREFIX_MAP: dict[str, str] = {
    "beads":                    "bd",
    "breadcrumbs":              "breadcrumbs",
    "cli-wrappers":             "cli-wrappers",
    "common-clojure":           "common-clojure",
    "ergo":                     "ergo",
    "gastown":                  "gt",
    "gastown-tdu-c08.2":        "gt-mol",
    "geekypunks":               "website",
    "geekypunks-fuck-it-up":    "website",
    "gitwarden":                "git-scout",
    "inbox":                    "inbox",
    "komboloi":                 "komboloi",
    "mothership":               "spaceship",
    "my-ralph":                 "my-ralph",
    "org-flight":               "flight",
    "remote":                   "ai-remote",
    "replicanter":              "replicanter",
    "stock":                    "stock",
    "teachme":                  "teachme",
    "templates":                "templates",
    "triplet-db":               "TDB",
    "triplet-db-ui":            "tdu",
    "uSEQ":                     "useq",
    "useq-perform":             "protocol",
    "useq-perform-probe-viz":   "protocol",
    "workwithme":               "workwithme",
    # claude-code-tui-copy: empty JSONL, skip
}

# These repos have real uncommitted changes (from bd_doctor scan)
DIRTY_REPOS = {
    "beads", "breadcrumbs", "cli-wrappers", "gastown", "geekypunks",
    "inbox", "komboloi", "my-ralph", "org-flight", "stock", "teachme",
    "templates", "triplet-db-ui", "uSEQ", "useq-perform", "useq-perform-probe-viz",
}

# These repos have local commits not yet pushed
AHEAD_REPOS = {"beads", "ergo", "geekypunks", "org-flight", "triplet-db-ui", "workwithme"}


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr


def git_status_short(repo: Path) -> str:
    _, out, _ = run(["git", "status", "--short"], repo)
    return out.strip()


def find_beads_repos() -> list[Path]:
    return sorted(
        e for e in SRC_DIR.iterdir()
        if e.is_dir() and (e / ".beads").is_dir()
    )


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
    def ok(self, msg):    self._write(" OK  ", msg)
    def warn(self, msg):  self._write("WARN ", msg)
    def error(self, msg): self._write("ERROR", msg)
    def skip(self, msg):  self._write("SKIP ", msg)

    def section(self, title: str):
        sep = "─" * 70
        self._write("─────", f"\n{sep}\n  {title}\n{sep}")

    def raw(self, text: str):
        self.fh.write(text + "\n")
        self.fh.flush()

    def close(self):
        self.fh.close()


def main():
    log = Logger(LOG_FILE)
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    log.info(f"bd_init_clean starting [{mode}] — log: {LOG_FILE}")

    repos = find_beads_repos()
    log.info(f"Found {len(repos)} repos with .beads dirs")

    # Split into clean vs dirty
    clean_repos = [r for r in repos if r.name not in DIRTY_REPOS and r.name in PREFIX_MAP]
    dirty_repos  = [r for r in repos if r.name in DIRTY_REPOS]
    skipped      = [r for r in repos if r.name not in PREFIX_MAP and r.name not in DIRTY_REPOS]

    log.info(f"Clean (will init):  {len(clean_repos)}")
    log.info(f"Dirty (skip+report): {len(dirty_repos)}")
    log.info(f"No prefix/empty JSONL (skip): {[r.name for r in skipped]}")

    # ── Phase 1: bd init --from-jsonl on clean repos ──────────────────────────
    log.section("Phase 1 — bd init --from-jsonl")

    init_ok: list[str] = []
    init_fail: list[tuple[str, str]] = []

    for repo in clean_repos:
        prefix = PREFIX_MAP[repo.name]
        ahead_note = " [ahead of upstream]" if repo.name in AHEAD_REPOS else ""
        log.info(f"  {repo.name} (prefix={prefix}){ahead_note}")

        if DRY_RUN:
            log.skip(f"    [dry-run] bd init --from-jsonl --prefix {prefix}")
            init_ok.append(repo.name)
            continue

        rc, out, err = run(
            ["bd", "init", "--from-jsonl", "--prefix", prefix],
            repo,
            timeout=300,
        )
        log.raw(f"\n[INIT] {repo.name}\n{out}{err}")

        if rc == 0:
            log.ok(f"    ✓ init succeeded")
            init_ok.append(repo.name)
        else:
            log.error(f"    ✗ init failed (exit {rc})")
            # show last few lines of error
            err_lines = (out + err).strip().splitlines()
            for line in err_lines[-5:]:
                log.error(f"      {line}")
            init_fail.append((repo.name, (out + err).strip()))

    # ── Phase 2: post-init fixes on successfully-init'd repos ─────────────────
    log.section("Phase 2 — post-init fixes (bd doctor --fix + role)")

    for repo in clean_repos:
        if repo.name not in init_ok:
            continue

        if DRY_RUN:
            log.skip(f"  [dry-run] {repo.name}: bd doctor --fix && bd config set beads.role maintainer")
            continue

        # bd doctor --fix
        rc, out, err = run(["bd", "doctor", "--fix"], repo)
        log.raw(f"\n[FIX] {repo.name} doctor --fix\n{out}{err}")
        if rc == 0:
            log.ok(f"  {repo.name}: bd doctor --fix ✓")
        else:
            log.warn(f"  {repo.name}: bd doctor --fix exited {rc}")

        # set role
        rc, out, err = run(["bd", "config", "set", "beads.role", "maintainer"], repo)
        log.raw(f"\n[ROLE] {repo.name}\n{out}{err}")
        if rc == 0:
            log.ok(f"  {repo.name}: beads.role=maintainer ✓")
        else:
            log.warn(f"  {repo.name}: bd config set exited {rc}")

    # ── Phase 3: surface dirty repos ──────────────────────────────────────────
    log.section("Phase 3 — dirty repos (need your attention)")

    dirty_report: list[dict] = []
    for repo in dirty_repos:
        status = git_status_short(repo)
        ahead = repo.name in AHEAD_REPOS
        dirty_report.append({
            "name": repo.name,
            "ahead": ahead,
            "git_status": status,
        })
        ahead_note = " + AHEAD of upstream" if ahead else ""
        log.warn(f"\n  {repo.name}{ahead_note}:")
        for line in status.splitlines():
            log.warn(f"    {line}")

    # ── Phase 4: write final summary ──────────────────────────────────────────
    log.section("Summary")
    log.info(f"Initialized:  {len(init_ok)} repos — {init_ok}")
    if init_fail:
        log.error(f"Failed:       {len(init_fail)} — {[r for r, _ in init_fail]}")
    log.info(f"Dirty/skipped: {len(dirty_repos)} repos (see above)")
    if skipped:
        log.info(f"No-op (empty JSONL): {[r.name for r in skipped]}")

    summary_path = LOG_DIR / f"bd_init_{TIMESTAMP}_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "timestamp": TIMESTAMP,
            "dry_run": DRY_RUN,
            "initialized": init_ok,
            "failed": [r for r, _ in init_fail],
            "dirty_repos": dirty_report,
        }, f, indent=2)

    log.info(f"Summary JSON: {summary_path}")
    log.info(f"Full log:     {LOG_FILE}")
    log.close()

    # ── Print dirty-repo digest to stdout for easy reading ────────────────────
    if dirty_report:
        print("\n" + "=" * 70)
        print("  REPOS NEEDING YOUR ATTENTION")
        print("=" * 70)
        for r in dirty_report:
            flags = []
            if r["ahead"]:
                flags.append("AHEAD")
            flag_str = f"  [{', '.join(flags)}]" if flags else ""
            print(f"\n{'─'*60}")
            print(f"  {r['name']}{flag_str}")
            for line in r["git_status"].splitlines():
                print(f"    {line}")


if __name__ == "__main__":
    main()
