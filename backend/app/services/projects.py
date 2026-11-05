import asyncio
import os
import shutil
import time
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import BuildJob, Project, ToolExecution, utcnow
from ..schemas import ProjectCreate
from ..utils import redact, sanitize_argv, slugify

ALLOWED_EXECUTABLES = {"python3", "python", "node", "npm", "git", "pytest", "ls"}


class ProjectService:
    def __init__(self, db: AsyncSession, settings: Settings):
        self.db = db
        self.settings = settings

    async def create(self, owner_id: str, data: ProjectCreate) -> Project:
        base = slugify(data.name)
        relative = base
        suffix = 2
        while await self.db.scalar(select(Project).where(Project.relative_path == relative)):
            relative = f"{base}-{suffix}"
            suffix += 1
        project = Project(
            owner_id=owner_id,
            name=data.name,
            description=data.description,
            template=data.template,
            relative_path=relative,
        )
        root = self._root(project)
        root.mkdir(parents=True, exist_ok=False)
        if data.template == "python":
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "README.md").write_text(
                f"# {data.name}\n\nPython project managed by TITAN.\n", encoding="utf-8"
            )
        elif data.template == "research":
            (root / "RESEARCH.md").write_text(
                f"# {data.name}\n\nResearch project. Sources and verification state required.\n",
                encoding="utf-8",
            )
        else:
            (root / "README.md").write_text(
                f"# {data.name}\n\n{data.description}\n", encoding="utf-8"
            )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get(self, project_id: str, owner_id: str) -> Project:
        project = await self.db.scalar(
            select(Project).where(Project.id == project_id, Project.owner_id == owner_id)
        )
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    def _root(self, project: Project) -> Path:
        root = (self.settings.workspace_root / project.relative_path).resolve()
        workspace = self.settings.workspace_root.resolve()
        if root != workspace and workspace not in root.parents:
            raise HTTPException(status_code=400, detail="Project path escapes workspace")
        return root

    def _path(self, project: Project, relative_path: str) -> Path:
        if "\x00" in relative_path:
            raise HTTPException(status_code=400, detail="Invalid path")
        root = self._root(project)
        path = (root / relative_path).resolve()
        if path == root or root not in path.parents:
            raise HTTPException(status_code=400, detail="Path traversal denied")
        # Reject traversal through a symlink even when its resolved target initially appears valid.
        current = root
        for part in Path(relative_path).parts:
            current = current / part
            if current.is_symlink():
                raise HTTPException(status_code=400, detail="Symlink access is not permitted")
        return path

    async def files(self, project_id: str, owner_id: str) -> list[dict]:
        project = await self.get(project_id, owner_id)
        root = self._root(project)
        output = []
        for path in sorted(root.rglob("*")):
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            output.append(
                {
                    "path": str(path.relative_to(root)),
                    "type": "directory" if path.is_dir() else "file",
                    "size": path.stat().st_size if path.is_file() else None,
                }
            )
        return output[:2000]

    async def read_file(self, project_id: str, owner_id: str, path: str) -> dict:
        project = await self.get(project_id, owner_id)
        target = self._path(project, path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        if target.stat().st_size > 1_000_000:
            raise HTTPException(status_code=413, detail="File exceeds editor size limit")
        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=415, detail="Binary files are not supported by this editor"
            ) from exc
        return {"path": path, "content": content}

    async def write_file(self, project_id: str, owner_id: str, path: str, content: str) -> dict:
        project = await self.get(project_id, owner_id)
        target = self._path(project, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.titan-tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, target)
        return {"path": path, "bytes": len(content.encode("utf-8")), "written": True}

    async def terminal(
        self, owner_id: str, project_id: str, argv: list[str], approved: bool, timeout_seconds: int
    ) -> ToolExecution:
        started = time.perf_counter()
        record = ToolExecution(
            actor_id=owner_id,
            project_id=project_id,
            tool_id="terminal.exec",
            arguments={"argv": sanitize_argv(argv)},
            approved=approved,
            status="queued",
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        if not self.settings.terminal_enabled:
            record.status = "blocked"
            record.error = "Terminal execution is disabled by server policy"
            await self.db.commit()
            return record
        if not approved:
            record.status = "approval_required"
            record.error = "Exact command approval is required"
            await self.db.commit()
            return record
        project = await self.get(project_id, owner_id)
        executable = argv[0]
        if executable not in ALLOWED_EXECUTABLES or Path(executable).name != executable:
            record.status = "denied"
            record.error = f"Executable not allowlisted: {executable}"
            await self.db.commit()
            return record
        binary = shutil.which(executable)
        if not binary:
            record.status = "blocked"
            record.error = f"Executable not installed: {executable}"
            await self.db.commit()
            return record
        record.status = "running"
        await self.db.commit()
        try:
            process = await asyncio.create_subprocess_exec(
                binary,
                *argv[1:],
                cwd=self._root(project),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "LANG": "C.UTF-8",
                    "HOME": str(self._root(project)),
                },
            )
            try:
                output, _ = await asyncio.wait_for(
                    process.communicate(),
                    timeout=min(timeout_seconds, self.settings.terminal_max_seconds),
                )
            except TimeoutError:
                process.kill()
                output, _ = await process.communicate()
                record.status = "timeout"
                record.error = "Command exceeded its execution timeout"
            else:
                record.status = "succeeded" if process.returncode == 0 else "failed"
                record.error = (
                    None
                    if process.returncode == 0
                    else f"Command exited with code {process.returncode}"
                )
            record.output = redact(output.decode("utf-8", "replace"))[:200_000]
        except Exception as exc:
            record.status = "failed"
            record.error = str(exc)[:1000]
        record.duration_ms = (time.perf_counter() - started) * 1000
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def build(self, project_id: str, owner_id: str, variant: str) -> BuildJob:
        project = await self.get(project_id, owner_id)
        root = self._root(project)
        job = BuildJob(project_id=project.id, status="running", variant=variant)
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        if (root / "settings.gradle.kts").exists() or (root / "settings.gradle").exists():
            missing = [name for name in ("java", "gradle", "adb") if not shutil.which(name)]
            job.status = "blocked"
            job.error = "Android build/install toolchain unavailable"
            job.logs = f"Missing tools: {', '.join(missing)}. No APK was generated."
        elif (root / "pyproject.toml").exists() or (root / "pytest.ini").exists():
            result = await self.terminal(
                owner_id, project.id, ["python3", "-m", "compileall", "-q", "."], True, 20
            )
            job.command = ["python3", "-m", "compileall", "-q", "."]
            job.logs = result.output
            job.status = "succeeded" if result.status == "succeeded" else "failed"
            job.error = result.error
        else:
            job.status = "blocked"
            job.error = "No supported build manifest detected"
            job.logs = "No artifact was generated. Add a supported project manifest."
        job.completed_at = utcnow()
        await self.db.commit()
        await self.db.refresh(job)
        return job
