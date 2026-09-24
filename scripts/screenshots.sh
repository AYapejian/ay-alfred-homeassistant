#!/usr/bin/env bash
# Capture documentation screenshots of the Alfred workflow against the demo HA.
#
# Drives the real Alfred window on your screen: for each line of
# docs/images/SHOTS.md it opens Alfred with a query, sends keystrokes, and
# captures only Alfred's window into docs/images/. Frames named hero-NN.png are
# stitched into docs/images/hero.gif and then deleted.
#
# While it runs, the workflow's HA_URL / HA_TOKEN point at the demo instance
# (127.0.0.1:8124). Your own values are backed up first and restored on exit —
# including on failure or Ctrl-C — then verified key by key. Values are never
# printed.
#
# Needs: demo HA running (make demo-ha-up), the workflow dev-installed, and for
# the app running this script: Accessibility (keystrokes) and Screen Recording
# (window capture) in System Settings → Privacy & Security.
#
# Usage: scripts/screenshots.sh [--check] [--only <name-substring>]
#   --check  run every preflight check, change nothing, drive nothing
#   --only   capture only shots whose filename contains the substring
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_ID="com.ayapejian.alfred-homeassistant"
ALFRED_ID="com.runningwithcrayons.Alfred"
SHOTS_FILE="$REPO_ROOT/docs/images/SHOTS.md"
OUT_DIR="$REPO_ROOT/docs/images"
DEMO_SH="$REPO_ROOT/scripts/demo-ha.sh"
SWIFT_SRC="$REPO_ROOT/scripts/screenshots/alfred_window.swift"
SETTLE="${SCREENSHOT_SETTLE:-1.5}"   # seconds to let Alfred render results
CONFIG_KEYS=(HA_URL HA_TOKEN)

