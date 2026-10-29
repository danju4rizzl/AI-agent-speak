# AI agent speak

Your AI agent reads its replies out loud when it finishes. You choose how much it reads:

| Mode | What you hear |
|---|---|
| `full` | The whole reply. Links and code are skipped. |
| `summary` (default) | The opening, then the first sentence of each later point. |
| `quick` | One or two sentences, or the first few bullet points. |

It uses a natural Microsoft voice ([edge-tts](https://github.com/rany2/edge-tts), free, needs internet; `en-GB-RyanNeural` by default) or the voice built into your computer (works offline). Speech stops as soon as you send your next message.

Turn on `jarvis` and the agent also replies in the style of JARVIS, a calm British assistant, at the length you chose above.

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

The installer copies the engine to `~/.speak/speak.py`, installs edge-tts, then finds the agents on your machine and sets each one up:

| Agent | How it's connected |
|---|---|
| Claude Code | Plugin: `claude plugin marketplace add <this folder>` + `claude plugin install speak@speak` |
| Antigravity | Plugin: `agy plugin install <this folder>` |
| Codex CLI | `notify = [...]` line in `~/.codex/config.toml`, a `UserPromptSubmit` hook in `~/.codex/hooks.json`, and the `speak` skill in `~/.codex/skills` |
| Grok CLI | Hook file `~/.grok/hooks/speak.json` |

If Codex already has a `notify` command, the installer leaves it alone and shows you the line to use instead. Hooks already in `~/.codex/hooks.json` are kept. Codex asks you to approve the new hook once: run `/hooks` in Codex.

Add `--dry-run` (or `-DryRun` on Windows) to see what it would change without changing anything. Restart your agent afterwards.

### Claude Code only (no download needed)
```
/plugin marketplace add danju4rizzl/AI-agent-speak
/plugin install speak@speak
```
Then run `/reload-plugins` or restart Claude Code. This route doesn't install the natural voice, so until you add it you'll hear your computer's built-in voice. To get the natural voice, run `pip install edge-tts` (or `uv tool install edge-tts`). It also doesn't create `~/.speak/speak.py`, which the [other agents](#other-agents) section uses.

## Use

Type these in your agent. In Claude Code the command is `/speak:speak`; some other agents show the same skill as `/speak`.

```
/speak:speak status                  what's on right now
/speak:speak on | off                read aloud, or stay quiet
/speak:speak full | summary | quick  how much is read (and how long JARVIS replies are)
/speak:speak edge                    natural voice (default)
/speak:speak system                  the computer's built-in voice, offline
/speak:speak voice en-GB-SoniaNeural pick a natural voice (list: edge-tts --list-voices)
/speak:speak jarvis | jarvis off     reply in the style of JARVIS, or stop
/speak:speak say Hello               read some text right now
/speak:speak doctor                  check what was found on this computer
```

Settings live in `~/.speak/config.json` and are shared by all your agents.

### JARVIS
With `jarvis` on, every prompt carries a reply style: calm, polished formality with dry wit, calling you "sir", never rambling. Reply length follows `full`, `summary` or `quick`. It works separately from `on`/`off`, so a muted agent still replies as JARVIS.

Claude Code, Codex and Antigravity get the style through their prompt hooks. Grok's prompt hook can't add to the conversation, so for Grok see [Other agents](#other-agents).

### Other agents
For an agent without hooks, pipe text in to have it read aloud (`~/.speak/speak.py` is put there by the installer):
```bash
echo "Build finished." | python3 ~/.speak/speak.py --text
```
`python3 ~/.speak/speak.py --persona` prints the current JARVIS style, or nothing when it's off. For an agent that reads `AGENTS.md` (or a similar instructions file), you can add:

- *"When you finish a reply, run `python3 ~/.speak/speak.py --text` with a short spoken summary as input."*
- *"Before each reply, run `python3 ~/.speak/speak.py --persona` and follow the style it prints, if any."*

## What each computer needs

| | Natural voice | Offline voice |
|---|---|---|
| macOS | edge-tts (the installer adds it) | built in (`say`) |
| Windows / WSL | edge-tts | built in (Windows speech) |
| Linux | edge-tts + an MP3 player: `sudo apt install mpv` | `sudo apt install espeak-ng` |

If the natural voice can't run (no internet, edge-tts missing), it falls back to the offline voice.

## Troubleshooting

- **Silent?** Run `/speak:speak doctor`. It lists what's missing. If you used the installer, `python3 ~/.speak/speak.py --doctor` does the same outside your agent.
- **Still silent right after installing?** Hooks load when a session starts: restart the agent (in Claude Code, `/reload-plugins` is enough). In Codex, check the hook is approved in `/hooks`.
- **See what the agent sent:** start the agent with `SPEAK_DEBUG=1`, then look at `~/.speak/debug.json`.
- **Updating:** pull or download the new version and run the installer again. Antigravity keeps its own copy, so it needs the reinstall. If you used the Claude-only install, run `/plugin marketplace update speak` instead.

Tested on Windows/WSL with Claude Code and Antigravity. The macOS, Linux, native Windows, Codex and Grok paths follow those tools' documented behaviour but haven't been tested on real machines yet. JARVIS has been checked against each agent's documented hook format, not yet in live sessions. Reports are welcome.

## License
MIT
