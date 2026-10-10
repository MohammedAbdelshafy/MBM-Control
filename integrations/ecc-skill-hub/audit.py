#!/usr/bin/env python3
"""audit.py — safety + inventory auditor for third-party agent-skill repos.

ECC-style skill bundles auto-run inside coding agents, so they are a
supply-chain surface. This script answers, hermetically:

  * does the repo actually contain what it claims (agent/skill counts)?
  * does any skill/agent file contain high-risk patterns?

Patterns are HEURISTIC. A hit is not a verdict: every flagged file is
printed with context for a human reviewer. A pattern match on the word
"curl ... | sh" inside a *warning* ("never do this") is a false positive
with a good sign attached.

Usage:
    python3 audit.py /path/to/repo              # human report to stdout
    python3 audit.py /path/to/repo --json       # machine report to stdout
    python3 audit.py /path/to/repo --scan-dir skills/lead-intelligence

Stdlib only. Read-only: never writes, never executes repo content.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

VERSION = "1.0.0"

# pattern -> (severity, human explanation)
RISK_PATTERNS: list[tuple[str, str, str]] = [
    (r"curl\s+[^|\n]*\|\s*(?:sudo\s+)?(?:sh|bash)\b",
     "HIGH", "pipe-to-shell remote execution (curl|sh)"),
    (r"wget\s+[^|\n]*\|\s*(?:sudo\s+)?(?:sh|bash)\b",
     "HIGH", "pipe-to-shell remote execution (wget|bash)"),
    (r"\beval\s*\(",
     "MEDIUM", "eval() — dynamic code execution"),
    (r"os\.system\s*\(",
     "MEDIUM", "os.system() shell invocation"),
    (r"subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True",
     "MEDIUM", "subprocess with shell=True"),
    (r"powershell\s+-[eE]ncoded[Cc]ommand",
     "HIGH", "obfuscated PowerShell payload"),
    (r"base64\s+(-d|--decode)\s*\|\s*(?:sh|bash)",
     "HIGH", "base64-decode piped to shell"),
    (r"\bexec\s*\(\s*requests\.get\(",
     "HIGH", "exec() on a fetched URL body"),
]

# Informational (LOW): legitimate in most skills, only worth noting in bulk.
INFO_PATTERNS: list[tuple[str, str, str]] = [
    (r"https?://[^\s\"')]+",
     "INFO", "remote URL referenced (check it is a docs link, not code)"),
    (r"npm\s+install\s+-g\s+\S+",
     "INFO", "global npm install instruction"),
    (r"\b(API_KEY|TOKEN|SECRET|PASSWORD)\b",
     "INFO", "credential-looking name (config slot, not a leak)"),
]


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    rule: str
    excerpt: str


@dataclass
class AuditReport:
    repo: str
    agent_files: int = 0
    skill_dirs: int = 0
    command_files: int = 0
    total_files: int = 0
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "repo": self.repo,
            "inventory": {
                "agent_files": self.agent_files,
                "skill_dirs": self.skill_dirs,
                "command_files": self.command_files,
                "total_files": self.total_files,
            },
            "findings": [asdict(f) for f in self.findings],
            "errors": self.errors,
        }


def _count_dir_files(root: Path, pattern: str) -> int:
    return sum(1 for _ in root.rglob(pattern) if _.is_file()) if root.is_dir() else 0


def scan_repo(repo: Path, scan_subdir: str | None = None) -> AuditReport:
    report = AuditReport(repo=str(repo))
    if not repo.is_dir():
        report.errors.append(f"not a directory: {repo}")
        return report

    scan_root = repo / scan_subdir if scan_subdir else repo

    # --- inventory ---
    agents = repo / "agents"
    skills = repo / "skills"
    commands = repo / "commands"
    report.agent_files = _count_dir_files(agents, "*.md")
    report.skill_dirs = sum(1 for d in skills.iterdir() if d.is_dir()) if skills.is_dir() else 0
    report.command_files = _count_dir_files(commands, "*.md")
    report.total_files = sum(1 for _ in repo.rglob("*") if _.is_file())

    # --- pattern scan ---
    compiled = [(re.compile(p), sev, rule) for p, sev, rule in RISK_PATTERNS + INFO_PATTERNS]
    text_exts = {".md", ".mdx", ".txt", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml"}
    for path in sorted(scan_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in text_exts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            report.errors.append(f"{path}: {exc}")
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for rx, sev, rule in compiled:
                if rx.search(line):
                    report.findings.append(Finding(
                        file=str(path.relative_to(repo)),
                        line=lineno, severity=sev, rule=rule,
                        excerpt=line.strip()[:160]))
    return report


def render_human(report: AuditReport) -> str:
    out = [f"ECC-skill-repo audit — {report.repo}",
           f"  agents:   {report.agent_files}",
           f"  skills:   {report.skill_dirs}",
           f"  commands: {report.command_files}",
           f"  files:    {report.total_files}",
           ""]
    sev_rank = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}
    for f in sorted(report.findings, key=lambda x: (sev_rank.get(x.severity, 9), x.file)):
        out.append(f"[{f.severity}] {f.file}:{f.line} — {f.rule}")
        out.append(f"         {f.excerpt}")
    if report.errors:
        out.append("")
        out += [f"ERROR: {e}" for e in report.errors]
    n_high = sum(1 for f in report.findings if f.severity == "HIGH")
    out += ["", f"verdict: {n_high} HIGH findings, review above before adopting any skill blindly."]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit a third-party agent-skill repo.")
    ap.add_argument("repo", help="path to the cloned repo")
    ap.add_argument("--scan-dir", default=None,
                    help="only scan this subdir of the repo")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    report = scan_repo(Path(args.repo), args.scan_dir)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
