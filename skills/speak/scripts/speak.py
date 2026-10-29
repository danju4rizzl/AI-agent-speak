#!/usr/bin/env python3
"""speak: read your AI agent's replies aloud (Claude Code, Antigravity, Codex, anything).

Python standard library only. Works on macOS, Linux, Windows and WSL.

Hook usage (the payload format is detected automatically):
  speak.py                  Claude Code / Antigravity Stop hook (JSON on stdin)
  speak.py '<json>'         Codex `notify` (JSON as the last argument)
  speak.py --stop           cut off speech in progress (run when a new prompt starts)
  echo text | speak.py --text   read any text aloud (for agents without hooks)

Settings (or /speak inside your agent):
  speak.py --config status | on | off | full | summary | quick | edge | system
                    | voice <name> | say <text>
  speak.py --doctor         show what was detected on this machine

Length: full = the whole reply (links and code dropped), summary = the opening plus the
first sentence of each later point (default), quick = 1-2 sentences or a few bullets.
Voices: edge = natural Microsoft neural voices via edge-tts (needs internet),
system = the voice built into your OS (offline). edge falls back to system on failure.
"""
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
STATE_DIR = Path(os.environ.get("SPEAK_HOME") or HOME / ".speak")
CONFIG_FILE = STATE_DIR / "config.json"
PID_FILE = STATE_DIR / "speak.pid"
OLD_CONFIG = HOME / ".claude" / "voice.json"  # pre-plugin location, migrated once

# Spoken-length cap per mode, in characters (~15 per second of speech).
MAX_CHARS = {"full": None, "summary": 700, "quick": 300}

DEFAULTS = {
    "engine": "edge",  # "edge" (natural, needs internet) or "system" (offline)
    "muted": False,
    "length": "summary",  # "full", "summary" or "quick"
    "edge_voice": "en-US-AvaNeural",  # list: edge-tts --list-voices
    "edge_rate": "+5%",
    "windows_rate": 1,  # system voice on Windows/WSL: -10 (slow) .. 10 (fast)
}

WINDOWS_SPEAK_PS = (
    "[Console]::InputEncoding=[Text.Encoding]::UTF8;"
    "$t=[Console]::In.ReadToEnd();"
    "Add-Type -AssemblyName System.Speech;"
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$s.Rate={rate};"
    "$s.Speak($t)"
)

PLAY_MP3_PS = (
    "Add-Type -AssemblyName PresentationCore;"
    "$p=New-Object System.Windows.Media.MediaPlayer;"
    '$p.Open([Uri]"{path}");$p.Play();$n=0;'
    "while(-not $p.NaturalDuration.HasTimeSpan -and $n -lt 50){{Start-Sleep -m 100;$n++}};"
    "if($p.NaturalDuration.HasTimeSpan){{$d=$p.NaturalDuration.TimeSpan.TotalSeconds;"
    "while($p.Position.TotalSeconds -lt $d){{Start-Sleep -m 200}}}};"
    "$p.Close()"
)

QUIET = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
if os.name == "nt":
    QUIET["creationflags"] = subprocess.CREATE_NO_WINDOW  # no console windows popping up


# ---------------------------------------------------------------- platform

def detect_platform():
    forced = os.environ.get("SPEAK_PLATFORM")  # for testing: mac, linux, windows, wsl
    if forced:
        return forced
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "mac"
    if "microsoft" in platform.release().lower():
        return "wsl"
    return "linux"


def first_cmd(*names):
    for name in names:
        if shutil.which(name):
            return name
    return None


def powershell():
    if os.name == "nt":
        return first_cmd("powershell.exe", "pwsh.exe")
    p = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    return p if os.path.exists(p) else first_cmd("powershell.exe")


def edge_tts_cmd():
    exe = shutil.which("edge-tts") or next(
        (str(p) for p in (HOME / ".local" / "bin" / "edge-tts",) if p.exists()), None)
    if exe:
        return [exe]
    if importlib.util.find_spec("edge_tts"):
        return [sys.executable, "-m", "edge_tts"]
    return None


def wsl_windows_temp():
    """Windows %TEMP% as (linux_path, windows_path); Windows can't play files from WSL."""
    cmd = shutil.which("cmd.exe") or "/mnt/c/Windows/System32/cmd.exe"
    out = subprocess.run([cmd, "/c", "echo %TEMP%"], capture_output=True,
                         cwd="/mnt/c", timeout=10).stdout.decode(errors="ignore").strip()
    linux = subprocess.run(["wslpath", "-u", out], capture_output=True,
                           timeout=10).stdout.decode().strip()
    return Path(linux), out


