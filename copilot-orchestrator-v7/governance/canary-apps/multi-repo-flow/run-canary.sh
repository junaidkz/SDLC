#!/usr/bin/env bash
# Canary: multi-repo flow.
# Verifies that scan-repo handles N repos in one application correctly.
# Run from the .github-private repo root.

set -euo pipefail

CANARY_DIR="$(dirname "$0")"
WORK="$(mktemp -d)"

cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

# Build two fake repos
mkdir -p "$WORK/canary-payments-api"
cat > "$WORK/canary-payments-api/MyApp.csproj" << 'EOF'
<Project Sdk="Microsoft.AspNetCore.App"><PropertyGroup><TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>
EOF
cat > "$WORK/canary-payments-api/global.json" << 'EOF'
{ "sdk": { "version": "8.0.100" } }
EOF

mkdir -p "$WORK/canary-payments-frontend"
cat > "$WORK/canary-payments-frontend/package.json" << 'EOF'
{ "name":"fe","scripts":{"build":"tsc","test":"jest","lint":"eslint ."},"dependencies":{"@angular/core":"^17.0.0"} }
EOF
echo "20.0.0" > "$WORK/canary-payments-frontend/.nvmrc"

# Scan each
RESULT_API=$(python skills/scan-repo/scripts/scan_repo.py --root "$WORK/canary-payments-api" --name canary-payments-api)
RESULT_FE=$(python skills/scan-repo/scripts/scan_repo.py --root "$WORK/canary-payments-frontend" --name canary-payments-frontend)

# Assert detected stacks
echo "$RESULT_API" | python -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'csharp' in d['stack']['languages'], f'expected csharp; got {d[\"stack\"][\"languages\"]}'
assert 'aspnetcore' in d['stack']['frameworks'], f'expected aspnetcore; got {d[\"stack\"][\"frameworks\"]}'
print('  ✓ api detected csharp + aspnetcore')
"
echo "$RESULT_FE" | python -c "
import json, sys
d = json.loads(sys.stdin.read())
assert 'typescript' in d['stack']['languages'], f'expected typescript; got {d[\"stack\"][\"languages\"]}'
assert 'angular' in d['stack']['frameworks'], f'expected angular; got {d[\"stack\"][\"frameworks\"]}'
print('  ✓ frontend detected typescript + angular')
"

# Build combined context.json — the shape the orchestrator agents consume
python - << PY
import json, sys, datetime
combined = {
  "version": 2,
  "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
  "application": "canary-payments-api",
  "repos": {
    "canary-payments-api":      $(python skills/scan-repo/scripts/scan_repo.py --root "$WORK/canary-payments-api" --name canary-payments-api),
    "canary-payments-frontend": $(python skills/scan-repo/scripts/scan_repo.py --root "$WORK/canary-payments-frontend" --name canary-payments-frontend),
  },
  "guardrails": {"no_install_without_adr": True, "no_eval_from_untrusted": True},
}
assert len(combined["repos"]) == 2, "expected 2 repos in combined context"
assert combined["repos"]["canary-payments-api"]["stack"]["languages"]
assert combined["repos"]["canary-payments-frontend"]["stack"]["languages"]
print('  ✓ combined context has both repos with non-empty stacks')
PY

echo "CANARY PASSED: multi-repo-flow"
