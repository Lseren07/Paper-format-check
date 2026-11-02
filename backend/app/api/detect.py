"""Detection task APIs: start, status, and result."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..parser.errors import DocumentParseError
from ..rules.registry import RuleSetNotFoundError, resolve_rule_set
from ..services.cleanup import run_lazy_cleanup
from ..services.pipeline import run_detection
from ..services.rule_summary import summarize_rule_source
from ..services.task_store import TaskRecord, store
from . import upload

router = APIRouter(prefix="/detect", tags=["detect"])

# 解析失败时统一追加的可操作提示；异常自带的 message 已经不含路径与文档内容。
PARSE_FAILURE_HINT = "请确认文件未加密且为有效的 .docx 文件"


class DetectStartRequest(BaseModel):
    task_id: str = Field(min_length=1)
    rule_set_id: str | None = None


def _task_file(task_id: str):
    return upload.UPLOAD_DIR / f"{task_id}.docx"


def _require_task(task_id: str) -> TaskRecord:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="检测任务不存在")
    return task


def _parse_failure_message(error: DocumentParseError) -> str:
    detail = (getattr(error, "message", "") or "").strip()
    if not detail:
        return f"文档解析失败，{PARSE_FAILURE_HINT}"
    return f"{detail}，{PARSE_FAILURE_HINT}"


def _rule_source_payload(rules) -> dict | None:
    """把规则来源摘要映射成契约里的 snake_case 结构；无来源时返回 None。"""
    summary = summarize_rule_source(rules)
    if not summary["available"]:
        return None
    return {
        "title": summary["title"],
        "document": summary["document"],
        "organization": summary["organization"],
        "scope": summary["scope"],
        "clause_count": len(summary["clauses"]),
    }


def _stats_payload(task: TaskRecord) -> tuple[str | None, dict, dict | None]:
    """统计口径见契约第 9 节：规则总数取启用项，涉及规则数按 rule_id 去重。"""
    issue_rule_count = len({error.rule_id for error in task.errors if error.rule_id})
    stats = {
        "rule_count": 0,
        "issue_rule_count": issue_rule_count,
        "error_count": len(task.errors),
    }
    try:
        resolved = resolve_rule_set(task.rule_set_id)
    except RuleSetNotFoundError:
        # 规则集被删/改坏时结果仍可取，只是规则总数与来源缺失，不伪造。
        return None, stats, None
    stats["rule_count"] = sum(1 for check in resolved.rules.checks if check.enabled)
    return resolved.info.name, stats, _rule_source_payload(resolved.rules)


@router.post("/start")
def start_detect(payload: DetectStartRequest) -> dict:
    run_lazy_cleanup()
    path = _task_file(payload.task_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="检测任务不存在")

    task = store.get(payload.task_id)
    if task is None:
        task = store.put(TaskRecord(task_id=payload.task_id, filename=path.name, size=path.stat().st_size))

    try:
        resolved = resolve_rule_set(payload.rule_set_id)
    except RuleSetNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    task.status = "detecting"
    task.progress = 50
    task.rule_set_id = resolved.info.id
    # 清除上一次成功检测的缓存，避免本次解析失败时分析接口返回过期文档。
    task.document = None
    task.errors = []
    try:
        task.document, task.errors = run_detection(path, document_id=payload.task_id, source_filename=task.filename, rule_set=resolved.rules)
    except DocumentParseError as error:
        task.status = "failed"
        task.progress = 100
        task.message = _parse_failure_message(error)
        task.errors = []
        return {
            "code": 200,
            "message": "检测失败",
            "data": {"task_id": payload.task_id, "status": "failed", "message": task.message},
        }
    finally:
        path.unlink(missing_ok=True)

    task.status = "completed"
    task.progress = 100
    task.message = ""
    return {
        "code": 200,
        "message": "检测任务创建成功",
        "data": {
            "task_id": payload.task_id,
            "status": task.status,
            "rule_set_id": task.rule_set_id,
            "rule_set_name": resolved.info.name,
        },
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
    run_lazy_cleanup()
    task = _require_task(task_id)
    if task.status == "failed":
        raise HTTPException(status_code=400, detail=task.message or "检测失败")
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="检测尚未完成")
    errors = [error.model_dump() for error in task.errors]
    rule_set_name, stats, rule_source = _stats_payload(task)
    return {
        "code": 200,
        "message": "success",
        "data": {
            "task_id": task.task_id,
            "filename": task.filename,
            "status": task.status,
            "rule_set_id": task.rule_set_id,
            "rule_set_name": rule_set_name,
            "total_error": len(errors),
            "stats": stats,
            "rule_source": rule_source,
            "errors": errors,
        },
    }
