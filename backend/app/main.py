"""FastAPI 应用入口：注册路由、统一鉴权、启动自检。

鉴权写成依赖而不是全局中间件（见 `security.py`），健康检查单独豁免，
这样测试可以用 `app.dependency_overrides` 精确控制 401 分支。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .api import upload as upload_api
from .api.analysis import router as analysis_router
from .api.cases import router as cases_router
from .api.detect import router as detect_router
from .api.health import router as health_router
from .api.report import router as report_router
from .api.rules import router as rules_router
from .api.task import router as task_router
from .api.upload import router as upload_router
from .rules.registry import rules_dir
from .security import KEY_ENV, require_engine_key
from .services import report as report_service
from .services.cleanup import cleanup_stale_uploads
from .version import SERVICE_VERSION

logger = logging.getLogger(__name__)


def validate_startup_config() -> None:
    """启动自检：缺密钥、缺规则目录时直接拒绝启动；字体缺失只告警。

    字体只影响 PDF 报告，不影响检测，所以不阻止启动（契约 §7.13 第 6 条）。
    """
    if not os.environ.get(KEY_ENV, "").strip():
        raise RuntimeError(f"未设置 {KEY_ENV}，检测引擎拒绝启动（必须与 Flask 侧一致）")

    directory = rules_dir()
    if not directory.is_dir():
        raise RuntimeError(f"规则目录不存在：{directory}")

    upload_api.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    report_service.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        report_service.report_font_path()
    except RuntimeError as error:
        logger.warning("%s；检测可用，但 PDF 报告会生成失败", error)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_startup_config()
    # 上次进程异常退出时可能留下没检测也没人管的 docx，启动顺手清掉。
    cleanup_stale_uploads(upload_api.UPLOAD_DIR)
    yield


app = FastAPI(
    title="Paper Checker API",
    version=SERVICE_VERSION,
    docs_url="/docs",
    lifespan=lifespan,
)

# 健康检查单独注册且不加鉴权，其余接口统一要求 X-Format-Key。
app.include_router(health_router, prefix="/api/v1")

_engine_auth = [Depends(require_engine_key)]

app.include_router(upload_router, prefix="/api/v1", dependencies=_engine_auth)
app.include_router(detect_router, prefix="/api/v1", dependencies=_engine_auth)
app.include_router(report_router, prefix="/api/v1", dependencies=_engine_auth)
app.include_router(analysis_router, prefix="/api/v1", dependencies=_engine_auth)
app.include_router(task_router, prefix="/api/v1", dependencies=_engine_auth)
app.include_router(rules_router, prefix="/api/v1", dependencies=_engine_auth)
app.include_router(cases_router, prefix="/api/v1", dependencies=_engine_auth)
