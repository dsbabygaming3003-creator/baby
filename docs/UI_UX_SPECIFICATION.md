# UI/UX SPECIFICATION

Premium, futuristic, mobile-first — and every screen is backed by real backend data.

---

## 1. Design language

| Token | Value | Use |
|---|---|---|
| Background | `#0B0F14` graphite | app background |
| Surface 1 / 2 / 3 | `#111823` / `#16202C` / `#1C2836` | elevation ladder (no pure black) |
| Primary accent | `#3DA9FC` | primary actions, active nav |
| Secondary accent | `#31E0C0` cyan | success, live data, wave |
| Warning | `#F5B544` | degraded capabilities |
| Danger | `#FF6B6B` | denials, errors |
| Text primary / secondary | `#E8EEF5` / `#8FA3B8` | hierarchy |

**Glass is selective.** Frosted surfaces are used only for overlays, the bottom navigation
bar and modals — never for content cards, where they would reduce contrast. Every
glass surface keeps a solid fallback colour so it stays legible when the backdrop is busy.

**Contrast** targets WCAG 2.2 AA (4.5:1 for body text, 3:1 for large text and UI
components). Status is never conveyed by colour alone — every state also carries a label
or an icon.

**Motion** is purposeful: a short fade/slide on navigation, a pulsing dot for a live
stream, and a shimmer-free waveform. The system respects the platform's reduced-motion
setting by shortening transitions.

---

## 2. Screens

### Home
Status tiles for backend health, research connectors, agents, models and builds. Each tile
shows the **live** value and its state colour. A capability strip renders the 12 server
capabilities with their real status (`available` / `degraded` / `blocked`) — a blocked
capability is displayed as blocked, not hidden.

### Chat
Conversation list + a message thread. The assistant reply streams token by token over SSE;
a skeleton bubble is shown while the first token is in flight. The provider mode is
displayed when the reply came from the mock provider, so the user is never misled.

### Voice
A large circular record control, a live waveform drawn from the real microphone
amplitude, a live transcript strip, and a play/stop bar for synthesis. Permission is
requested before the first capture.

### Agents
The 20 core agents plus any dynamic ones, each card showing the role, the quality score
and the number of granted tools. Tapping a card opens a detail dialog with the full
execution contract. A "create agent" action opens the factory form.

### Research
Platform chips with live per-connector status, a query field, a platform multi-select, a
run button and a result card showing documents / findings / verified counts plus the
report path. The history list shows previous tasks.

### Workspace
Project list, a terminal card that executes real commands through the sandbox and shows
the actual stdout/stderr and exit code, and a builds card listing build jobs with their
status, exit code and log path.

### More
Five tabs: **Models** (registry + provider health), **Skills** (marketplace + publish
state), **Workflows** (definitions + runs + resume), **Memory** (entries by scope) and
**Security** (RBAC roles, scopes, sandbox limits, egress allowlist, secret configuration
booleans).

---

## 3. Accessibility

| Requirement | Implementation |
|---|---|
| Screen-reader labels | every icon-only control has a content description |
| Touch targets | interactive elements are ≥ 48 dp |
| Text scaling | layouts use `sp` and wrap rather than clip |
| Colour independence | status = colour **+** label/icon |
| Reduced motion | transitions collapse when the platform setting is on |
| Focus order | follows the visual order; no focus traps outside modals |

---

## 4. Data honesty in the UI

* Every value on every screen comes from the backend; there is no hard-coded "demo" data.
* Where a capability is blocked or degraded, the screen says so.
* The chat bubble marks a mock-provider reply.
* The build card shows the real exit code and log path, including failures.
