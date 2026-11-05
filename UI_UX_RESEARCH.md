# UI/UX Research

**Date:** 2026-11-04

## Evidence

- Android Developers' Compose documentation confirms the active multi-group Compose release model and Material 3 support: https://developer.android.com/jetpack/androidx/releases/compose
- Google's `android/nowinandroid` repository was inspected through GitHub metadata as a modern modular Android reference (Apache-2.0): https://github.com/android/nowinandroid
- Open WebUI, Dify, Continue and other interfaces were included in ecosystem discovery, but their visual designs were not copied and their licenses do not transfer to independent design work.

## Selected direction

A mobile-first **AI operations workspace**, not a neon dashboard or chat-only wrapper:

- Graphite surfaces, one cyan/blue action accent, restrained borders and elevation.
- Material 3 on Android; accessible responsive web operations console for development/preview.
- Six primary destinations: Home, Chat, Voice, Agents, Workspace, More.
- Research, Skills, Memory, Models, Terminal, Builds, Workflows, Security and Settings under More.
- Persistent task state shown as queued/running/waiting approval/succeeded/failed/cancelled/partial—never decorative “live” indicators.
- Every research result exposes source URL, connector, retrieval time and verification status.
- Agent cards derive from registry/task APIs. Empty states remain empty rather than displaying mock metrics.
- Chat and Voice have separate routes and state/pipelines.

## Interaction and accessibility

- Minimum 44–48 dp touch targets, visible keyboard focus, semantic labels and sufficient contrast.
- Reduced-motion setting; no information conveyed only by color/glow.
- Streaming text remains selectable; stop/retry actions use actual operation state.
- Long tasks provide concise evidence/activity timelines, not private chain-of-thought.
- Errors preserve partial results and identify failed/inaccessible connectors.
- Bengali and English use appropriate system font fallbacks, dynamic sizing and bidirectional-safe layout.

## Validation required

Compose previews are not device verification. Screen reader, keyboard, font-scale, narrow-screen, Bengali rendering, reduced-motion, low-memory and real-device performance tests remain release gates.

**Status:** `DESIGN DIRECTION FROZEN; DEVICE UX VALIDATION BLOCKED UNTIL ANDROID TOOLCHAIN/DEVICE EXISTS.`
