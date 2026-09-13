"""Parsed document analysis endpoint."""

from fastapi import APIRouter, HTTPException

from ..services.task_store import store

router = APIRouter(prefix="/document", tags=["analysis"])


@router.get("/analysis/{task_id}")
def document_analysis(task_id: str) -> dict:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="检测任务不存在")
    if task.status == "failed":
        raise HTTPException(status_code=400, detail=task.message or "检测失败")
    if task.status != "completed" or task.document is None:
        raise HTTPException(status_code=409, detail="检测尚未完成")
    return {
        "code": 200,
        "message": "success",
        "data": {
            "task_id": task.task_id,
            "filename": task.filename,
            "status": task.status,
            "document": task.document.model_dump(),
        },
    }
