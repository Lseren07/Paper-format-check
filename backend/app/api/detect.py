"""Detection task APIs: start, status, and result."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..parser.errors import DocumentParseError
from ..services.pipeline import run_detection
from ..services.task_store import TaskRecord, store
from . import upload

router = APIRouter(prefix="/detect", tags=["detect"])


class DetectStartRequest(BaseModel):
    task_id: str = Field(min_length=1)


def _task_file(task_id: str):
    return upload.UPLOAD_DIR / f"{task_id}.docx"


def _require_task(task_id: str) -> TaskRecord:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="检测任务不存在")
    return task


@router.post("/start")
def start_detect(payload: DetectStartRequest) -> dict:
    path = _task_file(payload.task_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="检测任务不存在")

    task = store.get(payload.task_id)
    if task is None:
        task = store.put(TaskRecord(task_id=payload.task_id, filename=path.name, size=path.stat().st_size))

    task.status = "detecting"
    task.progress = 50
    # 清除上一次成功检测的缓存，避免本次解析失败时分析接口返回过期文档。
    task.document = None
    task.errors = []
    try:
        task.document, task.errors = run_detection(path, document_id=payload.task_id, source_filename=task.filename)
    except DocumentParseError:
        task.status = "failed"
        task.progress = 100
        task.message = "文档解析失败"
        task.errors = []
        return {"code": 200, "message": "检测失败", "data": {"task_id": payload.task_id, "status": "failed"}}
    finally:
        path.unlink(missing_ok=True)

    task.status = "completed"
    task.progress = 100
    task.message = ""
    return {
        "code": 200,
        "message": "检测任务创建成功",
        "data": {"task_id": payload.task_id, "status": task.status},
    }


@router.get("/status/{task_id}")
def detect_status(task_id: str) -> dict:
    task = _require_task(task_id)
    return {
        "code": 200,
        "message": "success",
        "data": {"task_id": task.task_id, "status": task.status, "progress": task.progress},
    }


@router.get("/result/{task_id}")
def detect_result(task_id: str) -> dict:
    task = _require_task(task_id)
    if task.status == "failed":
        raise HTTPException(status_code=400, detail=task.message or "检测失败")
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="检测尚未完成")
    errors = [error.model_dump() for error in task.errors]
    return {
        "code": 200,
        "message": "success",
        "data": {
            "task_id": task.task_id,
            "filename": task.filename,
            "status": task.status,
            "total_error": len(errors),
            "errors": errors,
        },
    }
