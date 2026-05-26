#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PREFECT_URL="http://localhost:4200/api"
POOL_NAME="local-pool"
PROFILE_NAME="hazlo"

cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

section() {
    echo ""
    echo -e "${BOLD}━━━ $* ━━━${NC}"
}

ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
info() { echo -e "  ${CYAN}→${NC} $*"; }
warn() { echo -e "  ${YELLOW}!${NC} $*"; }
fail() { echo -e "  ${RED}✗${NC} $*"; }

section "1. Docker services"

if ! docker compose ps --format json 2>/dev/null | grep -q .; then
    fail "Docker services not running. Start them first:"
    echo ""
    echo "    docker compose up -d"
    echo ""
    exit 1
fi

HEALTHY=$(docker compose ps --format json 2>/dev/null | python3 -c "
import json, sys
lines = [l.strip() for l in sys.stdin if l.strip()]
statuses = [json.loads(l).get('Health', '') for l in lines]
unhealthy = [s for s in statuses if s not in ('healthy', '')]
print('OK' if not unhealthy else 'UNHEALTHY')
")

if [ "$HEALTHY" != "OK" ]; then
    warn "Some services not healthy yet. Waiting..."
    sleep 10
fi

ok "Docker services running"

section "2. Prefect CLI profile"

EXISTING=$(prefect profile ls 2>/dev/null | grep -c "$PROFILE_NAME" || true)
if [ "$EXISTING" -eq 0 ]; then
    prefect profile create "$PROFILE_NAME"
    ok "Profile '$PROFILE_NAME' created"
else
    ok "Profile '$PROFILE_NAME' already exists"
fi

prefect -p "$PROFILE_NAME" config set PREFECT_API_URL="$PREFECT_URL"
prefect profile use "$PROFILE_NAME"
ok "PREFECT_API_URL = $PREFECT_URL"

section "3. Prefect server health"

MAX_ATTEMPTS=12
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -sf "$PREFECT_URL/health" > /dev/null 2>&1; then
        ok "Server healthy at $PREFECT_URL"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        fail "Server not reachable after ${MAX_ATTEMPTS} attempts"
        exit 1
    fi
    info "Waiting for server... (${ATTEMPT}/${MAX_ATTEMPTS})"
    sleep 5
done

section "4. Work pool"

POOL_EXISTS=$(curl -sf -X POST "$PREFECT_URL/work_pools/filter" \
    -H "Content-Type: application/json" \
    -d '{}' | python3 -c "
import json, sys
pools = json.load(sys.stdin)
match = [p for p in pools if p['name'] == '$POOL_NAME']
print('yes' if match else 'no')
")

if [ "$POOL_EXISTS" = "no" ]; then
    prefect work-pool create "$POOL_NAME" --type process
    ok "Work pool '$POOL_NAME' created"
else
    ok "Work pool '$POOL_NAME' already exists"
fi

section "5. Deploy flows"

if ! uv run python -c "import prefect" 2>/dev/null; then
    fail "Project dependencies not installed. Run: uv sync"
    exit 1
fi

uv run python -m hazlo.infrastructure.prefect.deployments
ok "Flows deployed"

section "6. Verify"

DEPLOYMENTS=$(curl -sf -X POST "$PREFECT_URL/deployments/filter" \
    -H "Content-Type: application/json" \
    -d '{}' | python3 -c "
import json, sys
deps = json.load(sys.stdin)
for d in deps:
    print(f\"    • {d['name']} ({d.get('flow_name', '?')}) [{'paused' if d.get('paused', False) else 'active'}]\")
")

echo -e "  ${BOLD}Deployments:${NC}"
echo "$DEPLOYMENTS"

echo ""
echo -e "  ${BOLD}Work pools:${NC}"
curl -sf -X POST "$PREFECT_URL/work_pools/filter" \
    -H "Content-Type: application/json" \
    -d '{}' | python3 -c "
import json, sys
pools = json.load(sys.stdin)
for p in pools:
    print(f\"    • {p['name']} ({p['type']}) [{p.get('status', '?')}]\")
"

echo ""
echo -e "${BOLD}━━━ Done ━━━${NC}"
echo ""
echo -e "  Prefect UI:   ${CYAN}http://localhost:4200${NC}"
echo -e "  Deploy flows: ${CYAN}mise run deploy-flows${NC}"
echo -e "  Setup again:  ${CYAN}bash scripts/setup-prefect.sh${NC}"
echo ""
