#!/usr/bin/env python3
"""
scan_repo.py — deterministic single-repo discovery.

Reads up to ~15 well-known manifest files in a repo, classifies the stack,
infers build/test/lint/audit commands, and prints one JSON object on stdout.

Stdlib only. No network. Idempotent.

Usage:
  python scripts/scan_repo.py --root /path/to/repo --name short-name

Output: a single JSON object on stdout matching the per-repo schema in
references/context-schema.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# ── detection tables ────────────────────────────────────────────────────────

LANG_MANIFESTS = {
    "csharp":   ["*.csproj", "*.sln", "global.json", "Directory.Build.props"],
    "typescript": ["package.json", "tsconfig.json"],
    "javascript": ["package.json"],
    "python":   ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"],
    "go":       ["go.mod"],
    "rust":     ["Cargo.toml"],
    "java":     ["pom.xml", "build.gradle", "build.gradle.kts"],
}

FRAMEWORK_MARKERS = {
    "aspnetcore":  ("csharp", lambda p: "Microsoft.AspNetCore" in p),
    "angular":     ("typescript", lambda p: '"@angular/core"' in p),
    "react":       ("typescript", lambda p: '"react"' in p),
    "vue":         ("typescript", lambda p: '"vue"' in p),
    "django":      ("python", lambda p: "django" in p.lower()),
    "fastapi":     ("python", lambda p: "fastapi" in p.lower()),
    "nestjs":      ("typescript", lambda p: '"@nestjs/core"' in p),
}

PACKAGE_MANAGERS = {
    "package.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "*.csproj": "nuget",
    "pyproject.toml": "pip",
    "Pipfile": "pipenv",
    "go.mod": "go",
    "Cargo.toml": "cargo",
}


# ── helpers ────────────────────────────────────────────────────────────────

def read_text(p: Path, limit: int = 8000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def find_one(root: Path, glob: str) -> Path | None:
    # search at depth 1–2 only; CI configs are sometimes nested
    for depth in (1, 2):
        for p in root.glob("/".join(["*"] * (depth - 1) + [glob])) if depth > 1 else root.glob(glob):
            if p.is_file():
                return p
    return None


def find_all(root: Path, glob: str, max_depth: int = 2, limit: int = 5) -> list[Path]:
    out: list[Path] = []
    for depth in range(1, max_depth + 1):
        pattern = "/".join(["*"] * (depth - 1) + [glob]) if depth > 1 else glob
        for p in root.glob(pattern):
            if p.is_file():
                out.append(p)
                if len(out) >= limit:
                    return out
    return out


# ── detection ──────────────────────────────────────────────────────────────

def detect_languages(root: Path) -> list[str]:
    found = set()
    for lang, manifests in LANG_MANIFESTS.items():
        if any(find_one(root, m) for m in manifests):
            found.add(lang)
    return sorted(found)


def detect_frameworks(root: Path) -> list[str]:
    out: list[str] = []
    pkg_json = read_text(root / "package.json")
    csprojs = find_all(root, "*.csproj", max_depth=3, limit=3)
    csproj_text = "\n".join(read_text(p) for p in csprojs)
    py_text = read_text(root / "pyproject.toml") + read_text(root / "requirements.txt")

    for name, (lang, predicate) in FRAMEWORK_MARKERS.items():
        text = {"typescript": pkg_json, "javascript": pkg_json,
                "csharp": csproj_text, "python": py_text}.get(lang, "")
        if text and predicate(text):
            out.append(name)
    return out


def detect_package_managers(root: Path) -> list[str]:
    out = set()
    for pat, name in PACKAGE_MANAGERS.items():
        if find_one(root, pat):
            out.add(name)
    return sorted(out)


def detect_runtime(root: Path) -> list[str]:
    runtime = []
    nvm = read_text(root / ".nvmrc").strip() or read_text(root / ".tool-versions")
    if nvm:
        m = re.search(r"\b(?:node[ -]?)?(\d+\.\d+(?:\.\d+)?)", nvm)
        if m:
            runtime.append(f"node-{m.group(1)}")
    gjson = read_text(root / "global.json")
    if gjson:
        m = re.search(r'"version"\s*:\s*"(\d+(?:\.\d+)*)', gjson)
        if m:
            runtime.append(f"dotnet-{m.group(1)}")
    py = read_text(root / ".python-version").strip()
    if py:
        runtime.append(f"python-{py}")
    return runtime


def infer_commands(root: Path, langs: list[str], pms: list[str]) -> dict[str, list[str]]:
    cmds = {"install": [], "build": [], "test_unit": [], "test_integration": [],
            "lint": [], "audit": []}

    if "csharp" in langs:
        cmds["install"].append("dotnet restore")
        cmds["build"].append("dotnet build --no-restore -c Release")
        cmds["test_unit"].append("dotnet test --no-build")
        cmds["lint"].append("dotnet format --verify-no-changes")
        cmds["audit"].append("dotnet list package --vulnerable --include-transitive")

    if "typescript" in langs or "javascript" in langs:
        pm = "npm"
        if "pnpm" in pms: pm = "pnpm"
        elif "yarn" in pms: pm = "yarn"
        cmds["install"].append({"npm": "npm ci", "pnpm": "pnpm install --frozen-lockfile",
                                 "yarn": "yarn install --frozen-lockfile"}[pm])
        # Inspect package.json scripts to refine
        pkg = read_text(root / "package.json")
        scripts = re.findall(r'"(build|test|lint)"\s*:\s*"[^"]+"', pkg)
        if '"build"' in pkg: cmds["build"].append(f"{pm} run build")
        if '"test"' in pkg: cmds["test_unit"].append(f"{pm} test -- --watch=false")
        if '"lint"' in pkg: cmds["lint"].append(f"{pm} run lint")
        cmds["audit"].append(f"{pm} audit --omit=dev" if pm == "npm" else f"{pm} audit")

    if "python" in langs:
        cmds["install"].append("pip install -e .")
        cmds["test_unit"].append("pytest")
        cmds["lint"].append("ruff check .")
        cmds["audit"].append("pip-audit")

    return cmds


def detect_layout(root: Path) -> dict[str, list[str]]:
    layout: dict[str, list[str]] = {"src": [], "tests": [], "frontend": [], "features": [], "docs": []}
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        n = child.name.lower()
        if n in ("src", "app", "lib"): layout["src"].append(f"{child.name}/")
        elif n in ("tests", "test", "__tests__", "spec"): layout["tests"].append(f"{child.name}/")
        elif n in ("web", "client", "ui", "frontend"): layout["frontend"].append(f"{child.name}/")
        elif n == "features": layout["features"].append(f"{child.name}/")
        elif n == "docs": layout["docs"].append(f"{child.name}/")
    return layout


def detect_conventions(root: Path) -> dict[str, str]:
    conv: dict[str, str] = {}
    # test framework — pick first matching test file
    for marker, name in [("[Fact]", "xunit + dotnet"),
                          ("[Test]", "nunit"),
                          ("describe(", "jest"),
                          ("test(", "jest"),
                          ("@pytest.fixture", "pytest")]:
        for tf in find_all(root, "*.cs", max_depth=4, limit=2) + find_all(root, "*.test.ts", max_depth=4, limit=2):
            if marker in read_text(tf, limit=2000):
                conv["test_framework"] = name
                break
        if "test_framework" in conv:
            break
    if (root / ".editorconfig").exists():
        conv["style"] = "see .editorconfig"
    return conv


# ── main ───────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--name", required=True)
    args = ap.parse_args()

    root: Path = args.root
    if not root.exists() or not root.is_dir():
        print(json.dumps({"name": args.name, "error": f"path not found: {root}"}))
        return 0  # not a script error — surface in JSON

    langs = detect_languages(root)
    fws = detect_frameworks(root)
    pms = detect_package_managers(root)
    runtime = detect_runtime(root)
    commands = infer_commands(root, langs, pms)
    layout = detect_layout(root)
    conv = detect_conventions(root)

    summary = ", ".join(filter(None, [", ".join(langs) or None, ", ".join(fws) or None]))[:80] or "unknown stack"

    print(json.dumps({
        "name": args.name,
        "root": str(root),
        "summary": summary,
        "stack": {
            "languages": langs,
            "frameworks": fws,
            "package_managers": pms,
            "runtime": runtime,
        },
        "commands": commands,
        "layout": layout,
        "conventions": conv,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
