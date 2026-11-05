# Cloud Execution and Build Boundary

## Development implementation

Each project has an owner-scoped directory under the configured workspace. File operations canonicalize paths and reject symlinks. Terminal commands use an argument vector, executable allowlist, closed stdin, minimal environment, real stdout, timeout and output limit. Python manifests can run compileall through the build service.

This is a real local execution service, **not** a secure cloud Linux sandbox. It does not provide CPU/memory/disk quotas, kernel isolation or reliable network denial. Project code can still execute through interpreters/package scripts. The production Compose reference disables terminal execution.

## Required production worker

Use per-job disposable non-root containers/VMs, dedicated tenant identity, read-only base image, writable scratch quota, seccomp/AppArmor, PID/CPU/memory/disk/time limits, no host Docker socket, default-deny egress and artifact signature/hash verification. Install JDK 17, Android SDK 36 and a pinned Gradle distribution only in the Android worker image.

Build acceptance requires actual logs, variant/version, artifact path, SHA-256/size, install on adb/device and launch evidence. Missing tools return `blocked`, never a success message or fake APK. Current environment fails those prerequisites.
