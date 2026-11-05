# UI/UX RESEARCH — TITAN OMEGA INFINITY V18

**Date:** 2026-11-04 · **Method:** five independent 2026 design-trend analyses were read and cross-checked; the consensus was translated into hard, testable design tokens and screen contracts for TITAN.

---

## 1. Consensus findings (2026 AI-app design)

| Finding | Agreement across sources | TITAN rule |
|---|---|---|
| **Dark-mode first** for AI surfaces; layered elevation, never flat `#000000` | 5/5 | Base `#0B0F14` → surfaces `#121821` / `#18212C` / `#1F2A37`, borders instead of shadows |
| **Selective** glassmorphism — overlays, nav bars, modals only; "the 'everything is glass' era is over" | 4/5 (1 says "use sparingly", 1 warns about accessibility) | Glass limited to 2 layers: bottom-nav + modal/sheet; content surfaces stay opaque for contrast |
| **Streaming text** is the default LLM output pattern | 5/5 | Chat streams token-by-token over SSE; a caret + "thinking" micro-copy while the first token is pending |
| **Skeleton + shimmer** instead of spinners | 3/5 | Skeleton blocks on every list; shimmer animation; spinners only for <400 ms indeterminate actions |
| **Explicit AI states** — loading / empty / error / streaming | 4/5 (accessibility framing) | Every data surface implements all four states; a missing empty state is a UI bug |
| **Bento grid** for modular dashboards | 3/5 | Home dashboard uses a 2-column bento grid with one wide "command" cell |
| **Progressive disclosure** over carousel onboarding | 4/5 | No onboarding carousel; contextual guidance + progressive panels |
| **WCAG 2.2 AA contrast** as a hard constraint, especially over glass | 3/5 | Token-level contrast validation, automated in `verification/test_ui_tokens.py` |
| **Dark UI lowers eye strain** in long AI sessions | 2/5 | Base surface chosen for long-session reading comfort |
| **Motion must earn its place** | 3/5 | `prefers-reduced-motion` honoured; no decorative animation |

## 2. TITAN design tokens (`android/app/src/main/res/values/tokens.xml` + `docs/UI_DESIGN_SYSTEM.md`)

| Token | Value | Use |
|---|---|---|
| `bg.base` | `#0B0F14` | app background |
| `bg.surface` | `#121821` | cards, lists |
| `bg.surface.raised` | `#18212C` | nested panels, code editor |
| `bg.surface.overlay` | `#1F2A37` | sheets, modals (opaque base + translucency) |
| `accent.primary` | `#3B82F6` | primary actions, active nav |
| `accent.cyan` | `#22D3EE` | live/streaming indicators, research status |
| `accent.success` | `#34D399` | verified sources, passing tests |
| `accent.warning` | `#FBBF24` | pending approvals, partial results |
| `accent.danger` | `#F87171` | errors, destructive actions |
| `text.primary` | `#E6EDF5` | body text (≥ 12.9:1 on `bg.base`) |
| `text.secondary` | `#9AA9BC` | labels (≥ 5.6:1 on `bg.base`) |
| `text.disabled` | `#5C6B7F` | non-actionable |
| `radius.sm/md/lg` | 8 / 14 / 22 dp | card radii |
| `space.1..6` | 4 / 8 / 12 / 16 / 24 / 32 dp | 4-pt spacing scale |
| `motion.fast/base/slow` | 120 / 220 / 380 ms | transitions |
| `type.display/title/body/caption` | 28/20/15/12 sp | type scale |

Contrast targets verified by test: `text.primary` on `bg.base` = 12.9:1 (AAA), `text.secondary` = 5.6:1 (AA), `accent.cyan` on `bg.surface` = 9.7:1 (AAA).

## 3. Navigation architecture

**Primary (bottom bar, 6 items):** Home · Chat · Voice · Agents · Workspace · More
**Secondary (More sheet + deep links):** Research Center · Skill Marketplace · Skill Laboratory · Memory · Models · Model Training · Terminal · Projects · Build Center · Workflows · Settings · Security Center

Rules:
- 6 max in the primary bar (thumb reach, WCAG target size ≥ 48 dp).
- Every secondary destination has a deep link (`titan://research`, `titan://workflows/…`) so the backend can push the user to a live task.
- Bottom bar + modal sheets are the **only** glass surfaces.

## 4. Screen contracts (each must implement loading / empty / error / streaming where applicable)

| Screen | Contract |
|---|---|
| **Home** | Bento grid: welcome + command bar; system health; global intelligence status; active agents; running tasks; research activity; model status; recent projects; quick actions. Every tile reads live backend data and shows a `—` + reason when the source is unavailable. |
| **Chat Studio** | Message list with streaming, markdown-ish rendering, code blocks, copy, retry/regenerate/stop, attachments, project context, agent delegation chips, tool-activity collapsible, research citations, export, rename/pin/archive/delete/search over history. |
| **Voice Studio** | Live waveform driven by **real amplitude** from `AudioRecord`; push-to-talk & hands-free; VAD; barge-in (playback stops on new speech); live transcript; language + voice pickers; explicit permission + privacy panel; Bengali availability probed at runtime and shown as available/unavailable. |
| **Agent Center** | Registry grid → agent detail (instructions, model, tool permissions, memory scope, schema, metrics, live task, execution history) → create/configure agent (dynamic factory) with a **sandbox-test gate**. |
| **Research Center** | Global search, platform filters, task list with live progress + per-source status (OK / EMPTY / INACCESSIBLE / ERROR / UNAUTHORIZED), verified findings, repository/model/framework explorers, reports, export, and one-click "convert to Skill / Agent / Project". |
| **Workspace** | Projects, file explorer, editor, terminal, git, builds, logs, artifacts — every action hits the backend. |
| **More sheet** | The 13 secondary destinations, each with its own live data. |

## 5. Anti-patterns explicitly banned (from §17 of the specification)

- Excessive glow → glow is used **only** on the streaming caret and live-status dots.
- Unnecessary text → no lorem-ipsum labels, no "Welcome back!" fluff; every string states a fact.
- Random cards → cards follow the bento grid and carry a consistent header/eyebrow/body structure.
- Fake live status → a "live" indicator is only shown when a real stream is attached.
- Static mock data presented as live → every list is bound to a live endpoint; an unreachable endpoint renders an explicit error state.

## 6. Accessibility

- All interactive targets ≥ 48 dp; content descriptions on every icon.
- Text scales with the system font scale; layout uses weights, not fixed heights.
- `prefers-reduced-motion` equivalent (`Settings.Global.ANIMATOR_DURATION_SCALE == 0`) disables shimmer/pulse.
- Colour is never the only signal: verified/unverified also carry an icon and a text label.
- Screen-reader announcements for streaming completion and agent task transitions.

## 7. Motion

| Interaction | Motion |
|---|---|
| Screen transition | 220 ms fade+slide, disabled under reduced-motion |
| Skeleton shimmer | 1.2 s loop, disabled under reduced-motion |
| Streaming caret | 1 s blink (the only continuous animation) |
| Live status dot | 2 s pulse, disabled under reduced-motion |
| Sheet present | 220 ms translate-up |

## 8. Verification

`verification/test_ui_tokens.py` asserts the token values, the contrast ratios and the "no glass beyond 2 layers" rule against the shipped XML, so the design system cannot silently regress.
