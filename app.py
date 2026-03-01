"""
app.py — Flask application for Web Analyser.

Job-queue design:
  POST /analyze           — enqueues the analysis; returns { job_id }
  GET  /status/<job_id>   — returns { status, stage, detail, progress }
  GET  /result/<job_id>   — returns final analysis JSON (once status == "done")
  GET  /                  — serves the dashboard
"""

import logging
import threading
import time
import traceback
import uuid
from datetime import datetime

from flask import Flask, jsonify, render_template, request

from analyzer import WebsiteAnalyzer
import config as cfg

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── In-memory job store ────────────────────────────────────────────────────────
# Each job:  { status, stage, detail, progress, result, error, created_at }
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _cleanup_old_jobs():
    """Remove jobs older than JOB_TTL_SECONDS (runs in the worker thread)."""
    now = time.time()
    with _jobs_lock:
        stale = [jid for jid, j in _jobs.items()
                 if now - j.get("created_at", 0) > cfg.JOB_TTL_SECONDS]
        for jid in stale:
            del _jobs[jid]
    if stale:
        logger.info("Purged %d stale job(s)", len(stale))


# Stage → approximate progress percentage
_STAGE_PROGRESS = {
    "queued":    5,
    "crawling":  20,
    "security":  40,
    "analysing": 60,
    "done":      100,
    "error":     100,
}


def _run_analysis(job_id: str, url: str, max_pages: int):
    """Worker function — runs in a daemon thread per analysis job."""

    def _progress(stage: str, detail: str | None = None):
        progress = _STAGE_PROGRESS.get(stage, 50)
        # For page-by-page progress refine the percentage
        if stage == "analysing" and detail:
            try:
                # detail looks like "Analysing page 3/20: ..."
                parts = detail.split("/")
                current = int(parts[0].split()[-1])
                total = int(parts[1].split(":")[0])
                if total > 0:
                    ratio = current / total
                    progress = int(40 + ratio * 55)   # 40% → 95%
            except (ValueError, IndexError):
                pass
        elif stage == "crawling" and detail:
            try:
                # detail: "Crawled 3/20: ..."
                parts = detail.split("/")
                current = int(parts[0].split()[-1])
                total = int(parts[1].split(":")[0])
                if total > 0:
                    ratio = current / total
                    progress = int(10 + ratio * 25)   # 10% → 35%
            except (ValueError, IndexError):
                pass

        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id].update(
                    stage=stage,
                    detail=detail or "",
                    progress=progress,
                )
        logger.info("[job %s] %s — %s", job_id[:8], stage, detail or "")

    try:
        analyzer = WebsiteAnalyzer(url, max_pages=max_pages,
                                   progress_callback=_progress)
        results = analyzer.analyze()

        with _jobs_lock:
            _jobs[job_id].update(
                status="done",
                stage="done",
                detail="Analysis complete",
                progress=100,
                result=results,
            )
        logger.info("[job %s] completed successfully", job_id[:8])

    except Exception as e:
        logger.error("[job %s] failed: %s", job_id[:8], e)
        traceback.print_exc()
        with _jobs_lock:
            _jobs[job_id].update(
                status="error",
                stage="error",
                detail=str(e),
                progress=100,
                error=f"Analysis failed: {str(e)}",
            )

    finally:
        _cleanup_old_jobs()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Render the main dashboard."""
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Enqueues an analysis job.
    Body JSON: { url: str, max_pages?: int }
    Returns:   { job_id: str }
    """
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    max_pages = max(1, min(100, int(data.get("max_pages", cfg.DEFAULT_MAX_PAGES))))

    if not url:
        return jsonify({"error": "Please provide a valid URL"}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "stage": "queued",
            "detail": "Job queued — starting shortly",
            "progress": 5,
            "result": None,
            "error": None,
            "created_at": time.time(),
            "url": url,
        }

    thread = threading.Thread(
        target=_run_analysis,
        args=(job_id, url, max_pages),
        daemon=True,
        name=f"analysis-{job_id[:8]}",
    )
    thread.start()
    logger.info("Job %s started for %s (max_pages=%d)", job_id[:8], url, max_pages)

    return jsonify({"job_id": job_id}), 202


@app.route("/status/<job_id>")
def status(job_id: str):
    """
    Returns the current state of a job.
    { status, stage, detail, progress }
    """
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    payload = {
        "status":   job["status"],
        "stage":    job["stage"],
        "detail":   job["detail"],
        "progress": job["progress"],
    }
    if job.get("error"):
        payload["error"] = job["error"]

    return jsonify(payload)


@app.route("/result/<job_id>")
def result(job_id: str):
    """
    Returns the final analysis result once the job is done.
    Returns 404 if not found, 202 if still running, 500 on error.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job["status"] == "error":
        return jsonify({"error": job.get("error", "Unknown error")}), 500

    if job["status"] != "done":
        return jsonify({"status": "running", "progress": job["progress"]}), 202

    return jsonify(job["result"])


# ── Dev server ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # debug=False is intentional — use Gunicorn in production
    app.run(debug=False, host="0.0.0.0", port=5002)
