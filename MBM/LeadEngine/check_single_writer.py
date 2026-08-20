#!/usr/bin/env python3
"""
STATIC SINGLE-WRITER WRITE-GUARD
================================
Scans source trees for any module that writes to the canonical dialer database
(`mbm-dialer/app/public/leads_database.json`) OUTSIDE the authorized gateway
modules.

The ONLY authorized writers are:
  - MBM/GLM/single_writer_lock.py       (DialerSingleWriter — core atomic writer)
  - MBM/LeadEngine/dialer_gateway.py    (commit_dialer_db / patch_dialer_db)
  - MBM/LeadEngine/dialer_db_lock.py    (DialerDatabaseLock — shared-lock helper)
  - server/dialer/dialerDbGateway.js    (Node canonical gateway)

Any other module performing a raw write (`write_text`, `open(.., "w")`,
`json.dump(.., f)`, `os.replace`, `Path.rename`, `shutil.copy2`) on the live
dialer DB path is a ROGUE WRITER and must be routed through the gateway.

Exit code:
  0 = clean (no rogue writers found)
  1 = violations found (list them)

Usage:
  python MBM/LeadEngine/check_single_writer.py              # scan whole repo (CI)
  python MBM/LeadEngine/check_single_writer.py --dirs MBM,server
  python MBM/LeadEngine/check_single_writer.py --path a.py  # scan specific file(s)/dirs
"""

from __future__ import annotations

import os
import re
import sys
import time
import argparse
from typing import Iterable, List, Tuple
from pathlib import Path

DB_FILE_NAME = "leads_database.json"
DB_DIR_REF = "mbm-dialer/app/public"
DB_TOKEN = "leads_database.json"
DB_PATH_TOKEN = "mbm-dialer/app/public"

# Authorized gateway modules (relative to repo root, forward slashes).
AUTHORIZED = {
    "MBM/GLM/single_writer_lock.py",
    "MBM/LeadEngine/dialer_gateway.py",
    "MBM/LeadEngine/dialer_db_lock.py",
    "server/dialer/dialerDbGateway.js",
}

# Directories pruned during full-repo scans (vendored/heavy/unrelated).
SKIP_DIRS = {
    ".git", ".git-rewrite", ".pytest_cache", ".venv", "venv", "env",
    "node_modules", "dist", "build", "logs", "__pycache__", ".next",
    "coverage", ".hermes", ".agents", ".claude", ".opencode", ".antigravity",
    "ComfyUI", "HunyuanVideo", "LTX-Video", "google-cloud-sdk", "litellm",
    "aider", "autogen", "crewai", "extracted_images", "extracted_images_un",
    "publish_queue", "GTM", "db_backups", "backups", "quarantine",
    "report_cache",
}

CODE_SUFFIXES = (".py", ".js", ".cjs", ".mjs", ".ts", ".tsx")

# Names of helper functions whose body writes a path argument to disk. A call to
# such a name passing a DB-bound argument is a raw write.
RAW_WRITE_HELPERS = {"save_json", "save_json_backup", "write_json_file", "atomic_save_json"}

# Write primitives that mutate a file on disk (applied to a path receiver).
WRITE_PRIMITIVES = [
    re.compile(r"\.write_text\s*\("),
    re.compile(r"\.write_bytes\s*\("),
    re.compile(r"\bopen\s*\([^)]*['\"]w"),        # open(..., 'w'/'wb'/'a')
    re.compile(r"json\.dump\b\s*\("),
    re.compile(r"os\.replace\b\s*\("),
    re.compile(r"\.rename\s*\("),
    # shutil is only a violation when it WRITES TO the DB (source -> DB path).
    # Reading the DB OUT to a backup file is legitimate and exempted below.
    re.compile(r"shutil\.copy2\b\s*\("),
    re.compile(r"shutil\.move\b\s*\("),
]

# Tokens that mark a shutil copy/move as a legit backup (DB -> backup).
BACKUP_TOKENS = ("backup", ".bak", "corrupt", "_backup", "recovery")


def _db_bound_names(text: str) -> set:
    """Names assigned to an expression referencing the production dialer DB path.

    e.g. `DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"`
    or `dialer_path = ROOT / "mbm-dialer" / ... / "leads_database.json"`
    or `OUTPUT = BASE.parent.parent / "mbm-dialer" / ...`.
    """
    names = set()
    for m in re.finditer(r"(?m)^\s*(\w+)\s*=\s*(.*)$", text):
        lhs, rhs = m.group(1), m.group(2)
        if DB_TOKEN in rhs or DB_PATH_TOKEN in rhs:
            if lhs.lower() not in ("if", "for", "while", "return"):
                names.add(lhs)
            # also catch `VAR = path or FALLBACK` where the path literal is present
    return names


def _is_onedrive_placeholder(path: Path) -> bool:
    """True for OneDrive on-demand / offline placeholders. Reading them would
    trigger a network download and hang the scan on big trees."""
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == -1:
            return False
        # OFFLINE / RECALL_ON_DATA_ACCESS / RECALL_ON_OPEN => cloud placeholder.
        if attrs & 0x1000 or attrs & 0x400000 or attrs & 0x40000:
            return True
        return False
    except Exception:
        return False


