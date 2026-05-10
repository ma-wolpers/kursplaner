# GUI Migration Backlog

## Active Exemptions
- kursplaner/adapters/gui/main_window.py
  remove_by: 2026-12-31
  reason: Existing GUI root entrypoint is baseline-scoped while strict shared-contract checks are active.
- kursplaner/adapters/gui/screen_builder.py
  remove_by: 2026-12-31
  reason: Existing primary screen composition entrypoint is baseline-scoped while strict shared-contract checks are active.
- kursplaner/adapters/gui/main_window.py:KursplanerApp
  remove_by: 2026-09-30
  reason: Local ui.Tk baseclass pending migration to bw-gui host/factory.
- kursplaner/adapters/gui/popup_window.py:ScrollablePopupWindow
  remove_by: 2026-09-30
  reason: Local ui.Toplevel popup base pending migration to shared bw-gui popup host.
- kursplaner/adapters/gui/wrapped_text_field.py:WrappedTextField
  remove_by: 2026-09-30
  reason: Local widgets.Frame text wrapper pending migration to shared bw-gui component.

## Notes
- This backlog tracks all currently allowed baseline/exemption entries referenced by guardrails.
- Exemptions are temporary and must be removed after each migration wave.
