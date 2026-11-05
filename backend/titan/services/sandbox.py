"""Sandboxed command execution.

Two backends implement one interface:
  * ``ProcessBackend`` — always available. Uses a jailed working root, POSIX
    resource limits, a scrubbed environment, a command allowlist, a wall-clock
    timeout with process-group kill and bounded output capture.
  * ``DockerBackend`` — used when a Docker daemon is present; the container
    gives stronger isolation for untrusted code.
"""
from __future__ import annotations

import asyncio
import os
import resource
import shlex
import shutil
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import settings


class SandboxError(RuntimeError):
    pass


@dataclass
class ExecutionResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> Dict:
        return {
            "command": self.command, "exit_code": self.exit_code, "stdout": self.stdout,
            "stderr": self.stderr, "duration_ms": round(self.duration_ms, 2),
            "timed_out": self.timed_out, "truncated": self.truncated, "ok": self.ok,
        }


def _limits() -> None:
    """Applied inside the child process before exec."""
    cpu = settings.sandbox_cpu_seconds
    mem = settings.sandbox_memory_mb * 1024 * 1024
    file_size = settings.sandbox_max_output_bytes
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_size, file_size))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (settings.sandbox_max_processes, settings.sandbox_max_processes))
    except (ValueError, OSError):
        pass


def _scrubbed_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Minimal environment: no provider secrets leak into shell output."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(settings.sandbox_root),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONUNBUFFERED": "1",
        "TITAN_SANDBOX": "1",
    }
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    return env


class ProcessBackend:
    """rlimit + jail based isolation. No Docker required."""

    name = "process"

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root or settings.sandbox_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def project_root(self, project_id: str) -> Path:
        safe = "".join(ch for ch in project_id if ch.isalnum() or ch in "-_")[:64] or "default"
        path = (self.root / safe).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise SandboxError("project root escapes the sandbox")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_path(self, project_id: str, relative: str) -> Path:
        base = self.project_root(project_id)
        candidate = (base / relative).resolve()
        if not str(candidate).startswith(str(base.resolve())):
            raise SandboxError(f"path '{relative}' escapes the project root")
        return candidate

    def _check_command(self, command: str) -> List[str]:
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            raise SandboxError(f"cannot parse command: {exc}") from exc
        if not parts:
            raise SandboxError("empty command")
        binary = os.path.basename(parts[0])
        if binary not in settings.command_allowlist:
            raise SandboxError(
                f"command '{binary}' is not in the allowlist "
                f"({len(settings.command_allowlist)} commands permitted)"
            )
        for part in parts:
            if ".." in part and part.startswith("/"):
                raise SandboxError("absolute traversal is not permitted")
        return parts

    async def run(self, command: str, *, project_id: str = "default",
                  timeout: Optional[int] = None,
                  env: Optional[Dict[str, str]] = None) -> ExecutionResult:
        parts = self._check_command(command)
        cwd = self.project_root(project_id)
        timeout = timeout or settings.sandbox_timeout_seconds
        started = time.perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                *parts,
                cwd=str(cwd),
                env=_scrubbed_env(env),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
                preexec_fn=_limits,
            )
        except FileNotFoundError:
            return ExecutionResult(command, 127, "", f"command not found: {parts[0]}",
                                   (time.perf_counter() - started) * 1000)
        except OSError as exc:
            return ExecutionResult(command, 126, "", str(exc), (time.perf_counter() - started) * 1000)

        timed_out = False
        try:
            stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                process.kill()
            stdout_b, stderr_b = await process.communicate()

        max_bytes = settings.sandbox_max_output_bytes
        truncated = False
        stdout = stdout_b.decode("utf-8", "replace")
        stderr = stderr_b.decode("utf-8", "replace")
        if len(stdout) > max_bytes:
            stdout = stdout[:max_bytes] + f"\n... [truncated at {max_bytes} bytes]"
            truncated = True
        if len(stderr) > max_bytes:
            stderr = stderr[:max_bytes] + f"\n... [truncated at {max_bytes} bytes]"
            truncated = True
        return ExecutionResult(
            command=command,
            exit_code=process.returncode if process.returncode is not None else -1,
            stdout=stdout,
            stderr=stderr,
            duration_ms=(time.perf_counter() - started) * 1000,
            timed_out=timed_out,
            truncated=truncated,
        )


class DockerBackend:
    """Container isolation for deployments that have a Docker daemon."""

    name = "docker"

    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image
        self.process = ProcessBackend()

    @staticmethod
    def available() -> bool:
        return shutil.which("docker") is not None

    async def run(self, command: str, *, project_id: str = "default",
                  timeout: Optional[int] = None,
                  env: Optional[Dict[str, str]] = None) -> ExecutionResult:
        if not self.available():
            return await self.process.run(command, project_id=project_id, timeout=timeout, env=env)
        root = self.process.project_root(project_id)
        timeout = timeout or settings.sandbox_timeout_seconds
        docker_cmd = (
            f"docker run --rm --network none --memory {settings.sandbox_memory_mb}m "
            f"--cpus 1.0 --pids-limit {settings.sandbox_max_processes} "
            f"-v {root}:/workspace -w /workspace {self.image} sh -lc {shlex.quote(command)}"
        )
        return await self.process.run(docker_cmd, project_id=project_id, timeout=timeout, env=env)


def get_backend() -> ProcessBackend | DockerBackend:
    """Prefer container isolation when a daemon is present, else process isolation."""
    if DockerBackend.available():
        return DockerBackend()
    return ProcessBackend()


backend = get_backend()
