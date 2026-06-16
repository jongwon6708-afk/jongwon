# Shortcuts action reference

Common `is.workflow.actions.*` identifiers and their key parameters, for use in
the JSON spec. Parameter values may contain `{{magic variables}}` (see SKILL.md).
This is a curated subset — the Shortcuts app has hundreds of actions; reach for
the closest one here, and verify against a real exported shortcut if unsure.

## Text & output

| Action | `id` | Key params |
|--------|------|-----------|
| Text | `is.workflow.actions.gettext` | `WFTextActionText` (string) |
| Comment | `is.workflow.actions.comment` | `WFCommentActionText` (string) — ignored at runtime |
| Show Result | `is.workflow.actions.showresult` | `Text` (string) |
| Show Notification | `is.workflow.actions.notification` | `WFNotificationActionBody`, `WFNotificationActionTitle`, `WFNotificationActionSound` (bool) |
| Show Alert | `is.workflow.actions.alert` | `WFAlertActionTitle`, `WFAlertActionMessage`, `WFAlertActionCancelButtonShown` (bool) |
| Speak Text | `is.workflow.actions.speaktext` | `WFText`, `WFSpeakTextRate` (num), `WFSpeakTextPitch` (num), `WFSpeakTextLanguage` |
| Quick Look | `is.workflow.actions.previewdocument` | (uses input) |

## Input from the user

| Action | `id` | Key params |
|--------|------|-----------|
| Ask for Input | `is.workflow.actions.ask` | `WFAskActionPrompt`, `WFInputType` (`Text`/`Number`/`URL`/`Date`/`Time`/`Date and Time`), `WFAskActionDefaultAnswer` |
| Choose from Menu | `is.workflow.actions.choosefrommenu` | `WFMenuPrompt`, `WFMenuItems` (array of strings). NOTE: menu bodies require paired `…menu.middle`/`…menu.end` actions — prefer If for simple branching. |
| Choose from List | `is.workflow.actions.choosefromlist` | `WFChooseFromListActionPrompt`, `WFInput` |

## Variables

| Action | `id` | Key params |
|--------|------|-----------|
| Set Variable | `is.workflow.actions.setvariable` | `WFVariableName` (string), `WFInput` (usually `{{something}}`) |
| Add to Variable | `is.workflow.actions.appendvariable` | `WFVariableName`, `WFInput` |
| Get Variable | `is.workflow.actions.getvariable` | `WFVariable` |

After a Set Variable named `foo`, reference it elsewhere with `{{foo}}`.

## Control flow

| Action | `id` | Key params |
|--------|------|-----------|
| If | `is.workflow.actions.conditional` | `WFCondition` (`Is`/`Is Not`/`Contains`/`Greater Than`…), `WFConditionalActionString`, `GroupingIdentifier`, `WFControlFlowMode` (0=if, 1=else, 2=end) |
| Repeat | `is.workflow.actions.repeat.count` | `WFRepeatCount` (num), `GroupingIdentifier`, `WFControlFlowMode` (0=start, 2=end) |
| Repeat with Each | `is.workflow.actions.repeat.each` | `GroupingIdentifier`, `WFControlFlowMode` |
| Wait | `is.workflow.actions.delay` | `WFDelayTime` (num, seconds) |
| Nothing / Stop | `is.workflow.actions.exit` | — |

**Control-flow blocks come in matched groups.** Emit one action per boundary,
all sharing the same `GroupingIdentifier` (any unique string), e.g. an If is
three actions: mode 0 (if), mode 1 (else, optional), mode 2 (end).

## Web & URLs

| Action | `id` | Key params |
|--------|------|-----------|
| URL | `is.workflow.actions.url` | `WFURLActionURL` (string) |
| Get Contents of URL | `is.workflow.actions.downloadurl` | `WFURL`, `WFHTTPMethod` (`GET`/`POST`…), `WFHTTPHeaders`, `WFRequestVariable` |
| Open URLs | `is.workflow.actions.openurl` | (uses input) |
| Open App | `is.workflow.actions.openapp` | `WFAppIdentifier` or `WFSelectedApp` |
| Get Dictionary from Input | `is.workflow.actions.detect.dictionary` | (uses input) |
| Get Value for Key | `is.workflow.actions.getvalueforkey` | `WFDictionaryKey` |

## Communication

| Action | `id` | Key params |
|--------|------|-----------|
| Send Message | `is.workflow.actions.sendmessage` | `WFSendMessageContent`, `WFSendMessageActionRecipients` |
| Send Email | `is.workflow.actions.sendemail` | `WFEmailSubject`, `WFEmailBody`, `WFSendEmailActionToRecipients` |
| Make Phone Call | `is.workflow.actions.makephonecall` | `WFPhoneNumber` |

## Clipboard, device & media

| Action | `id` | Key params |
|--------|------|-----------|
| Copy to Clipboard | `is.workflow.actions.setclipboard` | `WFInput` |
| Get Clipboard | `is.workflow.actions.getclipboard` | — |
| Set Brightness | `is.workflow.actions.setbrightness` | `WFBrightness` (0.0–1.0) |
| Set Low Power Mode | `is.workflow.actions.lowpowermode.set` | `OnValue` (bool) |
| Get Current Weather | `is.workflow.actions.weather.currentconditions` | `WFWeatherCustomLocation` |
| Get Battery Level | `is.workflow.actions.getbatterylevel` | — |
| Play/Pause | `is.workflow.actions.pausemusic` | `WFPlayPauseBehavior` (`Play`/`Pause`/`Play/Pause`) |

## Dates & numbers

| Action | `id` | Key params |
|--------|------|-----------|
| Date | `is.workflow.actions.date` | `WFDateActionMode` (`Current Date`/`Specified Date`) |
| Format Date | `is.workflow.actions.format.date` | `WFDateFormatStyle`, `WFDateFormat` |
| Number | `is.workflow.actions.number` | `WFNumberActionNumber` |
| Calculate | `is.workflow.actions.math` | `WFMathOperation`, `WFMathOperand`, `WFInput` |

## Calendar & reminders

| Action | `id` | Key params |
|--------|------|-----------|
| Add New Event | `is.workflow.actions.addnewcalendarevent` | `WFCalendarItemTitle`, `WFCalendarItemStartDate`, `WFCalendarItemEndDate`, `WFCalendarItemCalendar` |
| Find Calendar Events | `is.workflow.actions.filter.calendarevents` | `WFContentItemFilter` |
| Add New Reminder | `is.workflow.actions.addnewreminder` | `WFCalendarItemTitle`, `WFAlarmActionDueDate` |

---

## Top-level spec keys

- `name` — shortcut name (`WFWorkflowName`).
- `glyph` — `WFWorkflowIconGlyphNumber`, an integer glyph code. `61440` is a
  generic icon; any valid SF/Shortcuts glyph number works.
- `color` — `WFWorkflowIconStartColor`, an ARGB integer. Examples:
  red `4282601983`, orange `4251333119`, blue `463140863`, green `1440408063`.
- `types` — `WFWorkflowTypes` (default `["NCWidget", "WatchKit"]`). Controls
  where the shortcut is offered (widget, watch, share sheet, etc).
- `import_questions` — prompts shown when the shortcut is imported. Each entry:
  ```json
  {
    "ActionIndex": 0,
    "ParameterKey": "WFPhoneNumber",
    "Category": "Parameter",
    "Text": "Which number should I call?",
    "DefaultValue": ""
  }
  ```
  `ActionIndex` is the 0-based index into `actions`; `ParameterKey` is the param
  in that action to fill with the user's answer.
