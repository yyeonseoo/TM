from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
JOBS_PATH = os.path.join(DATA_DIR, "jobs.json")

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_jobs_from_disk():
    _ensure_data_dir()
    if not os.path.exists(JOBS_PATH):
        return
    try:
        with open(JOBS_PATH, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if isinstance(data, dict):
            _JOBS.update(data)
    except Exception:
        # best-effort; keep in-memory jobs
        return


def _save_jobs_to_disk():
    _ensure_data_dir()
    tmp_path = JOBS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fp:
        json.dump(_JOBS, fp, ensure_ascii=False, default=str, indent=2)
    os.replace(tmp_path, JOBS_PATH)


def init_jobs():
    with _LOCK:
        if not _JOBS:
            _load_jobs_from_disk()


def new_job(kind: str, run_id: Optional[str] = None) -> str:
    init_jobs()
    job_id = f"job_{kind}_{uuid.uuid4().hex[:10]}"
    now = _utcnow()
    with _LOCK:
        _JOBS[job_id] = {
            "jobId": job_id,
            "kind": kind,
            "runId": run_id,
            "status": "queued",
            "progress": 0,
            "message": "",
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
            "error": None,
        }
        _save_jobs_to_disk()
    return job_id


def update_job(job_id: str, *, status: Optional[str] = None, progress: Optional[int] = None, message: Optional[str] = None, error: Optional[str] = None):
    now = _utcnow().isoformat()
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        if status is not None:
            job["status"] = status
        if progress is not None:
            job["progress"] = int(max(0, min(100, progress)))
        if message is not None:
            job["message"] = message
        if error is not None:
            job["error"] = error
        job["updatedAt"] = now
        _save_jobs_to_disk()


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    init_jobs()
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def run_in_thread(job_id: str, fn: Callable[[], None]):
    def _runner():
        try:
            update_job(job_id, status="running", progress=1)
            fn()
            update_job(job_id, status="done", progress=100, message="완료")
        except Exception as exc:
            update_job(job_id, status="error", progress=100, error=str(exc), message="실패")

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    time.sleep(0.01)