def mp3_player(plat):
    if plat == "mac":
        return ["afplay"]
    if plat == "linux":
        for cmd in (["mpv", "--no-video", "--really-quiet"],
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
                    ["mpg123", "-q"]):
            if shutil.which(cmd[0]):
                return cmd
    return None  # Windows/WSL play through PowerShell


def system_voice(plat):
    if plat in ("windows", "wsl"):
        return "Windows speech (SAPI)" if powershell() else None
    if plat == "mac":
        return "say" if shutil.which("say") else None
    return first_cmd("spd-say", "espeak-ng", "espeak")


# ---------------------------------------------------------------- config

def load_config():
    for f in (CONFIG_FILE, OLD_CONFIG):
        try:
            cfg = {**DEFAULTS, **json.loads(f.read_text())}
            break
        except (OSError, ValueError):
            continue
    else:
        cfg = dict(DEFAULTS)
    if cfg["engine"] == "windows":
        cfg["engine"] = "system"
    return cfg


def save_config(cfg):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")


def describe(cfg):
    engine = (f"natural voice (edge-tts, {cfg['edge_voice']})"
              if cfg["engine"] == "edge" else "built-in system voice")
    return (f"Voice is {'OFF' if cfg['muted'] else 'ON'}, reading the {cfg['length']}"
            f" version with the {engine}.")


def configure(args):
    cfg = load_config()
    cmd = args[0].lower() if args else "status"
    if cmd in ("on", "unmute"):
        cfg["muted"] = False
    elif cmd in ("off", "mute"):
        cfg["muted"] = True
        stop_speaking()
    elif cmd in ("edge", "natural"):
        cfg["engine"] = "edge"
    elif cmd in ("system", "windows", "offline"):
        cfg["engine"] = "system"
    elif cmd in MAX_CHARS:
        cfg["length"] = cmd
    elif cmd == "voice" and len(args) > 1:
        cfg["edge_voice"] = args[1]
    elif cmd == "say" and len(args) > 1:
        stop_speaking()
        start_speaking(" ".join(args[1:]))
        print("Speaking.")
        return
    elif cmd == "doctor":
        doctor()
        return
    elif cmd != "status":
        print("Usage: /speak [status | on | off | full | summary | quick | edge | system"
              " | voice <name> | say <text>]")
        return
    if cmd != "status" or not CONFIG_FILE.exists():
        save_config(cfg)
    print(describe(cfg))


def doctor():
    plat = detect_platform()
    cfg = load_config()
    edge = edge_tts_cmd()
    print(f"platform:      {plat}")
    print(f"python:        {sys.executable} ({platform.python_version()})")
    print(f"config:        {CONFIG_FILE}")
    print(f"edge-tts:      {' '.join(edge) if edge else 'not found (pip install edge-tts)'}")
    if plat in ("windows", "wsl"):
        print(f"mp3 player:    PowerShell MediaPlayer ({powershell() or 'NOT FOUND'})")
    else:
        player = mp3_player(plat)
        print(f"mp3 player:    {' '.join(player) if player else 'not found (install mpv)'}")
    print(f"system voice:  {system_voice(plat) or 'not found'}")
    print(describe(cfg))


# ---------------------------------------------------------------- speaking

def say_system(text, cfg, plat):
    if plat in ("windows", "wsl"):
        subprocess.run([powershell(), "-NoProfile", "-NonInteractive", "-Command",
                        WINDOWS_SPEAK_PS.format(rate=int(cfg["windows_rate"]))],
                       input=text.encode("utf-8"), **QUIET)
        return
    voice = system_voice(plat)
    if not voice:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.write(text)
    try:
        if voice == "say":
            subprocess.run(["say", "-f", f.name], **QUIET)
        elif voice == "spd-say":
            subprocess.run(["spd-say", "-w", text], **QUIET)
        else:
            subprocess.run([voice, "-f", f.name], **QUIET)
    finally:
        os.unlink(f.name)


