"""健康检查：唯一不需要 `X-Format-Key` 的接口（契约 §7.2）。

Flask 用它判断引擎是否可达，返回体必须稳定，不能依赖规则集或字体等
可能缺失的资源。
"""

from fastapi import APIRouter

from ..version import CONTRACT_VERSION, SERVICE_NAME, SERVICE_VERSION

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "contract_version": CONTRACT_VERSION,
    }
