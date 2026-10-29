#!/usr/bin/env bash
# Install "speak" (read replies aloud) for every AI agent found on this machine.
# macOS, Linux and WSL. On Windows use install.ps1.
#
#   ./install.sh            install / update
#   ./install.sh --dry-run  show what would change, change nothing
#   ./install.sh --no-edge  skip installing the natural voice (edge-tts)
set -euo pipefail

DRY=0; EDGE=1
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --no-edge) EDGE=0 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
  esac
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="$REPO/skills/speak"
HOME_DIR="${SPEAK_HOME:-$HOME/.speak}"
SCRIPT="$HOME_DIR/speak.py"   # stable copy for agents wired by path (Codex, Grok)

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
note() { printf '  %s\n' "$*"; }
run()  { if [ "$DRY" = 1 ]; then note "[dry-run] $*"; else "$@"; fi; }

PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || { echo "Python 3 is required: https://www.python.org/downloads/"; exit 1; }

say "1. Engine -> $SCRIPT"
run mkdir -p "$HOME_DIR"
run cp "$SKILL/scripts/speak.py" "$SCRIPT"

say "2. Natural voice (edge-tts)"
if command -v edge-tts >/dev/null || "$PY" -c "import edge_tts" 2>/dev/null; then
  note "already installed"
elif [ "$EDGE" = 0 ]; then
  note "skipped (--no-edge): the built-in system voice will be used"
elif command -v uv >/dev/null; then run uv tool install edge-tts
elif command -v pipx >/dev/null; then run pipx install edge-tts
else run "$PY" -m pip install --user edge-tts || note "couldn't install edge-tts; the system voice will be used"
fi

case "$(uname -s)" in
  Darwin) ;;  # afplay and say are built in
  Linux)
    if ! grep -qi microsoft /proc/version 2>/dev/null; then
      command -v mpv >/dev/null || command -v ffplay >/dev/null || command -v mpg123 >/dev/null \
        || note "Linux: install an MP3 player for the natural voice, e.g. sudo apt install mpv"
      command -v spd-say >/dev/null || command -v espeak-ng >/dev/null || command -v espeak >/dev/null \
        || note "Linux: install an offline voice, e.g. sudo apt install espeak-ng"
    fi ;;
esac

say "3. Agents"
found=0

if command -v claude >/dev/null; then
  found=1; note "Claude Code: plugin speak@speak"
  run claude plugin marketplace add "$REPO" || true
  run claude plugin install speak@speak || true
fi

if command -v agy >/dev/null; then
  found=1; note "Antigravity: plugin speak"
  run agy plugin install "$REPO" || true
fi

if command -v codex >/dev/null || [ -d "$HOME/.codex" ]; then
  found=1; CFG="$HOME/.codex/config.toml"
  LINE="notify = [\"$PY\", \"$SCRIPT\"]"
  if grep -qs '^notify *=' "$CFG"; then
    if grep -qs "speak.py" "$CFG"; then note "Codex: already set up"
    else note "Codex: you already have a notify command, so I left it alone. To use speak, change it to:"
         note "  $LINE"
    fi
  else
    note "Codex: adding to $CFG -> $LINE"
    if [ "$DRY" = 0 ]; then
      mkdir -p "$HOME/.codex"; touch "$CFG"
      # notify must be a top-level key, so it goes above any [section].
      { echo "$LINE"; cat "$CFG"; } > "$CFG.speak-tmp" && mv "$CFG.speak-tmp" "$CFG"
    fi
  fi
  run mkdir -p "$HOME/.codex/skills"
  run cp -r "$SKILL" "$HOME/.codex/skills/"
  # Prompt hook: stops speech on a new prompt and gives Codex the persona (/speak:speak jarvis).
  note "Codex: UserPromptSubmit hook in ~/.codex/hooks.json (approve it once with /hooks)"
  [ "$DRY" = 1 ] || "$PY" - "$HOME/.codex/hooks.json" "\"$PY\" \"$SCRIPT\" --stop" <<'EOF' || true
import json, sys
from pathlib import Path
path, cmd = Path(sys.argv[1]), sys.argv[2]
try:
    data = json.loads(path.read_text()) if path.exists() else {}
except ValueError:
    sys.exit(f"  {path} isn't valid JSON, so I left it alone. Add a UserPromptSubmit hook: {cmd}")
groups = data.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
if not any("speak.py" in h.get("command", "") for g in groups for h in g.get("hooks", [])):
    groups.append({"hooks": [{"type": "command", "command": cmd}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
EOF
fi

if command -v grok >/dev/null || [ -d "$HOME/.grok" ]; then
  found=1; note "Grok: hook file ~/.grok/hooks/speak.json"
  if [ "$DRY" = 0 ]; then
    mkdir -p "$HOME/.grok/hooks"
    cat > "$HOME/.grok/hooks/speak.json" <<EOF
{
  "hooks": {
    "Stop": [{ "hooks": [{ "type": "command", "command": "\"$PY\" \"$SCRIPT\"" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "\"$PY\" \"$SCRIPT\" --stop" }] }]
  }
}
EOF
  fi
fi

[ "$found" = 1 ] || note "No supported agent found. Pipe any text in:  echo hello | $PY $SCRIPT --text"

say "4. Check"
[ "$DRY" = 1 ] || "$PY" "$SCRIPT" --doctor
say "Done. Restart your agent, then try /speak:speak status (or /speak:speak quick, /speak:speak off ...)."
