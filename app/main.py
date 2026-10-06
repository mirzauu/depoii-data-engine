import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.core.logging import logger, correlation_id_ctx
from app.api.v1.health import router as health_router


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID", f"req-{uuid.uuid4().hex[:8]}")
        token = correlation_id_ctx.set(corr_id)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = corr_id
            return response
        finally:
            correlation_id_ctx.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION} on {settings.HOST}:{settings.PORT}")
    yield
    logger.info("Shutting down Depoii Data Engine.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Autonomous Data Science, Normalization & Extraction Engine for Depoii Commercial Roofing Intelligence",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Correlation ID Middleware
app.add_middleware(CorrelationIdMiddleware)

# CORS Policy for Depoii Next.js frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4417",
        "http://127.0.0.1:4417",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(health_router)  # Also expose /health at root for Docker/K8s probes


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": "/health",
    }
