"""导出 FastAPI 应用实例，供 ASGI 服务器直接加载。"""

from backend.app.main import app

__all__ = ["app"]
