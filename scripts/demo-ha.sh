#!/usr/bin/env bash
# Throwaway demo Home Assistant in Docker (HA's built-in `demo` integration).
#
# Binds to 127.0.0.1:8124 only. Credentials are demo-only: demo / demo-password.
# See demo/README.md.
#
# Usage: scripts/demo-ha.sh <up|token|seed|down|reset|status|env>
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="$REPO_ROOT/demo"
CONFIG_DIR="$DEMO_DIR/config"
COMPOSE_FILE="$DEMO_DIR/docker-compose.yml"
TOKEN_FILE="$DEMO_DIR/.demo-token"
HELPER="$REPO_ROOT/scripts/demo_ha_helper.py"
DEMO_URL="http://127.0.0.1:8124"
READY_TIMEOUT="${DEMO_HA_READY_TIMEOUT:-240}"

log() { printf '[demo-ha] %s\n' "$*" >&2; }
die() { printf '[demo-ha] error: %s\n' "$*" >&2; exit 1; }

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

helper() {
  command -v uv >/dev/null 2>&1 || die "uv is required (https://docs.astral.sh/uv/)"
  uv run --quiet --no-project --with websockets python "$HELPER" --url "$DEMO_URL" "$@"
}

require_docker() {
  command -v docker >/dev/null 2>&1 || die "docker is not installed"
  docker info >/dev/null 2>&1 || die "docker daemon is not reachable (is Docker Desktop running?)"
}

# HTTP status of GET /api/onboarding, or 000 when HA is not answering yet.
onboarding_http_status() {
  curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$DEMO_URL/api/onboarding" || true
}

wait_ready() {
  local deadline=$((SECONDS + READY_TIMEOUT)) code
  log "waiting for Home Assistant at $DEMO_URL (up to ${READY_TIMEOUT}s)..."
  while ((SECONDS < deadline)); do
    # The unauthenticated onboarding status endpoint answers 200 once the HTTP
    # stack is up, whether or not onboarding is done. (Probing /api/ without a
    # token would log an invalid-auth warning on every poll.)
    code="$(onboarding_http_status)"
    if [[ "$code" == "200" ]]; then
      log "Home Assistant is answering"
      return 0
    fi
    sleep 3
  done
  compose logs --tail 40 homeassistant >&2 || true
  die "Home Assistant did not become ready within ${READY_TIMEOUT}s"
}

wait_demo_entities() {
  # The demo integration sets up asynchronously after HTTP is up.
  local deadline=$((SECONDS + 120)) token count
  token="$(cat "$TOKEN_FILE")"
  while ((SECONDS < deadline)); do
    count="$(curl -s --max-time 10 -H "Authorization: Bearer $token" "$DEMO_URL/api/states" \
      | python3 -c 'import json,sys; print(sum(1 for s in json.load(sys.stdin) if s["entity_id"].startswith("light.")))' \
      2>/dev/null || echo 0)"
    if [[ "$count" -gt 0 ]]; then
      return 0
    fi
    sleep 3
  done
  die "demo entities did not appear within 120s (is 'demo:' in demo/config/configuration.yaml?)"
}

token_valid() {
  [[ -s "$TOKEN_FILE" ]] || return 1
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 \
    -H "Authorization: Bearer $(cat "$TOKEN_FILE")" "$DEMO_URL/api/" || true)"
  [[ "$code" == "200" ]]
}

cmd_up() {
  require_docker
  log "starting container"
  compose up -d
  wait_ready
  helper onboard
  if token_valid; then
    log "existing token in demo/.demo-token is valid"
  else
    helper token --token-file "$TOKEN_FILE"
  fi
  wait_demo_entities
  helper seed
  log "ready: $DEMO_URL  (login demo / demo-password)"
  log "point the workflow CLI at it with: eval \"\$(scripts/demo-ha.sh env)\""
}

cmd_token() {
  require_docker
  wait_ready
  helper token --token-file "$TOKEN_FILE"
}

cmd_seed() {
  require_docker
  wait_ready
  helper seed
}

cmd_down() {
  require_docker
  compose down
}

cmd_reset() {
  require_docker
  compose down
  # Guard: only ever wipe the demo config directory inside this repo.
  [[ -f "$CONFIG_DIR/configuration.yaml" && "$CONFIG_DIR" == "$REPO_ROOT/demo/config" ]] \
    || die "refusing to reset: unexpected config dir $CONFIG_DIR"
  log "wiping runtime state in demo/config (keeping configuration.yaml) and the token"
  find "$CONFIG_DIR" -mindepth 1 -maxdepth 1 ! -name configuration.yaml -exec rm -rf {} +
  rm -f "$TOKEN_FILE"
  log "reset done; run 'scripts/demo-ha.sh up' for a fresh, onboarded instance"
}

cmd_status() {
  require_docker
  compose ps
  local code
  code="$(onboarding_http_status)"
  if [[ "$code" == "200" ]]; then
    echo "api: answering at $DEMO_URL"
  else
    echo "api: not answering at $DEMO_URL (HTTP $code)"
  fi
  if [[ ! -s "$TOKEN_FILE" ]]; then
    echo "token: none (run: scripts/demo-ha.sh token)"
  elif token_valid; then
    echo "token: demo/.demo-token is valid"
  else
    echo "token: demo/.demo-token present but not accepted (run: scripts/demo-ha.sh token)"
  fi
}

cmd_env() {
  [[ -s "$TOKEN_FILE" ]] || die "no token yet; run 'scripts/demo-ha.sh up' (or 'token') first"
  # The one place the token is emitted: stdout, for `eval "$(scripts/demo-ha.sh env)"`.
  printf 'export HA_URL=%q\n' "$DEMO_URL"
  printf 'export HA_TOKEN=%q\n' "$(tr -d '[:space:]' <"$TOKEN_FILE")"
}

usage() {
  cat >&2 <<'EOF'
Usage: scripts/demo-ha.sh <command>

  up      start the demo HA, wait for it, finish onboarding, ensure a token, seed
  token   create/replace the long-lived token in demo/.demo-token (mode 600)
  seed    (re)apply demo areas and the alfred_preferred label (idempotent)
  down    stop and remove the container (state in demo/config is kept)
  reset   stop and wipe all runtime state -> next 'up' onboards from scratch
  status  show container, API and token status
  env     print 'export HA_URL=... HA_TOKEN=...' for: eval "$(scripts/demo-ha.sh env)"

Demo-only instance on 127.0.0.1:8124, login demo / demo-password.
EOF
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    up) cmd_up ;;
    token) cmd_token ;;
    seed) cmd_seed ;;
    down) cmd_down ;;
    reset) cmd_reset ;;
    status) cmd_status ;;
    env) cmd_env ;;
    -h | --help | help | "") usage; [[ -n "$cmd" ]] ;;
    *) usage; die "unknown command: $cmd" ;;
  esac
}

main "$@"
