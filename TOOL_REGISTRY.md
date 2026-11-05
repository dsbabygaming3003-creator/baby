# Tool Registry

| Tool | Version | Real behavior | Permission and error contract |
|---|---|---|---|
| `research.github` | 1.0.0 | Official GitHub repository search, normalization, source evidence | Fixed HTTPS endpoint; OS CA verification; bounded results; source error persisted |
| `project.file.read` | 1.0.0 | UTF-8 project file read | Owner check, canonical path, symlink denial, 1 MB limit, binary rejection |
| `project.file.write` | 1.0.0 | Atomic project file write | Owner check, canonical path, symlink denial, size-limited schema |
| `terminal.exec` | 1.0.0 | `create_subprocess_exec`, real stdout/status/duration | Exact approval, owner check, executable allowlist, no shell, stdin closed, sanitized env, timeout/output cap |
| `build.detect` | 1.0.0 | Android toolchain blocker or Python compileall build | Owner/admin, persisted command/log/status; no artifact claim without a file |
| `model.invoke` | 1.0.0 | Explicit mock or OpenAI-compatible HTTP/SSE | Server-side secret, provider selection, output validation, timeout, usage records |
| `skill.execute` | 1.0.0 | Allowlisted pure-Python handler | Tested + approved + active + owner; input/output object schemas |

Terminal allowlist: `python3`, `python`, `node`, `npm`, `git`, `pytest`, `ls`. Allowlisting an executable is not a hardened security sandbox—project scripts can still execute code. Server policy can disable the terminal, and the Compose production reference disables it.

Not implemented as executable tools: browser automation, generic computer use, arbitrary code plugins, database migration agent, deployment, social connectors, media processing and fine-tuning.
