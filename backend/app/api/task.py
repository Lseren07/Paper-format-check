"""Task deletion endpoint."""

from fastapi import APIRouter, HTTPException
import re

from ..services.report import report_id_for, report_path
from ..services.task_store import store
from . import upload

router = APIRouter(prefix="/task", tags=["task"])


@router.delete("/{task_id}")
def delete_task(task_id: str) -> dict:
    if not re.fullmatch(r"T[A-Za-z0-9_-]+", task_id):
        raise HTTPException(status_code=404, detail="检测任务不存在")
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="检测任务不存在")
    upload_path = upload.UPLOAD_DIR / f"{task_id}.docx"
    report_path(report_id_for(task_id)).unlink(missing_ok=True)
    upload_path.unlink(missing_ok=True)
    store.delete(task_id)
    return {"code": 200, "message": "检测任务已删除", "data": {"task_id": task_id}}