CHECK_ONLY=0
ONLY=""
while (($#)); do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --only) ONLY="${2:?--only needs a value}"; shift ;;
    -h | --help) sed -n '2,21p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

log() { printf '[screenshots] %s\n' "$*" >&2; }
die() { printf '[screenshots] error: %s\n' "$*" >&2; exit 1; }

WORK="$(mktemp -d)"
chmod 700 "$WORK"
SWITCHED=0

# --- Alfred / workflow locations ---------------------------------------------

alfred_workflows_dir() {
  local sync
  sync="$(defaults read com.runningwithcrayons.Alfred-Preferences syncfolder 2>/dev/null || true)"
  if [[ -n "$sync" ]]; then
    printf '%s/Alfred.alfredpreferences/workflows' "${sync/#\~/$HOME}"
  else
    printf '%s/Library/Application Support/Alfred/Alfred.alfredpreferences/workflows' "$HOME"
  fi
}

WF_LINK="$(alfred_workflows_dir)/user.workflow.$BUNDLE_ID"
PREFS=""          # resolved in preflight
DATA_DIR="$HOME/Library/Application Support/Alfred/Workflow Data/$BUNDLE_ID"
CACHE_DIR="$HOME/Library/Caches/com.runningwithcrayons.Alfred/Workflow Data/$BUNDLE_ID"

# --- Alfred config switching (values travel via env, never argv) ------------

set_config() { # name value
  CFG_NAME="$1" CFG_VALUE="$2" CFG_WF="$BUNDLE_ID" osascript -e "
    tell application id \"$ALFRED_ID\" to set configuration (system attribute \"CFG_NAME\") ¬
      to value (system attribute \"CFG_VALUE\") in workflow (system attribute \"CFG_WF\")" >/dev/null
}

remove_config() { # name
  CFG_NAME="$1" CFG_WF="$BUNDLE_ID" osascript -e "
    tell application id \"$ALFRED_ID\" to remove configuration (system attribute \"CFG_NAME\") ¬
      in workflow (system attribute \"CFG_WF\")" >/dev/null
}

plist_has() { plutil -extract "$1" raw -o /dev/null "$2" >/dev/null 2>&1; }
plist_get() { plutil -extract "$1" raw -o - "$2" 2>/dev/null; }

verify_restored() { # prints nothing secret; returns 0 when every key matches
  local key ok=0
  for key in "${CONFIG_KEYS[@]}"; do
    if plist_has "$key" "$WORK/prefs.backup"; then
      if [[ "$(plist_get "$key" "$PREFS")" == "$(plist_get "$key" "$WORK/prefs.backup")" ]]; then
        log "restore check: $key match"
      else
        log "restore check: $key MISMATCH"; ok=1
      fi
    elif plist_has "$key" "$PREFS"; then
      log "restore check: $key should be unset but is set"; ok=1
    else
      log "restore check: $key unset (as before)"
    fi
  done
  return "$ok"
}

restore_config() {
  ((SWITCHED)) || return 0
  log "restoring your workflow configuration"
  osascript -e 'tell application "System Events" to key code 53' >/dev/null 2>&1 || true
  local key
  for key in "${CONFIG_KEYS[@]}"; do
    if plist_has "$key" "$WORK/prefs.backup"; then
      set_config "$key" "$(plist_get "$key" "$WORK/prefs.backup")" || true
    else
      remove_config "$key" || true
    fi
  done
  sleep 1
  if ! verify_restored; then
    log "falling back to copying the backup file into place and reloading the workflow"
    cp -p "$WORK/prefs.backup" "$PREFS"
    osascript -e "tell application id \"$ALFRED_ID\" to reload workflow \"$BUNDLE_ID\"" >/dev/null || true
    sleep 1
    verify_restored || log "RESTORE FAILED — backup kept at $WORK/prefs.backup (mode 600); do not delete it"
    SWITCHED=0
    return
  fi
  SWITCHED=0
}

cleanup() {
  local rc=$?
  restore_config
  # Keep the backup only if restore failed (message above says where).
  if [[ ! -f "$WORK/prefs.backup" ]] || verify_restored >/dev/null 2>&1; then
    rm -rf "$WORK"
  fi
  exit "$rc"
}
trap cleanup EXIT INT TERM

# --- Preflight ------------------------------------------------------------------

preflight() {
  local fail=0
  check() { # description, command...
    local desc="$1"; shift
    if "$@" >/dev/null 2>&1; then log "ok    $desc"; else log "FAIL  $desc"; fail=1; fi
  }

  check "demo HA answering with a valid token" bash -c "\"$DEMO_SH\" status | grep -q 'token: .* is valid'"
  check "Alfred is running" pgrep -x Alfred
  check "workflow is dev-installed ($WF_LINK)" test -L "$WF_LINK"
  if [[ -L "$WF_LINK" ]]; then
    PREFS="$(cd "$WF_LINK" && pwd -P)/prefs.plist"
    check "workflow configuration file exists" test -f "$PREFS"
    check "configuration has an HA_URL entry (value not read)" plist_has HA_URL "$PREFS"
  fi
  # Per-server storage moves legacy flat files into whichever server is
  # configured on first run. That first run must be YOUR server, not the demo.
  check "one-time storage migration already done for your server" \
    test -f "$DATA_DIR/servers/.legacy-migrated"
  check "no legacy flat usage.db left behind" test ! -e "$DATA_DIR/usage.db"
  check "swift compiler available" command -v swiftc
  check "ffmpeg available (for hero.gif)" command -v ffmpeg
  check "shot list exists ($SHOTS_FILE)" test -f "$SHOTS_FILE"
  check "Accessibility permission (System Events keystrokes)" \
    osascript -e 'tell application "System Events" to get name of first process'

  if ((fail)); then
    if [[ ! -f "$DATA_DIR/servers/.legacy-migrated" ]]; then
      log "→ open Alfred and run one normal 'ha' search against YOUR server first; it performs the one-time migration."
    fi
    die "preflight failed"
  fi
}

compile_helper() {
  swiftc -O -o "$WORK/alfred_window" "$SWIFT_SRC" >/dev/null 2>&1 || die "could not compile $SWIFT_SRC"
}

# --- Driving Alfred -----------------------------------------------------------

alfred_search() { # query (full Alfred text, e.g. "ha kitchen")
  Q="$1" osascript -e "tell application id \"$ALFRED_ID\" to search (system attribute \"Q\")" >/dev/null
}

send_keys() { # space-separated tokens: none enter cmd+enter alt+enter ctrl+enter down up tab esc type:<text> wait:<sec>
  local tok
  for tok in $1; do
    case "$tok" in
      none | "") ;;
      enter) osascript -e 'tell application "System Events" to key code 36' ;;
      cmd+enter) osascript -e 'tell application "System Events" to key code 36 using {command down}' ;;
      alt+enter) osascript -e 'tell application "System Events" to key code 36 using {option down}' ;;
      ctrl+enter) osascript -e 'tell application "System Events" to key code 36 using {control down}' ;;
      down) osascript -e 'tell application "System Events" to key code 125' ;;
      up) osascript -e 'tell application "System Events" to key code 126' ;;
      tab) osascript -e 'tell application "System Events" to key code 48' ;;
      esc) osascript -e 'tell application "System Events" to key code 53' ;;
      type:*) T="${tok#type:}" osascript -e 'tell application "System Events" to keystroke (system attribute "T")' ;;
      wait:*) sleep "${tok#wait:}" ;;
      *) die "unknown keystroke token: $tok" ;;
    esac
    sleep 0.4
  done
}