def _is_authorized(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        rel = path.as_posix()
    if rel in AUTHORIZED:
        return True
    # Test files live in hermetic tmp dirs; they never touch the production DB.
    if rel.startswith("MBM/LeadEngine/tests/") or rel.endswith("_test.py") or "/tests/" in rel:
        return True
    if rel.startswith("docker_manager/tests/"):
        return True
    return False


def scan_file(path: Path, repo_root: Path) -> List[Tuple[int, str]]:
    """Return list of (lineno, line) pairs that look like rogue DB writes."""
    if _is_onedrive_placeholder(path):
        return []
    if _is_authorized(path, repo_root):
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    if DB_TOKEN not in text and DB_PATH_TOKEN not in text:
        return []

    db_names = _db_bound_names(text)
    # also accept names imported from the gateway that resolve to the live DB,
    # but those files are expected to USE the sanctioned gateway (no raw write).
    hits: List[Tuple[int, str]] = []
    for idx, line in enumerate(text.splitlines(), 1):
        # The line is a write if a primitive targets a DB-bound receiver on THIS line,
        # or if a raw-write helper is CALLED with a DB-bound argument on this line.
        primitive_on_line = any(pat.search(line) for pat in WRITE_PRIMITIVES)
        helper_on_line = any(f" {h}(" in line or f"\t{h}(" in line for h in RAW_WRITE_HELPERS)
        # shutil.copy2/move that copies the DB OUT to a backup is legitimate.
        shutil_write = re.search(r"shutil\.(copy2|move)\b", line)
        if primitive_on_line and shutil_write and any(t in line for t in BACKUP_TOKENS):
            primitive_on_line = False
        name_on_line = any(
            name in line.split()
            or f",{name}," in line
            or f"({name}" in line
            or f" {name}," in line
            or f",{name})" in line
            or re.search(rf"\b{name}\b", line)
            for name in db_names
        )
        literal_on_line = (DB_TOKEN in line) or (DB_PATH_TOKEN in line)
        if not (primitive_on_line or helper_on_line):
            continue
        if literal_on_line or name_on_line:
            hits.append((idx, line.strip()))
    return hits


def _iter_code_files(base: Path):
    """Yield code files under `base`, pruning heavy/vendor dirs."""
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in sorted(files):
            if fname.endswith(CODE_SUFFIXES):
                yield Path(root) / fname


def iter_scan_paths(repo_root: Path, dirs: Iterable[str]) -> Iterable[Path]:
    """Yield candidate code files: explicit dirs (if given) or the whole repo."""
    for name in dirs:
        base = repo_root / name if not Path(name).is_absolute() else Path(name)
        if not base.exists():
            continue
        if base.is_file():
            yield base
        elif base.is_dir():
            yield from _iter_code_files(base)


def scan_repo(repo_root: Path, dirs: Iterable[str] = ()) -> dict:
    """Return {relpath: [(lineno, line)]} of rogue writers.

    With no `dirs`, scans the repo root + a curated set of code dirs plus the
    whole `MBM` and `server` trees (with vendor pruning). In CI (clean checkout)
    this is fast; locally on OneDrive it skips cloud placeholders.
    """
    violations: dict = {}
    targets = set(dirs) if dirs else set()
    if not targets:
        # Default: scan the dirs that actually hold dialer-touching code.
        targets = {".", "MBM", "mbm-dialer", "server", "MissionControl",
                   "coldcall", "scripts", "digital-product-store", "base44",
                   "MBM-Social", "MBM_OS", "docker", "docker_manager"}
    for path in iter_scan_paths(repo_root, targets):
        hits = scan_file(path, repo_root)
        if hits:
            try:
                rel = path.relative_to(repo_root).as_posix()
            except ValueError:
                rel = path.as_posix()
            violations[rel] = hits
    return violations


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=None, help="repo root")
    ap.add_argument("--dirs", type=str, default=None,
                    help="comma-separated dirs to scan (default: repo + curated code dirs)")
    ap.add_argument("--path", action="append", default=[],
                    help="explicit file/dir to scan (can repeat)")
    ap.add_argument("--quiet", action="store_true", help="only print summary")
    args = ap.parse_args(argv)

    repo_root = (args.repo or Path(__file__).resolve().parents[2]).resolve()
    dirs = args.dirs.split(",") if args.dirs else []
    targets = dirs + args.path if (dirs or args.path) else [""]

    t0 = time.time()
    violations = scan_repo(repo_root, targets) if targets != [""] else scan_repo(repo_root)
    elapsed = time.time() - t0

    if not violations:
        print(f"[PASS] Single-writer write-guard clean ({elapsed:.1f}s, 0 rogue writers of {DB_FILE_NAME}).")
        return 0

    print(f"[FAIL] {len(violations)} file(s) contain ROGUE WRITES of {DB_FILE_NAME}:")
    total = 0
    for rel, hits in violations.items():
        print(f"\n  {rel}")
        for lineno, line in hits:
            print(f"    L{lineno}: {line[:140]}")
            total += 1
    print(f"\n{total} rogue write site(s) found. Route all writers through the canonical "
          f"gateway (dialer_gateway / DialerSingleWriter / DialerDatabaseLock / dialerDbGateway).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
