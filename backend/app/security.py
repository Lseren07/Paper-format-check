"""引擎内部鉴权：Flask 与引擎共用同一个 `FORMAT_ENGINE_KEY`。

浏览器不直连引擎（契约 §2），所以这里只做「是不是 Flask 在调用」这一件事，
不涉及用户身份。密钥只从环境变量读取，不进日志、不返回给调用方。
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException

KEY_ENV = "FORMAT_ENGINE_KEY"
HEADER_NAME = "X-Format-Key"
INVALID_KEY_DETAIL = "无效的服务密钥"


def engine_key() -> str:
    """当前进程配置的服务密钥；为空表示没配置。"""
    return os.environ.get(KEY_ENV, "")


def require_engine_key(x_format_key: str = Header(default="", alias=HEADER_NAME)) -> None:
    """FastAPI 依赖：校验 `X-Format-Key`。

    写成依赖而不是中间件，测试里可以用 `app.dependency_overrides` 精确绕过，
    也能单独测试 401 分支。
    """
    expected = engine_key()
    # 没配置密钥时一律拒绝，避免漏配后变成无鉴权的裸服务。
    if not expected or not hmac.compare_digest(x_format_key, expected):
        raise HTTPException(status_code=401, detail=INVALID_KEY_DETAIL)
