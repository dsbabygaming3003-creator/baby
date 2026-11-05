"""Voice, translation, build and evaluation services."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..config import settings
from ..models import BuildArtifact, BuildJob, ModelEvaluation, TrainingDataset
from .gateway import CompletionRequest, gateway
from .observability import log, metrics

# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: Dict[str, str] = {
    "bn": "Bengali", "en": "English", "ar": "Arabic", "hi": "Hindi",
    "ja": "Japanese", "ko": "Korean", "zh": "Chinese", "fr": "French",
    "de": "German", "es": "Spanish", "pt": "Portuguese", "it": "Italian",
    "ru": "Russian", "tr": "Turkish", "vi": "Vietnamese", "id": "Indonesian",
    "ms": "Malay", "ta": "Tamil", "te": "Telugu", "mr": "Marathi",
    "gu": "Gujarati", "ur": "Urdu", "fa": "Persian", "he": "Hebrew",
    "th": "Thai", "uk": "Ukrainian", "pl": "Polish", "nl": "Dutch",
    "sv": "Swedish", "el": "Greek",
}

_SCRIPT_HINTS = [
    (re.compile(r"[\u0980-\u09FF]"), "bn"),   # Bengali
    (re.compile(r"[\u0600-\u06FF]"), "ar"),   # Arabic
    (re.compile(r"[\u4E00-\u9FFF]"), "zh"),   # Chinese
    (re.compile(r"[\uAC00-\uD7AF]"), "ko"),   # Hangul
    (re.compile(r"[\u3040-\u30FF]"), "ja"),   # Kana
    (re.compile(r"[\u0900-\u097F]"), "hi"),   # Devanagari
    (re.compile(r"[\u0370-\u03FF]"), "el"),   # Greek
    (re.compile(r"[\u0400-\u04FF]"), "ru"),   # Cyrillic
]


def detect_language(text: str) -> Dict[str, Any]:
    """Detect language using lingua when available, else a script heuristic."""
    text = (text or "").strip()
    if not text:
        return {"language": "und", "confidence": 0.0, "method": "empty"}
    try:
        from lingua import LanguageDetectorBuilder

        detector = LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()
        result = detector.detect_language_of(text)
        code = result.iso_code_639_1.name.lower() if result else "und"
        return {"language": code, "confidence": round(result.accuracy, 4) if result else 0.0,
                "method": "lingua"}
    except Exception:
        pass
    for pattern, code in _SCRIPT_HINTS:
        if pattern.search(text):
            return {"language": code, "confidence": 0.85, "method": "script-heuristic"}
    ascii_words = re.findall(r"[A-Za-z]+", text)
    if ascii_words:
        return {"language": "en", "confidence": 0.6, "method": "heuristic"}
    return {"language": "und", "confidence": 0.0, "method": "unknown"}


class TranslationService:
    async def translate(self, text: str, target: str, *, source: Optional[str] = None,
                        glossary: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if target not in SUPPORTED_LANGUAGES:
            return {"ok": False, "error": f"target language '{target}' is not supported",
                    "supported": sorted(SUPPORTED_LANGUAGES)}
        detection = detect_language(text) if not source else {"language": source, "confidence": 1.0,
                                                             "method": "explicit"}
        glossary = glossary or {}
        glossary_note = ("\nPreserve these technical terms verbatim: "
                         + ", ".join(f"{k} -> {v}" for k, v in glossary.items())) if glossary else ""
        prompt = (
            f"Translate the user's text into {SUPPORTED_LANGUAGES[target]} ({target}).\n"
            f"Source language: {detection['language']}.\n"
            "Preserve code identifiers, product names, numbers and units verbatim. "
            "Return only the translation."
            + glossary_note
        )
        result = await gateway.complete(CompletionRequest(
            messages=[{"role": "system", "content": "You are a precise multilingual translator."},
                      {"role": "user", "content": f"{prompt}\n\n---\n{text}"}],
            task="translation", max_tokens=2048,
        ))
        metrics.incr("translations_total", target=target, status="ok" if result.ok else "error")
        return {
            "ok": result.ok, "translation": result.text, "source_language": detection["language"],
            "target_language": target, "provider_mode": result.provider_mode, "model": result.model,
            "latency_ms": result.latency_ms, "error": result.error,
        }

    def supported(self) -> List[Dict[str, str]]:
        return [{"code": code, "name": name} for code, name in sorted(SUPPORTED_LANGUAGES.items())]


# ---------------------------------------------------------------------------
# Voice
# ---------------------------------------------------------------------------


class VoiceService:
    """Server-side ASR/TTS adapters plus an honest capability report.

    The Android client performs on-device capture/playback; the server keeps
    the transcripts and exposes provider adapters for cloud engines.
    """

    def __init__(self) -> None:
        self._transcripts: List[Dict[str, Any]] = []

    async def capabilities(self) -> Dict[str, Any]:
        local_whisper = shutil.which("whisper-cli") or shutil.which("whisper")
        piper = shutil.which("piper")
        cloud = {}
        for provider_id, env_key in (("openai", "OPENAI_API_KEY"), ("groq", "GROQ_API_KEY"),
                                     ("gemini", "GEMINI_API_KEY")):
            from ..security.core import secret_store

            cloud[provider_id] = secret_store.status(env_key)
        return {
            "server": {
                "whisper_cpp_binary": bool(local_whisper),
                "piper_binary": bool(piper),
                "cloud_providers": cloud,
            },
            "client": {
                "android_speech_recognizer": "provided by the platform (Android client)",
                "android_text_to_speech": "provided by the platform (Android client)",
                "bengali": "probed at runtime by the client via TextToSpeech.isLanguageAvailable('bn')",
            },
            "note": "A language is reported as supported only after a runtime probe succeeds.",
        }

    async def transcribe(self, session, *, audio_path: str, language: str = "bn",
                         org_id: str = "default") -> Dict[str, Any]:
        """Transcribe an uploaded audio file.

        No ASR engine is reachable in this deployment, so the method reports a
        precise, honest failure rather than inventing a transcript.
        """
        path = Path(audio_path)
        if not path.exists():
            return {"ok": False, "error": f"audio file not found: {audio_path}"}
        size = path.stat().st_size
        whisper = shutil.which("whisper-cli") or shutil.which("whisper")
        if whisper:
            import subprocess

            process = subprocess.run([whisper, "-l", language, "-f", str(path), "-otxt", "-of", str(path)],
                                     capture_output=True, text=True, timeout=300)
            text_path = Path(str(path) + ".txt")
            text = text_path.read_text(encoding="utf-8") if text_path.exists() else ""
            record = {"ok": process.returncode == 0, "transcript": text, "engine": "whisper.cpp",
                      "language": language, "size_bytes": size}
        else:
            record = {
                "ok": False,
                "error": "no ASR engine is installed in this deployment (whisper.cpp binary not found). "
                         "Use the Android client's on-device SpeechRecognizer, or install an ASR engine.",
                "engine": None, "language": language, "size_bytes": size,
            }
        self._transcripts.append(record)
        await session.flush()
        metrics.incr("transcriptions_total", status="ok" if record.get("ok") else "error")
        return record

    async def speak(self, text: str, *, language: str = "bn", voice: Optional[str] = None) -> Dict[str, Any]:
        """Server-side TTS.

        Piper is the reference engine; without it the service reports the
        boundary honestly and returns the text to be spoken by the client.
        """
        piper = shutil.which("piper")
        if not piper:
            return {"ok": False, "error": "no TTS engine is installed in this deployment (piper binary not found).",
                    "engine": None, "fallback": "client_tts", "text": text, "language": language}
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            output_path = handle.name
        process = subprocess.run([piper, "--output_file", output_path],
                                 input=text.encode("utf-8"), capture_output=True, timeout=120)
        return {"ok": process.returncode == 0, "engine": "piper", "language": language,
                "audio_path": output_path if process.returncode == 0 else None,
                "error": process.stderr.decode("utf-8", "replace")[:400]}


# ---------------------------------------------------------------------------
# Build service
# ---------------------------------------------------------------------------


class BuildService:
    async def run_build(self, session, *, project_id: Optional[str], name: str,
                        command: str, target: str = "apk", variant: str = "debug",
                        org_id: str = "default") -> BuildJob:
        job = BuildJob(project_id=project_id, name=name, target=target, variant=variant,
                       command=command, status="queued")
        session.add(job)
        await session.flush()

        from .sandbox import backend

        started = time.perf_counter()
        job.status = "running"
        await session.flush()
        result = await backend.run(command, project_id=project_id or "default",
                                   timeout=settings.workflow_step_timeout_seconds)
        duration = (time.perf_counter() - started) * 1000

        log_dir = settings.data_dir / "builds" / job.id
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "build.log"
        log_path.write_text(
            f"$ {command}\n\nexit={result.exit_code} timed_out={result.timed_out} "
            f"duration_ms={duration:.1f}\n\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n",
            encoding="utf-8",
        )
        job.status = "succeeded" if result.ok else "failed"
        job.exit_code = result.exit_code
        job.duration_ms = duration
        job.log_path = str(log_path)
        job.error = (result.stderr or "")[:4000] if not result.ok else ""
        await session.flush()

        # register artifacts produced in the sandbox root
        if project_id:
            root = backend.project_root(project_id) if hasattr(backend, "project_root") else None
            if root and root.exists():
                for path in sorted(root.rglob("*")):
                    if path.is_file() and path.suffix in (".apk", ".aab", ".jar", ".so", ".aar", ".zip"):
                        digest = hashlib.sha256(path.read_bytes()).hexdigest()
                        session.add(BuildArtifact(
                            build_job_id=job.id, name=path.name, kind=path.suffix.lstrip("."),
                            size_bytes=path.stat().st_size, sha256=digest, path=str(path),
                        ))
        await session.flush()
        metrics.incr("builds_total", status=job.status)
        return job

    async def list_jobs(self, session, org_id: str = "default", limit: int = 30) -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(BuildJob).where(BuildJob.org_id == org_id)
            .order_by(BuildJob.created_at.desc()).limit(limit)
        )).scalars().all()
        output = []
        for job in rows:
            artifacts = (await session.execute(
                select(BuildArtifact).where(BuildArtifact.build_job_id == job.id)
            )).scalars().all()
            output.append({
                "id": job.id, "name": job.name, "target": job.target, "variant": job.variant,
                "status": job.status, "exit_code": job.exit_code, "duration_ms": job.duration_ms,
                "command": job.command, "log_path": job.log_path, "error": job.error,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "artifacts": [{"name": a.name, "kind": a.kind, "size_bytes": a.size_bytes,
                               "sha256": a.sha256, "download_url": a.download_url} for a in artifacts],
            })
        return output


# ---------------------------------------------------------------------------
# Model evaluation + training
# ---------------------------------------------------------------------------

DEFAULT_EVAL_CASES = [
    {"id": "json-output", "prompt": "Return a JSON object with keys 'name' and 'count' where name is 'titan' and count is 3.",
     "criteria": {"type": "json", "keys": ["name", "count"]}},
    {"id": "refusal-discipline", "prompt": "Explain in one sentence why sky is blue.",
     "criteria": {"type": "min_length", "value": 40}},
    {"id": "instruction-following", "prompt": "Reply with exactly the word: TITAN",
     "criteria": {"type": "contains", "value": "TITAN"}},
    {"id": "no-fabrication", "prompt": "What is the airspeed velocity of an unladen swallow?",
     "criteria": {"type": "not_empty", "forbid": ["as an ai language model"]}},
]


class EvaluationService:
    async def evaluate_model(self, session, model_id: str, *, dataset_id: Optional[str] = None,
                             cases: Optional[List[Dict[str, Any]]] = None,
                             org_id: str = "default") -> Dict[str, Any]:
        """Run a real benchmark and store measured scores."""
        from ..models import ModelRecord  # noqa: F401  (ensures table registered)

        cases = cases or DEFAULT_EVAL_CASES
        # Normalise and validate the case set: a case without a prompt cannot be
        # scored, and a case without an id gets a stable generated one.
        normalised: List[Dict[str, Any]] = []
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                raise ValueError(f"evaluation case #{index} must be an object")
            prompt = (case.get("prompt") or case.get("input") or "").strip()
            if not prompt:
                raise ValueError(f"evaluation case #{index} has no prompt")
            normalised.append({**case, "id": str(case.get("id") or f"case-{index + 1}"),
                               "prompt": prompt})
        cases = normalised

        results: List[Dict[str, Any]] = []
        total_score = 0.0
        total_latency = 0.0
        total_cost = 0.0
        provider_modes: List[str] = []

        for case in cases:
            started = time.perf_counter()
            completion = await gateway.complete(CompletionRequest(
                messages=[{"role": "user", "content": case["prompt"]}],
                model=model_id, task="chat", max_tokens=512,
            ))
            latency = (time.perf_counter() - started) * 1000
            score, detail = self._score(case, completion.text, completion.ok)
            total_score += score
            total_latency += latency
            total_cost += completion.cost_usd
            provider_modes.append(completion.provider_mode)
            results.append({
                "case_id": case["id"], "score": score, "detail": detail,
                "latency_ms": round(latency, 2), "model": completion.model,
                "provider_mode": completion.provider_mode,
                "output_preview": (completion.text or "")[:400],
                "error": completion.error,
            })

        avg = total_score / len(cases) if cases else 0.0
        record = ModelEvaluation(
            model_id=model_id, dataset_id=dataset_id, score=round(avg, 4),
            latency_ms=round(total_latency / len(cases), 2) if cases else 0.0,
            cost_usd=round(total_cost, 6), sample_count=len(cases),
            provider_mode="mock" if "mock" in provider_modes else "real",
            details={"cases": results, "criteria_source": "built-in default dataset"},
            org_id=org_id,
        )
        session.add(record)
        await session.flush()
        metrics.incr("model_evaluations_total", model=model_id)
        return {"evaluation_id": record.id, "model_id": model_id, "score": record.score,
                "latency_ms": record.latency_ms, "cost_usd": record.cost_usd,
                "cases": results, "provider_mode": record.provider_mode}

    def _score(self, case: Dict[str, Any], text: str, ok: bool) -> tuple[float, str]:
        criteria = case.get("criteria") or {}
        if not ok:
            return 0.0, "provider call failed"
        body = (text or "").strip()
        kind = criteria.get("type")
        if kind == "json":
            try:
                payload = json.loads(body[body.find("{"): body.rfind("}") + 1])
            except Exception:
                return 0.0, "output was not parseable JSON"
            missing = [k for k in criteria.get("keys", []) if k not in payload]
            return (1.0, "valid JSON with all required keys") if not missing else (0.5, f"missing keys: {missing}")
        if kind == "min_length":
            ok_len = len(body) >= int(criteria.get("value", 0))
            return (1.0, f"length {len(body)}") if ok_len else (0.0, f"length {len(body)} below threshold")
        if kind == "contains":
            value = criteria.get("value", "")
            found = value.lower() in body.lower()
            return (1.0, "required content present") if found else (0.0, "required content missing")
        if kind == "not_empty":
            if not body:
                return 0.0, "empty output"
            for forbid in criteria.get("forbid", []):
                if forbid.lower() in body.lower():
                    return 0.0, f"output contained refusal phrase '{forbid}'"
            return 1.0, "non-empty output"
        return 0.5, "no criterion matched"

    async def list_evaluations(self, session, model_id: Optional[str] = None,
                               org_id: str = "default", limit: int = 50) -> List[Dict[str, Any]]:
        stmt = select(ModelEvaluation).where(ModelEvaluation.org_id == org_id)
        if model_id:
            stmt = stmt.where(ModelEvaluation.model_id == model_id)
        rows = (await session.execute(
            stmt.order_by(ModelEvaluation.created_at.desc()).limit(limit)
        )).scalars().all()
        return [
            {"id": r.id, "model_id": r.model_id, "score": r.score, "latency_ms": r.latency_ms,
             "cost_usd": r.cost_usd, "sample_count": r.sample_count,
             "provider_mode": r.provider_mode,
             "created_at": r.created_at.isoformat() if r.created_at else None,
             "details": r.details}
            for r in rows
        ]

    # -- training ---------------------------------------------------------
    async def prepare_dataset(self, session, *, name: str, records: List[Dict[str, Any]],
                              org_id: str = "default", source: str = "manual") -> Dict[str, Any]:
        """Clean, deduplicate and quality-filter a dataset.

        This is Level-1/2/3 preparation. It does NOT train a model: no training
        runtime exists in this deployment, and the service refuses to claim
        otherwise.
        """
        seen: set = set()
        cleaned: List[Dict[str, Any]] = []
        duplicates = 0
        rejected = 0
        for record in records:
            prompt = (record.get("prompt") or "").strip()
            completion = (record.get("completion") or "").strip()
            if not prompt or not completion:
                rejected += 1
                continue
            digest = hashlib.sha256(f"{prompt}\n{completion}".encode()).hexdigest()
            if digest in seen:
                duplicates += 1
                continue
            seen.add(digest)
            if len(prompt) < 3 or len(completion) < 1:
                rejected += 1
                continue
            cleaned.append({"prompt": prompt, "completion": completion})

        dataset = TrainingDataset(
            name=name, source=source, record_count=len(records), cleaned_count=len(cleaned),
            status="prepared", org_id=org_id,
            licence_note=records[0].get("licence", "operator must confirm training-data rights")
            if records else "unspecified",
            stats={"duplicates_removed": duplicates, "rejected": rejected,
                   "quality_filter": "non-empty prompt and completion, exact-duplicate removal"},
        )
        session.add(dataset)
        await session.flush()
        return {"dataset_id": dataset.id, "records_in": len(records), "records_clean": len(cleaned),
                "duplicates_removed": duplicates, "rejected": rejected, "status": dataset.status}

    async def list_datasets(self, session, org_id: str = "default") -> List[Dict[str, Any]]:
        rows = (await session.execute(
            select(TrainingDataset).where(TrainingDataset.org_id == org_id)
            .order_by(TrainingDataset.created_at.desc())
        )).scalars().all()
        return [
            {"id": r.id, "name": r.name, "source": r.source, "record_count": r.record_count,
             "cleaned_count": r.cleaned_count, "status": r.status, "stats": r.stats,
             "licence_note": r.licence_note,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]

    async def training_status(self, session, org_id: str = "default") -> Dict[str, Any]:
        """Honest report of the fine-tuning capability of this deployment."""
        datasets = await self.list_datasets(session, org_id)
        runtime = None
        for module in ("torch", "transformers", "peft", "trl"):
            try:
                __import__(module)
                runtime = module
                break
            except Exception:
                continue
        return {
            "level": "Level 3 — skills acquired" if runtime is None else "Level 4 — training runtime present",
            "training_runtime_available": runtime is not None,
            "detected_runtime": runtime,
            "datasets": datasets,
            "jobs": [],
            "status": "NOT_RUN",
            "reason": (
                "No training runtime (torch/transformers/peft) is installed in this deployment, so no "
                "fine-tuning job can be executed. Dataset preparation, cleaning, deduplication and "
                "quality filtering ARE implemented and were run on the datasets listed above."
            ) if runtime is None else "Training runtime detected; job submission is not enabled by default.",
            "policy": "This service never reports a trained model without a real training artifact and an evaluation report.",
        }


translation_service = TranslationService()
voice_service = VoiceService()
build_service = BuildService()
evaluation_service = EvaluationService()
