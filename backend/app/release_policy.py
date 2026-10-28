"""Application admission only; trusted Python/OS/database access is not sandboxed."""
from functools import wraps

from app.config import server_profile

RELEASE_MODE_BLOCKED = "RELEASE_MODE_BLOCKED"


class ReleaseModeBlocked(RuntimeError):
    code = RELEASE_MODE_BLOCKED

    def __init__(self):
        super().__init__("This operation is disabled by the SEC-only read-only server profile.")


def require_development() -> None:
    if server_profile().name != "development":
        raise ReleaseModeBlocked()


def development_only(function):
    """Reject even dry runs and injected clients before the function body runs."""
    return _guarded(function, require_development)


def require_encoder() -> None:
    if server_profile().name not in {"development", "sec_readonly"}:
        raise ReleaseModeBlocked()


def encoder_only(function):
    """Guard before cache hits as well as model imports/constructors."""
    return _guarded(function, require_encoder)


def _guarded(function, admission):
    @wraps(function)
    def guarded(*args, **kwargs):
        admission()
        return function(*args, **kwargs)
    # functools.wraps does not copy lru_cache's class-level control methods.
    # Keep the existing development cache API while admission stays outermost.
    for name in ("cache_clear", "cache_info", "cache_parameters"):
        if hasattr(function, name):
            setattr(guarded, name, getattr(function, name))
    return guarded


# Explicit reviewed method/template pairs, never a path-prefix permission.
READONLY_ROUTES = frozenset({
    ("GET", "/healthz"), ("GET", "/dbz"), ("GET", "/capabilities"),
    ("GET", "/companies"),
    ("POST", "/companies/{ticker}/research-answer"),
    ("GET", "/companies/{ticker}/financials/summary"),
    ("GET", "/companies/{ticker}/financials/annual"),
    ("GET", "/companies/{ticker}/financials/insights"),
    ("GET", "/companies/{ticker}/financials/metrics/{metric}"),
    ("GET", "/companies/{ticker}/financial-summary"),
    ("GET", "/companies/{ticker}/financial-snapshot"),
    ("GET", "/companies/{ticker}/financial-history"),
    ("GET", "/companies/{ticker}/sources"),
    ("GET", "/companies/{ticker}/freshness"),
    ("GET", "/companies/{ticker}/context"),
    ("GET", "/companies/{ticker}/filings/{accession_number}/text"),
    ("GET", "/companies/{ticker}/filings/{accession_number}/chunks"),
    ("GET", "/companies/{ticker}/filings/{accession_number}/chunks/{chunk_id}/tone"),
    ("GET", "/companies/{ticker}/filings/{accession_number}/search"),
    ("GET", "/companies/{ticker}/filings/{accession_number}/semantic-search"),
    ("GET", "/companies/{ticker}/filings/{accession_number}/context"),
})


# 02A has no database/research capability, including keyword-only research.
READER_ROUTES = frozenset({("GET", "/healthz"), ("GET", "/capabilities")})


class ReleaseAdmissionMiddleware:
    """Outermost admission, before CORS, routing redirects or dependencies.

    Capture the reviewed route objects at app construction. A newly registered
    alias/replacement cannot inherit permission from an admitted path.
    """
    def __init__(self, app, router, admitted_routes, expected_profile=None):
        self.app = app
        self.router = router
        self.admitted_routes = admitted_routes
        self.expected_profile = expected_profile

    async def __call__(self, scope, receive, send):
        profile = server_profile().name
        consistent = (profile in {"development", "sec_readonly", "sec_reader"}
                      and (self.expected_profile is None or profile == self.expected_profile))
        if scope["type"] == "lifespan":
            if not consistent:
                raise ReleaseModeBlocked()
            return await self.app(scope, receive, send)
        if consistent and profile == "development":
            return await self.app(scope, receive, send)
        allowed = (READONLY_ROUTES if profile == "sec_readonly" else
                   READER_ROUTES if profile == "sec_reader" and self.expected_profile == "sec_reader"
                   else frozenset())
        if scope["type"] == "http":
            from starlette.routing import Match
            for route in self.router.routes:
                match, _ = route.matches(scope)
                if match == Match.FULL:
                    if (consistent
                            and any(route is admitted for admitted in self.admitted_routes)
                            and (scope["method"], route.path) in allowed
                            and (profile != "sec_reader" or (
                                scope["path"] == route.path
                                and scope.get("raw_path", b"") == route.path.encode("ascii")
                                and not scope.get("root_path", "")))):
                        return await self.app(scope, receive, send)
                    break
            from starlette.responses import JSONResponse
            response = JSONResponse(
                {"detail": "This operation is disabled by the SEC-only read-only server profile."},
                status_code=403,
                headers={"X-FinLens-Error-Code": RELEASE_MODE_BLOCKED, "Cache-Control": "no-store"},
            )
            return await response(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        raise ReleaseModeBlocked()