def say_edge(text, cfg, plat):
    """Returns False if the natural voice couldn't be generated or played."""
    edge = edge_tts_cmd()
    if not edge:
        return False
    if plat == "wsl":
        tmp, tmp_win = wsl_windows_temp()
    else:
        tmp = tmp_win = Path(tempfile.gettempdir())
    for old in Path(tmp).glob("speak-*.*"):  # leftovers from cut-off replies
        try:
            old.unlink()
        except OSError:
            pass
    name = f"speak-{os.getpid()}"
    mp3, txt = Path(tmp) / f"{name}.mp3", Path(tmp) / f"{name}.txt"
    txt.write_text(text, encoding="utf-8")
    try:
        result = subprocess.run(
            edge + ["--voice", cfg["edge_voice"], f"--rate={cfg['edge_rate']}",
                    "--file", str(txt), "--write-media", str(mp3)], timeout=60, **QUIET)
        if result.returncode != 0:
            return False
        if plat in ("windows", "wsl"):
            subprocess.run([powershell(), "-NoProfile", "-NonInteractive", "-Command",
                            PLAY_MP3_PS.format(path=f"{tmp_win}\\{name}.mp3")], **QUIET)
            return True
        player = mp3_player(plat)
        if not player:
            return False
        subprocess.run(player + [str(mp3)], **QUIET)
        return True
    finally:
        txt.unlink(missing_ok=True)
        mp3.unlink(missing_ok=True)


def say(text):
    """Runs in a detached process so the hook can return straight away."""
    cfg = load_config()
    plat = detect_platform()
    if cfg["engine"] == "edge":
        try:
            if say_edge(text, cfg, plat):
                return
        except (OSError, subprocess.SubprocessError):
            pass
    say_system(text, cfg, plat)  # chosen engine, or fallback when edge-tts fails


def start_speaking(text):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = {"stdin": subprocess.PIPE, **QUIET}
    if os.name == "nt":  # replaces CREATE_NO_WINDOW: detached processes have no console
        kwargs["creationflags"] = (subprocess.CREATE_NEW_PROCESS_GROUP
                                   | subprocess.DETACHED_PROCESS)
    else:
        # Its own process group, so stop_speaking() also kills edge-tts and the player,
        # and it keeps talking after the hook exits.
        kwargs["start_new_session"] = True
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--say"], **kwargs)
    PID_FILE.write_text(str(proc.pid))
    proc.stdin.write(text.encode("utf-8"))
    proc.stdin.close()


