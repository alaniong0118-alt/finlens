"""Opt-in development HTTP route. Release policy allowlists stay unchanged."""
import os
from threading import BoundedSemaphore, Lock

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response

from app.config import server_profile
from app.hypothetical_risk import MAX_REQUEST_BYTES, parse_body, response_bytes
from app.portfolio_risk import PortfolioRiskError

router = APIRouter()
_slot = BoundedSemaphore(1)


def failure(status, reason):
    return JSONResponse({"detail": reason}, status_code=status,
                        headers={"Cache-Control": "no-store", "X-FinLens-Error-Code": "HYPOTHETICAL_RISK_REJECTED"})


class _SlotOwner:
    """One acquired slot, handed from the waiting request to actual worker entry.

    Cleanup and worker entry race under the same lock. If cleanup wins, a late
    callback skips work. If entry wins, only that worker may release the slot.
    Cleanup is synchronous/idempotent, including under repeated cancellation.
    """
    def __init__(self, slot):
        self._lock = Lock()
        self._slot = slot
        self._state = "queued" if slot.acquire(blocking=False) else "busy"

    @property
    def acquired(self):
        return self._state != "busy"

    def release_if_queued(self):
        with self._lock:
            if self._state == "queued":
                self._state = "released"
                self._slot.release()

    def compute(self, value):
        with self._lock:
            if self._state != "queued":
                return None  # Request cleanup revoked this late callback.
            self._state = "running"
        try:
            return response_bytes(value)
        finally:
            with self._lock:
                self._state = "released"
                self._slot.release()


@router.post("/hypothetical-risk", include_in_schema=False)
async def hypothetical_risk(request: Request):
    if server_profile().name != "development":
        return failure(403, "development_only")
    if os.environ.get("FINLENS_HYPOTHETICAL_RISK") != "1":
        return failure(404, "candidate_disabled")
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        return failure(415, "application_json_required")
    if request.headers.get("content-encoding", "identity") != "identity":
        return failure(415, "content_encoding_unsupported")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
            return failure(413, "request_resource_limit")
        body.extend(chunk)
    try:
        value = parse_body(bytes(body))
        if await request.is_disconnected():
            return failure(409, "request_cancelled")
        owner = _SlotOwner(_slot)
        if not owner.acquired:
            return failure(429, "candidate_busy_retry_explicitly")
        try:
            payload = await run_in_threadpool(owner.compute, value)
        finally:
            # Covers cancellation while awaiting capacity and dispatch failures;
            # running workers retain ownership until their own finally executes.
            owner.release_if_queued()
        if payload is None:
            raise RuntimeError("Calculation worker did not acquire its slot.")
        return Response(payload, media_type="application/json", headers={"Cache-Control": "no-store"})
    except PortfolioRiskError as exc:
        return failure(422, str(exc))
