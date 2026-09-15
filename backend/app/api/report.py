"""PDF report creation and download endpoints."""

from pathlib import Path
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..rules.registry import RuleSetNotFoundError, resolve_rule_set
from ..services.report import build_report, report_id_for, report_path
from ..services.rule_summary import summarize_rule_source
from ..services.task_store import TaskRecord, store
from . import upload

router = APIRouter(prefix="/report", tags=["report"])


class ReportCreateRequest(BaseModel):
    task_id: str = Field(min_length=1)


def _require_task(task_id: str) -> TaskRecord:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="检测任务不存在")
    return task


@router.post("/create")
def create_report(payload: ReportCreateRequest) -> dict:
    task = _require_task(payload.task_id)
    if task.status == "failed":
        raise HTTPException(status_code=400, detail="检测失败，无法生成报告")
    if task.status != "completed":
        raise HTTPException(status_code=409, detail="检测尚未完成")
    try:
        # 报告必须复述检测时真正用过的那套规则，而不是当前默认规则。
        resolved = resolve_rule_set(task.rule_set_id)
        rules = resolved.rules
        build_report(task, rules=rules, rule_file=resolved.info.file)
    except (OSError, RuntimeError, ValueError, RuleSetNotFoundError) as error:
        raise HTTPException(status_code=500, detail="检测报告生成失败") from error
    upload_path = upload.UPLOAD_DIR / f"{task.task_id}.docx"
    upload_path.unlink(missing_ok=True)
    report_id = report_id_for(task.task_id)
    summary = summarize_rule_source(rules)
    return {"code": 200, "message": "报告生成成功", "data": {
        "report_id": report_id,
        "task_id": task.task_id,
        "filename": f"{Path(task.filename).stem}_格式检测报告.pdf",
        "total_error": len(task.errors),
        "download_url": f"/api/v1/report/download/{report_id}",
        "rule_set_id": resolved.info.id,
        "rule_file": resolved.info.file,
        "rule_source": {
            "available": summary["available"],
            "title": summary["title"],
            "document": summary["document"],
            "organization": summary["organization"],
            "scope": summary["scope"],
            "clause_count": len(summary["clauses"]),
            "automated_clause_count": summary["automated_clause_count"],
            "manual_clause_count": summary["manual_clause_count"],
            "check_count": summary["check_count"],
        },
    }}


@router.get("/download/{report_id}")
def download_report(report_id: str) -> FileResponse:
    if not re.fullmatch(r"RT[A-Za-z0-9_-]+", report_id):
        raise HTTPException(status_code=404, detail="检测报告不存在")
    task_id = report_id.removeprefix("R")
    path = report_path(report_id)
    task = _require_task(task_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="检测报告不存在")
    return FileResponse(path, media_type="application/pdf", filename=f"{Path(task.filename).stem}_格式检测报告.pdf")
