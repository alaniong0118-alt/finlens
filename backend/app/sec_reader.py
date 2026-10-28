"""Inactive 02A foundation: static diagnostics only, no research/data imports.

This module is an application boundary, not an activation/deployment mechanism.
An explicit profile/entrypoint pair is required before framework initialization.
"""
import os

# Process admission must precede imports that can read backend-local dotenv.
if os.environ.get("FINLENS_SERVER_PROFILE") != "sec_reader":
    raise ValueError("app.sec_reader requires explicit FINLENS_SERVER_PROFILE=sec_reader.")

from app.config import server_profile

if server_profile().name != "sec_reader":
    raise ValueError("app.sec_reader requires explicit FINLENS_SERVER_PROFILE=sec_reader.")

from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.release_policy import READER_ROUTES, ReleaseAdmissionMiddleware


app = FastAPI(title="FinLens disabled SEC reader", docs_url=None,
              redoc_url=None, openapi_url=None)


@app.get("/healthz")
def healthz():
    """Process diagnostic only; makes no readiness or database claim."""
    return JSONResponse({"status": "ok", "service": "finlens-sec-reader"},
                        headers={"Cache-Control": "no-store"})


@app.get("/capabilities")
def capabilities():
    """No credential inspection, provider probes or data availability claims."""
    return JSONResponse({"research_mode": False, "ai_analysis_configured": False,
                         "ai_analysis_enabled": False, "server_profile": "sec_reader"},
                        headers={"Cache-Control": "no-store"})


app.add_middleware(
    ReleaseAdmissionMiddleware, router=app.router, expected_profile="sec_reader",
    admitted_routes=tuple(route for route in app.router.routes
                          if any((method, getattr(route, "path", None)) in READER_ROUTES
                                 for method in getattr(route, "methods", ()))),
)
