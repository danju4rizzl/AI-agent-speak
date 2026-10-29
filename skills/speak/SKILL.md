---
name: speak
description: Read replies aloud - on, off, full, summary, quick, edge (natural voice), system (offline voice), voice <name>, say <text>, status, or doctor. Use when the user types /speak:speak (or /speak) or asks to turn read-aloud on/off, change how much is read, or change the voice.
argument-hint: "[status|on|off|full|summary|quick|edge|system|voice <name>|say <text>|doctor]"
allowed-tools: Bash(python3 *speak.py*), Bash(python *speak.py*)
---
!`python3 "${CLAUDE_SKILL_DIR}/scripts/speak.py" --config $ARGUMENTS 2>/dev/null || python "${CLAUDE_SKILL_DIR}/scripts/speak.py" --config $ARGUMENTS`

If the line above shows a result, repeat it to the user in one short sentence and do nothing else (for `doctor`, show the output as-is).

Otherwise (your agent didn't run it for you), run this from the folder that contains this SKILL.md, passing the user's words after the command as the arguments, then repeat its output in one short sentence:

```
python3 scripts/speak.py --config <arguments>
```

(On Windows use `python` instead of `python3`.)

What the options do:
- `on` / `off`: read replies aloud, or stay silent.
- `full`: the whole reply (links and code are skipped).
- `summary` (default): the opening plus the first sentence of each later point.
- `quick`: one or two sentences, or the first few bullets.
- `edge`: natural Microsoft neural voice (needs internet and `edge-tts`).
- `system`: the voice built into the computer (works offline).
- `voice <name>`: choose a natural voice, e.g. `en-GB-SoniaNeural` (list: `edge-tts --list-voices`).
- `say <text>`: read some text aloud now.
