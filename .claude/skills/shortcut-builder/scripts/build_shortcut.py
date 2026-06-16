#!/usr/bin/env python3
"""Build an (unsigned) iOS Shortcuts file from a simple JSON action spec.

The Shortcuts file format is a property list (plist) whose root is a
``WFWorkflow`` dictionary. The fiddly parts — assigning per-action UUIDs,
wiring "magic variables" (action outputs) into text via
``WFTextTokenString`` / ``attachmentsByRange``, and serializing the plist —
are all handled here so the caller only has to describe actions.

Spec format (JSON)::

    {
      "name": "Morning Briefing",
      "glyph": 61440,                      // optional, see reference/actions.md
      "color": 4282601983,                 // optional ARGB int
      "import_questions": [...],           // optional, asked on import
      "actions": [
        {
          "id": "is.workflow.actions.gettext",
          "params": {"WFTextActionText": "Hello world"},
          "output": "greeting"             // optional name other actions can reference
        },
        {
          "id": "is.workflow.actions.showresult",
          "params": {"Text": "You said: {{greeting}}"}
        }
      ]
    }

Template tokens ``{{name}}`` inside any string parameter are replaced with a
magic-variable reference:

* ``{{name}}`` where ``name`` is an earlier action's ``output`` -> that action's output
* ``{{name}}`` where ``name`` is a variable created by Set Variable -> that variable
* built-in sources: ``{{ShortcutInput}}`` / ``{{Input}}``, ``{{Clipboard}}``,
  ``{{CurrentDate}}`` / ``{{Date}}``, ``{{Ask}}``, ``{{DeviceDetails}}``

Usage::

    python3 build_shortcut.py spec.json -o "Morning Briefing.shortcut"
    cat spec.json | python3 build_shortcut.py - -o out.shortcut
    python3 build_shortcut.py spec.json --xml   # human-readable, for inspection
"""

from __future__ import annotations

import argparse
import json
import plistlib
import re
import sys
import uuid

# {{ token }}  -> magic variable reference
TOKEN_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

# Object Replacement Character: marks where an attachment sits in a token string.
OBJ_REPLACEMENT = "￼"

# Built-in variable sources, keyed by lowercased token name.
BUILTIN_VARS = {
    "shortcutinput": {"Type": "ExtensionInput"},
    "input": {"Type": "ExtensionInput"},
    "clipboard": {"Type": "Clipboard"},
    "currentdate": {"Type": "CurrentDate"},
    "date": {"Type": "CurrentDate"},
    "now": {"Type": "CurrentDate"},
    "ask": {"Type": "Ask"},
    "askeachtime": {"Type": "Ask"},
    "devicedetails": {"Type": "DeviceDetails"},
    "device": {"Type": "DeviceDetails"},
}

# Standard set of content classes a shortcut declares it can accept as input.
DEFAULT_INPUT_CLASSES = [
    "WFAppStoreAppContentItem",
    "WFArticleContentItem",
    "WFContactContentItem",
    "WFDateContentItem",
    "WFEmailAddressContentItem",
    "WFGenericFileContentItem",
    "WFImageContentItem",
    "WFiTunesProductContentItem",
    "WFLocationContentItem",
    "WFDCMapsLinkContentItem",
    "WFAVAssetContentItem",
    "WFPDFContentItem",
    "WFPhoneNumberContentItem",
    "WFRichTextContentItem",
    "WFSafariWebPageContentItem",
    "WFStringContentItem",
    "WFURLContentItem",
]


def resolve_attachment(name: str, outputs: dict[str, str]) -> dict:
    """Map a token name to a WFTextTokenAttachment dictionary."""
    key = name.lower()
    if key in BUILTIN_VARS:
        return dict(BUILTIN_VARS[key])
    if name in outputs:
        return {
            "Type": "ActionOutput",
            "OutputUUID": outputs[name],
            "OutputName": name,
        }
    # Fall back to a named variable (e.g. one made by Set Variable).
    return {"Type": "Variable", "VariableName": name}


