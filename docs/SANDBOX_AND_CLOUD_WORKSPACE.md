# SANDBOX & CLOUD WORKSPACE

TITAN's execution environment for shells, builds and file work. The terminal in this
deployment is **real**: it runs processes and returns their actual output.

---

## 1. Backends

| Backend | When it is used | State here |
|---|---|---|
| `ProcessBackend` | default | **active** — real process execution with rlimits |
| `DockerBackend` | when a Docker socket is present | unavailable on this host (reported honestly by `/system/capabilities`) |

The active backend is reported by `GET /security/summary` → `sandbox_backend`.

---

## 2. Isolation and limits

| Limit | Setting | Default |
|---|---|---|
| CPU seconds | `sandbox_cpu_seconds` | 20 |
| Memory | `sandbox_memory_mb` | 1024 MB |
| Processes | `sandbox_max_processes` | 64 |
| Wall clock | `sandbox_timeout_seconds` | 30 s |
| Output | `sandbox_max_output_bytes` | 256 KB |
| Root | `sandbox_root` | `/tmp/titan-sandbox` |

Each project gets its own subdirectory under the root, so a workspace cannot read another
project's files by accident. Path traversal outside the root is refused.

---

## 3. Command allowlist

Only these commands may be executed (first token of the command line):

```
ls pwd echo cat head tail wc find grep rg git python3 pip node npm make cmake gradle
javac java kotlinc aapt2 d8 zip unzip sha256sum stat df du ps env which date uname
sort uniq sed awk jq diff tree mkdir cp mv rm touch
```

`curl http://example.com` is **not** on the list, so it is refused — verified by AT-23,
which asserts `ok == false` and `error_code == "BLOCKED_BY_POLICY"`.

A refusal is a normal outcome, not a crash:

```json
{"command": "curl http://example.com", "ok": false, "exit_code": null,
 "stdout": "", "stderr": "command 'curl' is not on the sandbox allowlist",
 "duration_ms": 0.0, "timed_out": false, "truncated": false,
 "error_code": "BLOCKED_BY_POLICY"}
```

The refusal is also written to the audit trail with `outcome = "denied"`.

---

## 4. Toolchain inside the workspace

The allowlist deliberately includes the Android build chain (`java`, `kotlinc`, `aapt2`,
`d8`, `zip`, `unzip`) so a build job can produce an APK from inside TITAN:

```
python3 → java/kotlinc → aapt2 → d8 → zip → apksigner
```

`POST /builds` runs a build command in the sandbox, streams the log to
`build_jobs.log_path`, records the exit code and duration, and stores the produced
artifact in `build_artifacts` with its size and SHA-256.

`release.verify` is a real APK verifier: it opens the APK, checks for `classes.dex`,
`AndroidManifest.xml` and the signature blocks, and reports the findings.

---

## 5. Limits and what is not claimed

| Capability | Status |
|---|---|
| Real shell execution | **available** |
| Per-project isolation | **available** (directory scoping + path-traversal refusal) |
| CPU/memory/process/output caps | **available** |
| Command allowlist | **available** |
| Docker-grade isolation | **blocked** — no Docker socket in this deployment |
| A cloud VM per project | **not implemented** — the workspace is a local sandbox directory |
| Persistent network egress from the sandbox | **restricted** to the allowlist |

This is a **sandbox**, not a cloud provider. The Cloudflare Workers/D1/R2/Queues stack named
in the original brief is a *deployment target* (see `docs/DEPLOYMENT.md`), not something this
build runs.
