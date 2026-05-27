#!/usr/bin/env python3
"""
query_catalog.py — query a service catalog for an application's repos.

Reads .copilot/catalog.json for provider config. Writes
.copilot/application.json with the resolved repo list. Stdlib only.

Exit codes:
  0  hit (file written)
  1  miss (no match in catalog; caller should ask user manually)
  2  error (config invalid, network, auth) — message on stderr

Usage:
  python scripts/query_catalog.py --app <name>
  python scripts/query_catalog.py --app <name> --config .copilot/catalog.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def die(rc: int, msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(rc)


def load_config(path: Path) -> dict:
    if not path.exists():
        die(2, f"no catalog config at {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(2, f"invalid catalog config: {e}")
    return {}


def auth_header(cfg: dict) -> dict[str, str]:
    auth = cfg.get("auth") or {}
    kind = (auth.get("type") or "none").lower()
    if kind == "none":
        return {}
    if kind == "bearer":
        token_env = auth.get("token_env") or "CATALOG_TOKEN"
        token = os.environ.get(token_env)
        if not token:
            die(2, f"missing env: {token_env}")
        return {"Authorization": f"Bearer {token}"}
    if kind == "basic":
        u, p = os.environ.get(auth.get("user_env", "")), os.environ.get(auth.get("pass_env", ""))
        if not u or not p:
            die(2, "missing basic auth env vars")
        return {"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()}
    die(2, f"unsupported auth.type: {kind}")
    return {}


def fetch_json(url: str, headers: dict[str, str], timeout: float = 15.0) -> tuple[int, object]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, None
        die(2, f"HTTP {e.code} from catalog: {e.reason}")
    except urllib.error.URLError as e:
        die(2, f"network error: {e.reason}")
    return 0, None


def get_path(obj: object, path: str) -> object:
    """Walk a dotted path through nested dicts/lists. Returns None on miss."""
    cur: object = obj
    for part in path.split("."):
        if part == "":
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        else:
            return None
        if cur is None:
            return None
    return cur


def normalize_repo(raw: object, cfg: dict) -> dict | None:
    """Project a provider-specific repo entry to our schema."""
    if isinstance(raw, str):
        # Plain URL
        return {"name": raw.rstrip("/").split("/")[-1].removesuffix(".git"),
                "url": raw, "default_branch": "main", "local_path": None, "role": "supporting"}
    if not isinstance(raw, dict):
        return None
    map_ = cfg.get("repo_field_map", {})
    url = get_path(raw, map_.get("url", "url"))
    if not url:
        return None
    return {
        "name": get_path(raw, map_.get("name", "name")) or str(url).rstrip("/").split("/")[-1].removesuffix(".git"),
        "url": str(url),
        "default_branch": get_path(raw, map_.get("default_branch", "default_branch")) or "main",
        "local_path": get_path(raw, map_.get("local_path", "local_path")),
        "role": get_path(raw, map_.get("role", "role")) or "supporting",
    }


def query_backstage(app: str, cfg: dict) -> list[dict]:
    base = cfg["url"].rstrip("/")
    headers = auth_header(cfg)
    url = f"{base}/entities/by-name/component/{urllib.parse.quote(app)}"
    status, data = fetch_json(url, headers)
    if status == 404 or data is None:
        return []
    # Backstage stores repo in spec.source.location or metadata.annotations
    repos: list[dict] = []
    primary = (get_path(data, "spec.source.location")
               or get_path(data, "metadata.annotations.backstage.io/source-location")
               or get_path(data, "metadata.annotations.github.com/project-slug"))
    if primary:
        repos.append({"name": app, "url": str(primary).removeprefix("url:"),
                      "default_branch": "main", "local_path": None, "role": "primary"})
    # Subcomponents
    for sub in get_path(data, "spec.subcomponentOf") or []:
        n = normalize_repo(sub, cfg)
        if n:
            repos.append(n)
    return repos


def query_custom(app: str, cfg: dict) -> list[dict]:
    pattern = cfg.get("url_pattern")
    if not pattern:
        die(2, "custom provider needs url_pattern")
    url = pattern.replace("{app}", urllib.parse.quote(app))
    headers = auth_header(cfg)
    status, data = fetch_json(url, headers)
    if status == 404 or data is None:
        return []
    repos_raw = get_path(data, cfg.get("response_path", "repos"))
    if not isinstance(repos_raw, list):
        return []
    out: list[dict] = []
    for entry in repos_raw:
        n = normalize_repo(entry, cfg)
        if n:
            out.append(n)
    return out


def write_application_json(app: str, owner: str, source: str, repos: list[dict]) -> Path:
    out = Path(".copilot/application.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": {"name": app, "owner": owner, "source": source},
        "repos": repos,
    }
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", required=True)
    ap.add_argument("--config", default=".copilot/catalog.json")
    args = ap.parse_args()

    cfg = load_config(Path(args.config))
    provider = (cfg.get("type") or "custom").lower()

    if provider == "backstage":
        repos = query_backstage(args.app, cfg)
        owner = "unknown"  # backstage owner lookup omitted for stdlib brevity
    elif provider == "custom":
        repos = query_custom(args.app, cfg)
        owner = "unknown"
    else:
        die(2, f"unsupported provider: {provider}")
        return 2

    if not repos:
        print(f"no repos found for application: {args.app}", file=sys.stderr)
        return 1

    out = write_application_json(args.app, owner, provider, repos)
    print(f"wrote {out} with {len(repos)} repo(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