def make_token_string(text: str, outputs: dict[str, str]):
    """Convert a string with {{tokens}} into a WFTextTokenString dict.

    Returns the original string unchanged when it contains no tokens.
    """
    result = []
    attachments: dict[str, dict] = {}
    cursor = 0  # length of the rebuilt string so far (UTF-16-ish offset)
    last = 0
    for m in TOKEN_RE.finditer(text):
        chunk = text[last:m.start()]
        result.append(chunk)
        cursor += len(chunk)
        attachments["{%d, 1}" % cursor] = resolve_attachment(m.group(1).strip(), outputs)
        result.append(OBJ_REPLACEMENT)
        cursor += 1
        last = m.end()
    if not attachments:
        return text
    result.append(text[last:])
    return {
        "WFSerializationType": "WFTextTokenString",
        "Value": {
            "string": "".join(result),
            "attachmentsByRange": attachments,
        },
    }


def process_value(value, outputs: dict[str, str]):
    """Recursively expand {{tokens}} in any string found in a parameter value."""
    if isinstance(value, str):
        return make_token_string(value, outputs)
    if isinstance(value, list):
        return [process_value(v, outputs) for v in value]
    if isinstance(value, dict):
        return {k: process_value(v, outputs) for k, v in value.items()}
    return value


def build_workflow(spec: dict) -> dict:
    actions = spec.get("actions")
    if not actions:
        raise ValueError("spec must contain a non-empty 'actions' array")

    # Pass 1: give every named output an action UUID.
    outputs: dict[str, str] = {}
    prepared = []
    for i, action in enumerate(actions):
        ident = action.get("id") or action.get("identifier")
        if not ident:
            raise ValueError(f"action #{i} is missing 'id'")
        params = dict(action.get("params", {}))
        out = action.get("output")
        if out:
            params.setdefault("UUID", str(uuid.uuid4()).upper())
            outputs[out] = params["UUID"]
        prepared.append((ident, params, out))

    # Pass 2: resolve tokens now that all output UUIDs are known.
    built = []
    for ident, params, out in prepared:
        resolved = {k: process_value(v, outputs) for k, v in params.items()}
        if out:
            resolved.setdefault("CustomOutputName", out)
        built.append(
            {
                "WFWorkflowActionIdentifier": ident,
                "WFWorkflowActionParameters": resolved,
            }
        )

    workflow = {
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowClientVersion": "2607.0.2",
        "WFWorkflowClientRelease": "2.2.2",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": spec.get("color", 4282601983),
            "WFWorkflowIconGlyphNumber": spec.get("glyph", 61440),
        },
        "WFWorkflowImportQuestions": spec.get("import_questions", []),
        "WFWorkflowTypes": spec.get("types", ["NCWidget", "WatchKit"]),
        "WFWorkflowInputContentItemClasses": spec.get(
            "input_classes", DEFAULT_INPUT_CLASSES
        ),
        "WFWorkflowActions": built,
    }
    if spec.get("name"):
        workflow["WFWorkflowName"] = spec["name"]
    return workflow


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("spec", help="path to JSON spec, or '-' for stdin")
    parser.add_argument(
        "-o",
        "--output",
        help="output path (default: '<name>.shortcut' or 'shortcut.shortcut')",
    )
    parser.add_argument(
        "--xml",
        action="store_true",
        help="write an XML plist instead of binary (easier to inspect)",
    )
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.spec == "-" else open(args.spec, encoding="utf-8").read()
    spec = json.loads(raw)
    workflow = build_workflow(spec)

    out_path = args.output
    if not out_path:
        base = spec.get("name", "shortcut").strip() or "shortcut"
        out_path = f"{base}.shortcut"

    fmt = plistlib.FMT_XML if args.xml else plistlib.FMT_BINARY
    with open(out_path, "wb") as f:
        plistlib.dump(workflow, f, fmt=fmt)

    n = len(workflow["WFWorkflowActions"])
    print(f"Wrote {out_path} ({n} action{'s' if n != 1 else ''}, {'XML' if args.xml else 'binary'} plist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
