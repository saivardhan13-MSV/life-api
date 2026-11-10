"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from life_api import __version__
from life_api.api.deps import require_api_key
from life_api.api.routers import applications, days, public
from life_api.config import get_settings

log = logging.getLogger("life_api.access")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Life API",
        version=__version__,
        description="Sleep, fitness, screen time and job applications for one person.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    @app.middleware("http")
    async def access_log(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        start = time.perf_counter()
        response = await call_next(request)
        log.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        response.headers["x-request-id"] = request_id
        return response

    private = [Depends(require_api_key)]
    app.include_router(public.router)
    app.include_router(applications.router, dependencies=private)
    app.include_router(days.router, dependencies=private)
    return app
