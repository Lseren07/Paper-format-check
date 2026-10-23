"""项目案例相关接口"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models.contracts import ProjectCase
from ..services.case_store import get_case_store

router = APIRouter(prefix="/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    """创建案例请求"""
    title: str
    description: str
    school: str
    file_count: int
    error_rate: float
    thumbnail_url: str | None = None
    tags: list[str] | None = None


class UpdateCaseRequest(BaseModel):
    """更新案例请求"""
    title: str | None = None
    description: str | None = None
    school: str | None = None
    file_count: int | None = None
    error_rate: float | None = None
    thumbnail_url: str | None = None
    tags: list[str] | None = None


@router.get("")
async def list_cases() -> dict[str, list[ProjectCase]]:
    """获取所有案例列表"""
    store = get_case_store()
    cases = store.list_all()
    return {"data": cases}


@router.get("/{case_id}")
async def get_case(case_id: str) -> dict[str, ProjectCase]:
    """获取单个案例详情"""
    store = get_case_store()
    case = store.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return {"data": case}


@router.post("")
async def create_case(request: CreateCaseRequest) -> dict[str, ProjectCase]:
    """创建新案例"""
    store = get_case_store()
    case_id = store.generate_case_id()

    from datetime import datetime
    created_at = datetime.now().isoformat()

    case = ProjectCase(
        case_id=case_id,
        title=request.title,
        description=request.description,
        school=request.school,
        file_count=request.file_count,
        error_rate=request.error_rate,
        created_at=created_at,
        thumbnail_url=request.thumbnail_url,
        tags=request.tags or [],
    )

    created_case = store.create(case)
    return {"data": created_case}


@router.put("/{case_id}")
async def update_case(case_id: str, request: UpdateCaseRequest) -> dict[str, ProjectCase]:
    """更新案例信息"""
    store = get_case_store()

    # 过滤掉 None 值
    updates = {k: v for k, v in request.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(status_code=400, detail="没有提供更新内容")

    updated_case = store.update(case_id, updates)
    if not updated_case:
        raise HTTPException(status_code=404, detail="案例不存在")

    return {"data": updated_case}


@router.delete("/{case_id}")
async def delete_case(case_id: str) -> dict[str, str]:
    """删除案例"""
    store = get_case_store()
    success = store.delete(case_id)
    if not success:
        raise HTTPException(status_code=404, detail="案例不存在")
    return {"message": "案例已删除"}
