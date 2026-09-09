"""文件上传接口：接收 .docx 论文文件，校验后保存到 uploads/，返回 task_id。"""
import os
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

# 每个 router 是"一组"接口。prefix 先拼 /upload，main.py 再统一拼版本号 /api/v1
router = APIRouter(prefix="/paper/upload", tags=["upload"])

# ---- 可调参数：先写成常量，后续再统一挪到配置文件里 ----
ALLOWED_SUFFIX = {".docx"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))  # 默认50MB，可被环境变量覆盖
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))       # 保存目录
READ_CHUNK = 1024 * 1024                            # 每次读 1MB，避免整个文件占满内存


@router.post("")
async def upload_paper(file: UploadFile = File(...)) -> dict:
    """接收老师上传的论文文件。校验通过后保存，返回任务编号。"""

    # 校验1：扩展名必须在白名单里（Path(file.filename).suffix 取出".docx"这种尾巴）
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持 .docx 文件，收到的是: {suffix or '未知'}",
        )

    # 任务ID：uuid 保证全局唯一。取前12位十六进制，短一些更友好（如 T3f9a21c8d4e2）
    task_id = "T" + uuid.uuid4().hex[:12]
    # 目标路径：uploads/{task_id}.docx。用任务ID命名，不用原始文件名——
    # 这样两个学生都传"论文.docx"也不会互相覆盖。
    target = UPLOAD_DIR / f"{task_id}{suffix}"
    UPLOAD_DIR.mkdir(exist_ok=True)  # 目录不存在就创建（幂等，存在也不报错）

    # 边读边写边计数：不把整个文件一次性读进内存（大文件会撑爆RAM）
    # "while chunk := await file.read(READ_CHUNK)" —— := 叫"海象运算符"，
    # 它先赋值给chunk，再把值当条件判断；读到末尾返回空b""时循环结束。
    size = 0
    too_big = False
    with target.open("wb") as out:
        while chunk := await file.read(READ_CHUNK):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                too_big = True
                break          # 先跳出，让 with 自动关闭文件句柄
            out.write(chunk)

    # 超限：删掉已写了一半的残留文件，返回 413
    if too_big:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=413,
            detail=f"文件超过 {MAX_UPLOAD_MB}MB 大小限制",
        )

    try:
        with zipfile.ZipFile(target) as archive:
            if "word/document.xml" not in archive.namelist():
                raise zipfile.BadZipFile("Missing Word document XML")
    except (OSError, zipfile.BadZipFile):
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"文件不是有效的 {suffix} 文档")

    return {
        "code": 200,
        "message": "upload succeeded",
        "data": {
        "task_id": task_id,
        "filename": file.filename,   # 把原始文件名记下来（只用于展示，不用于存盘）
        "size": size,
        "status": "uploaded",
        },
    }