def stop_speaking():
    try:
        pid = int(PID_FILE.read_text())
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], **QUIET)
        else:
            os.killpg(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass
    PID_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------- reading replies

def final_reply(transcript_path):
    """Claude Code transcript: text of the last assistant turn after its last tool call."""
    texts = []
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            msg = entry.get("message") or {}
            content = msg.get("content")
            if entry.get("type") == "user":
                # A real user prompt (not a tool result) starts a new turn.
                if isinstance(content, str) or not any(
                    c.get("type") == "tool_result" for c in content or []
                ):
                    texts = []
            elif entry.get("type") == "assistant" and isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_use":
                        texts = []  # only keep what follows the last tool call
                    elif block.get("type") == "text":
                        texts.append(block["text"])
    return "\n\n".join(texts).strip()


def final_reply_agy(transcript_path):
    """Antigravity transcript: the last model message with text (the final answer)."""
    last = ""
    with open(transcript_path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            content = entry.get("content")
            if (entry.get("type") == "PLANNER_RESPONSE" and isinstance(content, str)
                    and content.strip()):
                last = content
    return last.strip()


def blocks(text):
    """Markdown -> [(kind, text)] with kind para/item/heading. Drops code and tables."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    out, para = [], []

    def flush():
        if para:
            out.append(("para", " ".join(para)))
            para.clear()

    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("|"):
            flush()
        elif re.match(r"#{1,6}\s", s):
            flush()
            out.append(("heading", s))
        elif re.match(r"(?:[-*+]|\d+\.)\s+", s):
            flush()
            out.append(("item", s))
        elif line[:1] in " \t" and out and out[-1][0] == "item" and not para:
            out[-1] = ("item", out[-1][1] + " " + s)  # wrapped bullet text
        else:
            para.append(s)
    flush()
    return out


def sentences(text):
    return [t for t in re.split(r"(?<=[.!?])\s+", text) if t]


def shorten(text, length):
    """Keep only the parts of the reply worth speaking at the chosen length."""
    if length == "full":
        return text
    bs = blocks(text)
    picked = []
    if length == "quick":
        # The first 1-2 sentences; if they introduce a list, a few of its bullets.
        for i, (kind, t) in enumerate(bs):
            if kind != "para":
                continue
            picked += sentences(t)[:2 - len(picked)]
            if t.endswith(":"):
                picked += [sentences(b)[0] for k, b in bs[i + 1:] if k == "item"][:3]
                break
            if len(picked) >= 2:
                break
        if not picked:  # the reply is only bullets
            picked = [sentences(b)[0] for k, b in bs if k == "item"][:3]
    else:
        # The opening paragraph, then the first sentence of each later point.
        lead_done = False
        for kind, t in bs:
            if kind == "heading":
                continue
            if kind == "para" and not lead_done:
                picked += sentences(t)[:3]
                lead_done = True
            else:
                picked.append(sentences(t)[0])
    return "\n".join(picked)


def clean(text, max_chars=None):
    text = re.sub(r"```.*?```", " Code block omitted. ", text, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)  # images
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # links -> link text
    text = re.sub(r"<?https?://\S+>?", "", text)  # bare URLs
    text = re.sub(r"`([^`]*)`", r"\1", text)  # inline code -> its text
    # File paths -> just the file name (e.g. /a/b/speak.py:12 -> speak.py)
    text = re.sub(r"(?:~|\.{0,2})?(?:/[\w.\-]+){2,}(?::\d+)?",
                  lambda m: m.group(0).split(":")[0].rsplit("/", 1)[-1], text)
    text = re.sub(r"^[ \t]*\|?[ \t:|-]+\|[ \t:|-]*$", "", text, flags=re.M)  # table rules
    text = re.sub(r"^[ \t]*\|(.*?)\|?[ \t]*$", lambda m: re.sub(r"\s*\|\s*", ", ", m.group(1).strip()),
                  text, flags=re.M)  # table rows -> "a, b"
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)  # headings
    text = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", text, flags=re.M)  # list markers
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)  # quotes
    text = re.sub(r"(\*\*|__|\*|~~)", "", text)  # bold/italic/strike
    text = re.sub(r"[^\x00-⿿]", "", text)  # emoji and other symbols
    text = text.replace("→", " to ").replace("—", ", ")
    # Make each line end like a sentence so the voice pauses between them.
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    text = " ".join(l if l[-1] in ".!?:;," else l + "." for l in lines)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars and len(text) > max_chars:
        cut = text[:max_chars]
        text = cut[: cut.rfind(". ") + 1 or max_chars] + " The rest is on screen."
    return text


# ---------------------------------------------------------------- hook entry

def read_payload():
    """Hook payload from argv (Codex notify) or stdin (Claude, Antigravity)."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        try:
            return json.loads(args[-1])
        except ValueError:
            pass
    if sys.stdin is None or sys.stdin.isatty():
        return {}
    try:
        data = json.loads(sys.stdin.read() or "{}")
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def reply_text(payload):
    """The finished reply for any supported agent, or "" when there's nothing to say."""
    if payload.get("type") == "agent-turn-complete":  # Codex notify
        return payload.get("last-assistant-message") or ""
    if "transcriptPath" in payload or "terminationReason" in payload:  # Antigravity
        if payload.get("terminationReason") not in (None, "NO_TOOL_CALL"):
            return ""
        path = payload.get("transcriptPath")
        return final_reply_agy(path) if path and os.path.exists(path) else ""
    text = payload.get("last_assistant_message") or ""  # Claude Code (and Codex hooks)
    path = payload.get("transcript_path")
    if not text and path:
        for _ in range(5):  # the transcript can lag a moment behind the hook
            text = final_reply(path)
            if text:
                break
            time.sleep(0.3)
    return text


def main():
    if "--config" in sys.argv:
        configure(sys.argv[sys.argv.index("--config") + 1:])
        return
    if "--doctor" in sys.argv:
        doctor()
        return
    if "--say" in sys.argv:
        say(sys.stdin.buffer.read().decode("utf-8"))
        return
    stop_speaking()
    if "--text" in sys.argv:
        payload, text = {}, sys.stdin.read()
    else:
        payload = read_payload()
        text = "" if "--stop" in sys.argv else reply_text(payload)
    if os.environ.get("SPEAK_DEBUG"):  # troubleshooting: what the agent sent us
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "debug.json").write_text(json.dumps(
            {"argv": sys.argv, "payload": payload, "text": text}, indent=2))
    if "conversationId" in payload or "transcriptPath" in payload:
        print("{}")  # Antigravity hooks must answer with JSON
    cfg = load_config()
    if cfg["muted"] or not isinstance(text, str):
        return
    length = cfg["length"] if cfg["length"] in MAX_CHARS else "summary"
    text = clean(shorten(text, length), MAX_CHARS[length])
    if text:
        start_speaking(text)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if "--config" in sys.argv or "--doctor" in sys.argv:
            raise
        # otherwise never let speech problems interrupt the agent
