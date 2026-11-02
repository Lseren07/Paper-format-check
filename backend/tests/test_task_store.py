"""任务与报告的过期清理：过期要被清掉，未过期不能被误删。"""

import os
import time
from pathlib import Path

from backend.app.services import report as report_service
from backend.app.services.cleanup import (
    cleanup_expired_reports,
    cleanup_expired_tasks,
    cleanup_stale_uploads,
    task_ttl_seconds,
)
from backend.app.services.task_store import TaskRecord, TaskStore, store


def _age(path: Path, seconds: int) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def test_task_store_cleanup_drops_only_expired() -> None:
    local = TaskStore()
    old = local.put(TaskRecord(task_id="Told00000000", filename="old.docx"))
    fresh = local.put(TaskRecord(task_id="Tnew00000000", filename="new.docx"))
    old.created_at = time.time() - 7200

    removed = local.cleanup(3600)

    assert removed == 1
    assert local.get(old.task_id) is None
    assert local.get(fresh.task_id) is fresh
    assert len(local) == 1


def test_cleanup_expired_tasks_uses_env_ttl(monkeypatch) -> None:
    monkeypatch.setenv("TASK_TTL_SECONDS", "0")
    assert task_ttl_seconds() == 0
    task = store.put(TaskRecord(task_id="Tttl00000000", filename="t.docx"))
    # Windows 的 time.time() 精度较粗，靠 TTL=0 撞边界不稳，直接把创建时间放到过去。
    task.created_at = time.time() - 1
    try:
        assert cleanup_expired_tasks() >= 1
        assert store.get(task.task_id) is None
    finally:
        store.delete(task.task_id)


def test_task_ttl_falls_back_on_invalid_env(monkeypatch) -> None:
    monkeypatch.setenv("TASK_TTL_SECONDS", "not-a-number")
    assert task_ttl_seconds() == 86400


def test_cleanup_expired_reports_removes_pdf_and_sidecar(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_service, "REPORT_DIR", tmp_path)
    old_pdf = tmp_path / "RTold00000001.pdf"
    old_json = tmp_path / "RTold00000001.json"
    new_pdf = tmp_path / "RTnew00000001.pdf"
    unrelated = tmp_path / "notes.txt"
    for path in (old_pdf, old_json, new_pdf, unrelated):
        path.write_text("x", encoding="utf-8")
    _age(old_pdf, 4 * 86400)
    _age(old_json, 4 * 86400)

    removed = cleanup_expired_reports(3 * 86400)

    assert removed == 2
    assert not old_pdf.exists()
    assert not old_json.exists()
    assert new_pdf.exists()
    assert unrelated.exists()


def test_cleanup_reports_ignores_non_report_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_service, "REPORT_DIR", tmp_path / "missing")
    assert cleanup_expired_reports(0) == 0


def test_cleanup_stale_uploads_removes_abandoned_docx(tmp_path) -> None:
    stale = tmp_path / "Tabandoned00.docx"
    fresh = tmp_path / "Tfresh000000.docx"
    other = tmp_path / "keep.pdf"
    for path in (stale, fresh, other):
        path.write_bytes(b"x")
    _age(stale, 2 * 3600)

    removed = cleanup_stale_uploads(tmp_path, max_age_seconds=3600)

    assert removed == 1
    assert not stale.exists()
    assert fresh.exists()
    assert other.exists()
