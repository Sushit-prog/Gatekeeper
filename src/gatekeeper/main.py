import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gatekeeper.api.routes import router, set_registry
from gatekeeper.audit.db import init_db
from gatekeeper.config import settings
from gatekeeper.rules.registry import RuleRegistry


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await init_db()
    registry = RuleRegistry(settings.policy_path)
    set_registry(registry)
    yield


app = FastAPI(title="GateKeeper", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return BLOCK for malformed requests instead of 422."""
    return JSONResponse(
        status_code=200,
        content={
            "decision": "BLOCK",
            "matched_rules": [],
            "latency_ms": 0.0,
            "audit_id": "",
            "reason": "malformed_args",
        },
    )
