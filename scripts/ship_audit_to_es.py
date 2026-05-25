#!/usr/bin/env python3
"""
ship_audit_to_es.py

Fallback shipper for environments without Filebeat. Reads JSONL files from
.copilot/audit/, posts to Elasticsearch _bulk, and renames shipped files
with .sent suffix so they aren't re-sent.

Env:
  ELASTIC_URL       e.g. https://es.internal:9200
  ELASTIC_USERNAME
  ELASTIC_PASSWORD
  ELASTIC_INDEX     default: copilot-audit (the write alias)
  AUDIT_DIR         default: ~/.copilot/audit
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path
from datetime import datetime, timezone


def env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None:
        sys.exit(f"missing env: {name}")
    return v


def basic_auth() -> str:
    return "Basic " + base64.b64encode(
        f"{env('ELASTIC_USERNAME')}:{env('ELASTIC_PASSWORD')}".encode()
    ).decode()


def bulk_lines(path: Path, index: str) -> bytes:
    out = bytearray()
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError:
                continue  # skip corrupt line
            doc.setdefault("@timestamp", datetime.now(timezone.utc).isoformat())
            out += json.dumps({"index": {"_index": index}}).encode() + b"\n"
            out += json.dumps(doc).encode() + b"\n"
    return bytes(out)


def post_bulk(url: str, body: bytes) -> dict:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url=f"{url.rstrip('/')}/_bulk",
        data=body,
        headers={
            "Authorization": basic_auth(),
            "Content-Type": "application/x-ndjson",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read())


def main() -> int:
    audit_dir = Path(env("AUDIT_DIR", str(Path.home() / ".copilot" / "audit")))
    if not audit_dir.exists():
        print(f"no audit dir: {audit_dir}")
        return 0
    index = env("ELASTIC_INDEX", "copilot-audit")
    url = env("ELASTIC_URL")
    files = sorted(audit_dir.glob("*.jsonl"))
    if not files:
        print("nothing to ship")
        return 0
    rc = 0
    for f in files:
        body = bulk_lines(f, index)
        if not body:
            f.rename(f.with_suffix(".jsonl.sent"))
            continue
        try:
            resp = post_bulk(url, body)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {f}: {e}", file=sys.stderr)
            rc = 1
            continue
        if resp.get("errors"):
            print(f"PARTIAL {f}: see ES response", file=sys.stderr)
            rc = 1
        else:
            f.rename(f.with_suffix(".jsonl.sent"))
            print(f"shipped {f}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
