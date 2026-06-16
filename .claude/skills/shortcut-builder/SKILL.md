---
name: shortcut-builder
description: Build iOS/iPadOS Shortcuts from a natural-language description. Use when the user wants to create, generate, or design an Apple Shortcuts automation ("아이폰 단축어", "iPhone shortcut", "Shortcuts app") and have an importable .shortcut file produced. Translates plain-language requests into the Shortcuts plist file format.
---

# Shortcut Builder

Turn a natural-language request ("아침마다 날씨랑 일정 알려주는 단축어 만들어줘") into an
**importable iOS Shortcuts file**. You design the action flow; a helper script
handles the fiddly plist format (UUIDs, magic-variable wiring, serialization).

## How it works

1. **Understand the request.** Figure out the trigger context, the inputs, the
   steps, and the output. Ask the user only if something is genuinely ambiguous
   (e.g. which contact to message). Prefer sensible defaults otherwise.
2. **Design the action flow** as an ordered list of Shortcuts actions. See
   `reference/actions.md` for identifiers and parameter keys.
3. **Write a JSON spec** (format below) to a temp file.
4. **Run the builder:**
   ```bash
   python3 .claude/skills/shortcut-builder/scripts/build_shortcut.py spec.json -o "<Name>.shortcut"
   ```
5. **Deliver the file** to the user with `SendUserFile`, plus the short import
   instructions from "Delivering to the user" below.

To sanity-check the structure while developing, add `--xml` to get a
human-readable plist you can open/inspect.

## JSON spec format

```json
{
  "name": "Morning Briefing",
  "glyph": 61440,
  "color": 4282601983,
  "actions": [
    {
      "id": "is.workflow.actions.gettext",
      "params": { "WFTextActionText": "Hello world" },
      "output": "greeting"
    },
    {
      "id": "is.workflow.actions.showresult",
      "params": { "Text": "You said: {{greeting}}" }
    }
  ]
}
```

- `id` — the action identifier (`is.workflow.actions.*`). Required.
- `params` — the action's `WFWorkflowActionParameters`. Keys are action-specific.
- `output` — optional name. Marks this action's result as a **magic variable**
  that later actions reference with `{{output}}`. The script assigns the UUID
  and wires it up; you never write UUIDs by hand.

### Magic variables (the important part)

Inside **any string parameter**, `{{name}}` inserts a reference:

| Token | Refers to |
|-------|-----------|
| `{{greeting}}` | the output of an earlier action whose `output` is `"greeting"` |
| `{{myVar}}` | a variable created by a Set Variable action named `myVar` |
| `{{ShortcutInput}}` / `{{Input}}` | the shortcut's input |
| `{{Clipboard}}` | the clipboard |
| `{{CurrentDate}}` / `{{Date}}` | the current date/time |
| `{{Ask}}` | "Ask Each Time" |
| `{{DeviceDetails}}` | device details |

Plain strings with no `{{...}}` are left as ordinary text, so static parameters
just work.

## Delivering to the user

Unsigned shortcuts are not code-signed by Apple, so the user must allow them
once. Give them these steps along with the file:

1. On the iPhone/iPad, open **Settings → Shortcuts** and turn on
   **Allow Untrusted Shortcuts** (this toggle only appears after the Shortcuts
   app has been opened and at least one shortcut has been run once).
2. Transfer the `.shortcut` file to the device (AirDrop, iCloud Drive, or save
   to Files).
3. Tap the file → an import preview opens in Shortcuts → **Add Shortcut**.

If the toggle is greyed out: open Shortcuts, run any built-in shortcut once,
then return to Settings.

## Guidelines

- Keep flows minimal — only the actions needed to fulfill the request.
- Use `import_questions` (see `reference/actions.md`) when a value is clearly
  personal (a phone number, a city) so the user is prompted on import instead of
  you hard-coding a guess.
- Verify the action identifiers and parameter keys against `reference/actions.md`.
  If an action you need isn't listed, say so and either find the identifier or
  pick the closest supported approach rather than inventing a key.
- After building, briefly describe in plain language what the shortcut does so
  the user can confirm it matches their intent.
- Examples of complete specs live in `examples/`.
