from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.routes import router

app = FastAPI(title="Context Manager Demo")
app.include_router(router)
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[2] / "frontend", html=True), name="frontend")


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": str(detail)}}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": "Request validation failed.", "details": exc.errors()}},
    )


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "index.html")
