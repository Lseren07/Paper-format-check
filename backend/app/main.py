from fastapi import FastAPI

from .api.detect import router as detect_router
from .api.upload import router as upload_router


app = FastAPI(
    title="Paper Checker API",
    version="0.1.0",
    docs_url="/docs",
)

# 挂载上传路由：给整组接口统一加上 /api/v1 版本前缀
app.include_router(upload_router, prefix="/api/v1")
app.include_router(detect_router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "paper-checker-backend"}
