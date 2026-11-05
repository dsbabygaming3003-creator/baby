# UI Design System

## Visual language

Premium AI operations workspace: Graphite `#0B0E13`, panels `#11161E`, raised `#161D27`, borders `#263140`, primary text `#EDF3F8`, muted `#91A0B2`, cyan `#82D9F4`. Success/warning/error colors are paired with text/status labels, never color alone. Controlled borders replace decorative glow.

## Structure

Desktop sidebar and mobile bottom navigation: Home, Chat, Voice, Agents, Research, Workspace, More. Skills, Models, Workflows and Security are real secondary routes. Panels use 13–16 px radii, consistent 14–22 px gaps and clear eyebrow/title hierarchy.

## State and motion

All metrics and registry cards come from APIs. Empty states stay empty; errors appear as toast/inline status. Status values include succeeded/partial/failed/blocked/mock. Streaming text remains selectable and stoppable. `prefers-reduced-motion` disables animation/transitions.

## Accessibility/responsiveness

Keyboard focus rings, semantic forms/labels, touch-friendly controls, responsive one-column mobile layouts and Bengali-capable system font fallbacks. Waveform is actual microphone amplitude. Browser/device screen-reader, contrast, font-scale and Bengali tests still require real device/browser QA.

The web console is an additional operations client, not an APK or proof of Android visual verification.