capture() { # output path
  local info id
  info="$("$WORK/alfred_window")" || die "Alfred window not found on screen"
  id="${info%% *}"
  screencapture -o -x -l "$id" "$1"
  [[ -s "$1" ]] || die "screencapture produced nothing for $1 (Screen Recording permission?)"
}

# SHOTS.md lines: `file.png | query after 'ha ' | keystrokes | what must be visible`
shot_lines() {
  grep -E '^[[:space:]]*`?[A-Za-z0-9._-]+\.png`?[[:space:]]*\|' "$SHOTS_FILE"
}

trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; s="${s#\`}"; printf '%s' "${s%\`}"; }

build_gif() {
  local frames=("$OUT_DIR"/hero-*.png)
  [[ -e "${frames[0]}" ]] || return 0
  log "building hero.gif from ${#frames[@]} frames"
  local w h
  read -r w h < <(for f in "${frames[@]}"; do sips -g pixelWidth -g pixelHeight "$f" | awk '/pixelWidth/{w=$2}/pixelHeight/{h=$2}END{print w, h}'; done \
    | awk '{if($1>w)w=$1; if($2>h)h=$2} END{print w, h}')
  ffmpeg -loglevel error -y -framerate 1 -pattern_type glob -i "$OUT_DIR/hero-*.png" \
    -vf "pad=${w}:${h}:0:0:color=0x00000000,split[a][b];[a]palettegen=reserve_transparent=1[p];[b][p]paletteuse" \
    -loop 0 "$OUT_DIR/hero.gif"
  rm -f "${frames[@]}"
}

# --- Main -----------------------------------------------------------------------

preflight
compile_helper
if ((CHECK_ONLY)); then
  log "window helper compiled; --check complete, nothing changed"
  exit 0
fi

eval "$("$DEMO_SH" env)"   # sets HA_URL / HA_TOKEN to the demo instance
cp -p "$PREFS" "$WORK/prefs.backup"
chmod 600 "$WORK/prefs.backup"

log "pointing the workflow at the demo HA"
SWITCHED=1
set_config HA_URL "$HA_URL"
set_config HA_TOKEN "$HA_TOKEN"

log "warming the demo server's cache (its own per-server directory)"
alfred_workflow_cache="$CACHE_DIR" alfred_workflow_data="$DATA_DIR" \
  /usr/bin/python3 "$REPO_ROOT/src/ha_workflow/cli.py" cache refresh >/dev/null

mkdir -p "$OUT_DIR"
count=0
while IFS='|' read -r file query keys _; do
  file="$(trim "$file")"; query="$(trim "$query")"; keys="$(trim "$keys")"
  [[ -z "$ONLY" || "$file" == *"$ONLY"* ]] || continue
  log "shot $file  ←  ha $query  [$keys]"
  alfred_search "ha $query"
  sleep "$SETTLE"
  send_keys "$keys"
  sleep "$SETTLE"
  capture "$OUT_DIR/$file"
  osascript -e 'tell application "System Events" to key code 53' >/dev/null
  sleep 0.5
  count=$((count + 1))
done < <(shot_lines)

build_gif
log "captured $count shot(s) into docs/images/"
