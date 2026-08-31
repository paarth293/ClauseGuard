"""
ClauseGuard Pipeline Logger
Centralized logging with structured output, step timing, and pipeline metrics.
All pipeline modules should import and use this instead of raw print() calls.
"""

import sys
import time
import logging
import json
from datetime import datetime, timezone
from typing import Optional

# Force UTF-8 on Windows terminals to avoid UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass  # Python < 3.7 fallback


# ── Logger Setup ──────────────────────────────────────────────────────────────

class PipelineLogger:
    """
    Structured logger for the ClauseGuard pipeline.
    Provides step-by-step timing, finding counts, and audit trail.
    """

    def __init__(self, contract_name: Optional[str] = None):
        self.contract_name = contract_name or "unknown"
        self.step_times: list[dict] = []
        self.metrics: dict = {}
        self._current_step_start: Optional[float] = None
        self._current_step_name: Optional[str] = None
        self.start_time = time.time()

        # Configure the underlying Python logger
        self._logger = logging.getLogger(f"clauseguard.{self.contract_name}")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "[%(asctime)s] %(levelname)s | %(message)s",
                datefmt="%H:%M:%S"
            ))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    # ── Step Tracking ─────────────────────────────────────────────────────

    def step_start(self, step_name: str, details: str = ""):
        """Mark the beginning of a pipeline step."""
        self._current_step_name = step_name
        self._current_step_start = time.time()
        msg = f">> [{step_name}]"
        if details:
            msg += f" {details}"
        self._logger.info(msg)
        print(msg)

    def step_end(self, finding_count: Optional[int] = None, details: str = ""):
        """Mark the end of the current pipeline step and record timing."""
        if self._current_step_start is None or self._current_step_name is None:
            return

        elapsed = time.time() - self._current_step_start
        step_record = {
            "step": self._current_step_name,
            "elapsed_seconds": round(elapsed, 3),
            "finding_count": finding_count,
        }

        msg = f"OK [{self._current_step_name}] completed in {elapsed:.2f}s"
        if finding_count is not None:
            msg += f" | findings: {finding_count}"
        if details:
            msg += f" | {details}"

        self._logger.info(msg)
        print(msg)

        self.step_times.append(step_record)
        self._current_step_start = None
        self._current_step_name = None

    # ── Finding Logging ───────────────────────────────────────────────────

    def log_findings(self, stage: str, findings: list[dict]):
        """Log a summary of findings at a pipeline stage."""
        count = len(findings)
        severity_counts = {}
        category_counts = {}
        for f in findings:
            sev = f.get("severity", "unknown")
            cat = f.get("category", "unknown")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            category_counts[cat] = category_counts.get(cat, 0) + 1

        msg = f"  [{stage}] {count} findings: severity={severity_counts}, categories={category_counts}"
        self._logger.info(msg)
        print(msg)

    def log_dropped(self, stage: str, original_count: int, kept_count: int):
        """Log how many findings were dropped at a verification stage."""
        dropped = original_count - kept_count
        msg = f"  [{stage}] Dropped {dropped}/{original_count} findings ({kept_count} survived)"
        self._logger.info(msg)
        print(msg)

    # ── Score Logging ─────────────────────────────────────────────────────

    def log_score(self, score: int, breakdown: dict):
        """Log the final risk score with its breakdown."""
        msg = f"  [Score] Safety Score: {score}/100 | breakdown: {json.dumps(breakdown, default=str)}"
        self._logger.info(msg)
        print(msg)

    # ── Error Logging ─────────────────────────────────────────────────────

    def log_error(self, stage: str, error: Exception):
        """Log an error at a specific pipeline stage."""
        msg = f"XX [{stage}] ERROR: {type(error).__name__}: {error}"
        self._logger.error(msg)
        print(msg)

    def log_warning(self, stage: str, message: str):
        """Log a warning at a specific pipeline stage."""
        msg = f"!! [{stage}] {message}"
        self._logger.warning(msg)
        print(msg)

    # ── Pipeline Summary ──────────────────────────────────────────────────

    def pipeline_summary(self, score: int, total_findings: int):
        """Print and log the final pipeline summary."""
        total_elapsed = time.time() - self.start_time
        self.metrics["total_elapsed_seconds"] = round(total_elapsed, 3)
        self.metrics["final_score"] = score
        self.metrics["final_findings"] = total_findings
        self.metrics["steps"] = self.step_times

        separator = "=" * 60
        print(f"\n{separator}")
        print(f"  PIPELINE SUMMARY — {self.contract_name}")
        print(separator)
        print(f"  Final Safety Score : {score}/100")
        print(f"  Final Findings     : {total_findings}")
        print(f"  Total Time         : {total_elapsed:.2f}s")
        print(f"  Steps:")
        for step in self.step_times:
            fc = step['finding_count'] if step['finding_count'] is not None else "-"
            print(f"    - {step['step']:<30} {step['elapsed_seconds']:.2f}s  (findings: {fc})")
        print(separator)

        self._logger.info(json.dumps(self.metrics, default=str))

    def get_metrics(self) -> dict:
        """Return the collected metrics dict."""
        self.metrics["total_elapsed_seconds"] = round(time.time() - self.start_time, 3)
        self.metrics["steps"] = self.step_times
        return self.metrics
