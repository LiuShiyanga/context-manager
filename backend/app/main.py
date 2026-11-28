"""组装 FastAPI 应用、统一错误响应，并托管无构建步骤的前端页面。"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.routes import router

# 仅从仓库根目录加载本地配置；默认不覆盖调用进程已设置的环境变量。
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)

# 业务 API 先注册，根路径静态挂载负责提供前端资源和 HTML 回退。
app = FastAPI(title="Context Manager Demo")
app.include_router(router)
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[2] / "frontend", html=True), name="frontend")


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    """将显式 HTTP 异常统一包装为前端可消费的 ``error`` 对象。"""

    detail = exc.detail
    # 业务路由已经给出错误码时保留其结构，否则补成通用 HTTP 错误。
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": str(detail)}}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """把 Pydantic 请求校验失败规范化为稳定的 422 API 响应。"""

    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": "Request validation failed.", "details": [{"type": str(error.get("type", "")), "loc": error.get("loc", []), "msg": error.get("msg", "")} for error in exc.errors()]}},
    )


@app.get("/", include_in_schema=False)
def index():
    """返回演示工作台首页，并避免该静态入口出现在 OpenAPI 中。"""

    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "index.html")
