"""过期清理：内存任务、引擎报告、残留上传文件。

采用懒清理（请求入口顺手清一次），不额外起后台线程：本轮 QPS 很低，
省掉一个线程就少一类退出时序问题。契约要求的是「过期能被清掉」，不是「准点清掉」。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from . import report as report_service
from .task_store import store

logger = logging.getLogger(__name__)

DEFAULT_TASK_TTL_SECONDS = 86400
STALE_UPLOAD_SECONDS = 3600
REPORT_SUFFIXES = {".pdf", ".json"}


def task_ttl_seconds() -> int:
    try:
        return int(os.getenv("TASK_TTL_SECONDS", str(DEFAULT_TASK_TTL_SECONDS)))
    except ValueError:
        return DEFAULT_TASK_TTL_SECONDS


def cleanup_expired_tasks(ttl_seconds: int | None = None) -> int:
    return store.cleanup(task_ttl_seconds() if ttl_seconds is None else ttl_seconds)


def cleanup_expired_reports(ttl_seconds: int | None = None) -> int:
    """按文件修改时间清理 `reports/R*`，PDF 和 sidecar 一起删。"""
    ttl = report_service.report_ttl_seconds() if ttl_seconds is None else ttl_seconds
    directory = report_service.REPORT_DIR
    if not directory.is_dir():
        return 0
    now = time.time()
    removed = 0
    for path in directory.iterdir():
        if path.suffix.lower() not in REPORT_SUFFIXES or not path.stem.startswith("R"):
            continue
        try:
            if now - path.stat().st_mtime <= ttl:
                continue
            path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            logger.warning("清理报告文件失败：%s", path, exc_info=True)
    return removed


def cleanup_stale_uploads(upload_dir: Path, max_age_seconds: int = STALE_UPLOAD_SECONDS) -> int:
    """清掉上传后既没检测也没人管的半截文件。"""
    if not upload_dir.is_dir():
        return 0
    now = time.time()
    removed = 0
    for path in upload_dir.glob("*.docx"):
        try:
            if now - path.stat().st_mtime <= max_age_seconds:
                continue
            path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            logger.warning("清理上传文件失败：%s", path, exc_info=True)
    return removed


def run_lazy_cleanup() -> None:
    """请求入口调用；任何清理异常都不能影响主流程。"""
    for step in (cleanup_expired_tasks, cleanup_expired_reports):
        try:
            step()
        except Exception:  # noqa: BLE001 - 清理失败不能拖垮业务请求
            logger.warning("过期清理失败：%s", step.__name__, exc_info=True)
