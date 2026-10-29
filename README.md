# AI agent speak

Your AI agent reads its replies out loud when it finishes. You choose how much it reads:

| Mode | What you hear |
|---|---|
| `full` | The whole reply. Links and code are skipped. |
| `summary` (default) | The opening, then the first sentence of each later point. |
| `quick` | One or two sentences, or the first few bullet points. |

It uses a natural Microsoft voice ([edge-tts](https://github.com/rany2/edge-tts), free, needs internet) or the voice built into your computer (works offline). Speech stops as soon as you send your next message.

**Works with:** Claude Code, Antigravity, Codex CLI, Grok CLI, and any other tool that can pipe text. It runs on macOS, Windows, Linux and WSL, and needs only Python 3.

## Install

You need [Python 3](https://www.python.org/downloads/). Download this repo ([zip](https://github.com/danju4rizzl/AI-agent-speak/archive/refs/heads/main.zip)) or clone it:

```bash
git clone https://github.com/danju4rizzl/AI-agent-speak.git
cd AI-agent-speak
```

Then run:

**macOS / Linux / WSL**
```bash
./install.sh
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer finds the agents on your machine and sets each one up:

| Agent | How it's connected |
|---|---|
| Claude Code | Plugin: `claude plugin marketplace add <this folder>` + `claude plugin install speak@speak` |
| Antigravity | Plugin: `agy plugin install <this folder>` |
| Codex CLI | `notify = [...]` line in `~/.codex/config.toml`, plus the `/speak` skill in `~/.codex/skills` |
| Grok CLI | Hook file `~/.grok/hooks/speak.json` |

If Codex already has a `notify` command, the installer leaves it alone and shows you the line to use instead.

Add `--dry-run` (or `-DryRun` on Windows) to see what it would change without changing anything. Restart your agent afterwards.

### Claude Code only (no download needed)
```
/plugin marketplace add danju4rizzl/AI-agent-speak
/plugin install speak@speak
```
Restart Claude Code afterwards. This route doesn't install the natural voice, so until you add it you'll hear your computer's built-in voice. To get the natural voice, run `pip install edge-tts` (or `uv tool install edge-tts`).

## Use

Type these in your agent:

```
/speak status        what's on right now
/speak on | off      read aloud, or stay quiet
/speak full | summary | quick
/speak edge          natural voice (default)
/speak system        the computer's built-in voice, offline
/speak voice en-GB-SoniaNeural    pick a natural voice (list: edge-tts --list-voices)
/speak say Hello     read some text right now
/speak doctor        check what was found on this computer
```

Settings live in `~/.speak/config.json` and are shared by all your agents.

### Other agents (no hooks)
Pipe any text in (`~/.speak/speak.py` is put there by the installer):
```bash
echo "Build finished." | python3 ~/.speak/speak.py --text
```
For an agent that reads `AGENTS.md`, you can add: *"When you finish a reply, run `python3 ~/.speak/speak.py --text` with a short spoken summary as input."*

## What each computer needs

| | Natural voice | Offline voice |
|---|---|---|
| macOS | edge-tts (the installer adds it) | built in (`say`) |
| Windows / WSL | edge-tts | built in (Windows speech) |
| Linux | edge-tts + an MP3 player: `sudo apt install mpv` | `sudo apt install espeak-ng` |

If the natural voice can't run (no internet, edge-tts missing), it falls back to the offline voice.

## Troubleshooting

- **Silent?** Run `/speak doctor`. It lists what's missing. If you used the installer, `python3 ~/.speak/speak.py --doctor` does the same outside your agent.
- **Still silent right after installing?** Restart the agent. Hooks only load when a session starts.
- **See what the agent sent:** start the agent with `SPEAK_DEBUG=1`, then look at `~/.speak/debug.json`.
- **Updating:** pull or download the new version and run the installer again. Antigravity keeps its own copy, so it needs the reinstall. If you used the Claude-only install, run `/plugin marketplace update speak` instead.

Tested on Windows/WSL with Claude Code and Antigravity. The macOS, Linux, native Windows, Codex and Grok paths follow those tools' documented behaviour but haven't been tested on real machines yet. Reports are welcome.

## License
MIT
