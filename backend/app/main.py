import os
from typing import Annotated

from app.config import server_profile
from app.release_policy import READONLY_ROUTES, ReleaseAdmissionMiddleware

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, Field
from sqlalchemy import func, select, text
from app.sec_client import (
    build_filing_url,
    build_filing_raw_url,
)
from app.database import HttpSessionLocal, database_failure
from app.embedding_service import EncoderDependencyError
from app.financial_analysis import (
    get_financial_history,
    get_financial_snapshot,
    get_financial_summary,
)
from app.filing_search_service import (
    search_filing_chunks,
    search_filing_chunks_semantic,
)
from app.rag_context_service import build_filing_context, build_company_context
from app.answer_service import (
    AnswerConfigurationError,
    AnswerGenerationError,
    AnswerTimeoutError,
    MalformedModelOutputError,
    answer_filing_question,
)
from app.models import Company, FinancialFact, FilingChunk
from app.financial_metrics_service import load_financial_metrics, UnknownCompany, UnknownMetric
from app.financial_metric_schemas import AnnualFinancialComparison, NormalizedFinancialSummary, NormalizedMetricHistory, PeriodKind
from app.research_answer_service import ResearchAnswer, ResearchAnswerRequest, answer_research_question
from app.freshness_service import (
    freshness, read_session, request_scope, require_published, schema_ready,
    research_chunks, stored_research_text, validate_chunks, validate_research_input,
    inconsistent_evidence,
)
from app.refresh_contracts import Freshness
from app.filing_tone_service import (
    FilingToneResponse, resolve_published_passage, score_published_passage, validate_tone_request,
)
from app.models import FilingPublication
from app.schemas import (
    CompanyResponse,
    FinancialSourceResponse,
    FinancialHistoryResponse,
    FinancialSnapshotResponse,
    FinancialSummaryResponse,
    FilingAnswerResponse,
)

class HealthResponse(BaseModel):
    status: str
    service: str


class DatabaseHealthResponse(BaseModel):
    status: str
    database: str


class CapabilityResponse(BaseModel):
    research_mode: bool
    ai_analysis_configured: bool
    ai_analysis_enabled: bool
    server_profile: str


class FilingAnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=50, strict=True)


def _http_result_count(value):
    # Query parameters arrive as strings. Reject decimal/exponent spellings
    # before Pydantic's permissive integer coercion (e.g. "1.0").
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise ValueError("limit must be an integer between 1 and 50")
    return value


ResearchQuery = Annotated[str, Query(min_length=1, max_length=2000)]
ResearchLimit = Annotated[int, BeforeValidator(_http_result_count), Query(ge=1, le=50)]


class VersionedRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handle(request):
            ticker = request.path_params.get("ticker")
            scope = {"ticker": ticker.upper() if ticker else None,
                     "expected": request.headers.get("X-FinLens-Data-Version"), "version": None}
            token = request_scope.set(scope)
            try:
                try:
                    response = await original(request)
                except StarletteHTTPException as exc:
                    response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                            headers=exc.headers)
                except RequestValidationError as exc:
                    response = await request_validation_exception_handler(request, exc)
                except Exception as exc:
                    failure = database_failure(exc)
                    if isinstance(exc, EncoderDependencyError):
                        failure = (503, "RETRIEVAL_UNAVAILABLE",
                                   "Filing evidence search is unavailable. Try again later.")
                    if failure:
                        status, code, message = failure
                        response = JSONResponse({"detail": message}, status_code=status,
                                                headers={"X-FinLens-Error-Code": code})
                    else:
                        response = JSONResponse({"detail": "Internal server error."}, status_code=500)
                if ticker and scope["version"] is not None:
                    response.headers["X-FinLens-Data-Version"] = str(scope["version"])
                response.headers["Cache-Control"] = "no-store"
                return response
            finally:
                request_scope.reset(token)
        return handle


app = FastAPI(
    title="FinLens API",
    version="0.1.0",
    description=(
        "Local development foundation for the "
        "FinLens financial research platform."
    ),
)
app.router.route_class = VersionedRoute

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get(
    "/healthz",
    response_model=HealthResponse,
)
def healthz() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="finlens-api",
    )


@app.get("/capabilities", response_model=CapabilityResponse)
def capabilities() -> CapabilityResponse:
    """Configuration only; does not probe a provider or disclose credentials."""
    return CapabilityResponse(
        research_mode=True,
        ai_analysis_configured=server_profile().generation_allowed and bool(os.getenv("OPENAI_API_KEY", "").strip()),
        ai_analysis_enabled=server_profile().generation_allowed and bool(os.getenv("OPENAI_API_KEY", "").strip()),
        server_profile=server_profile().name,
    )


@app.get(
    "/dbz",
    response_model=DatabaseHealthResponse,
)
def database_health() -> DatabaseHealthResponse:
    with read_session(HttpSessionLocal) as session:
        session.execute(text("SELECT 1"))

    return DatabaseHealthResponse(
        status="ok",
        database="postgresql",
    )


@app.get(
    "/companies",
    response_model=list[CompanyResponse],
)
def get_companies() -> list[CompanyResponse]:
    with read_session(HttpSessionLocal) as session:
        if schema_ready(session.connection()):
            indexed_filings = select(FilingPublication.company_cik.label("company_cik"),
                func.count().label("indexed_filing_count")).group_by(FilingPublication.company_cik).subquery()
        else:
            # Transitional, read-only deployment before authorized migration:
            # two bulk reads validate completeness, never any-vector readiness.
            companies = list(session.scalars(select(Company).order_by(Company.ticker)))
            groups, counts = {}, {}
            for chunk in research_chunks(session):
                groups.setdefault((chunk.company_cik, chunk.accession_number), []).append(chunk)
            for (cik, accession), chunks in groups.items():
                try:
                    validate_chunks(chunks)
                    counts[cik] = counts.get(cik, 0) + 1
                except ValueError:
                    pass
            return [CompanyResponse(id=c.id, ticker=c.ticker, name=c.name, cik=c.cik, exchange=c.exchange,
                has_indexed_filing=counts.get(c.cik, 0) > 0, indexed_filing_count=counts.get(c.cik, 0)) for c in companies]
        rows = session.execute(
            select(
                Company,
                func.coalesce(indexed_filings.c.indexed_filing_count, 0),
            )
            .outerjoin(indexed_filings, Company.cik == indexed_filings.c.company_cik)
            .order_by(Company.ticker)
        ).all()
        return [
            CompanyResponse(
                id=company.id,
                ticker=company.ticker,
                name=company.name,
                cik=company.cik,
                exchange=company.exchange,
                has_indexed_filing=count > 0,
                indexed_filing_count=count,
            )
            for company, count in rows
        ]


@app.post("/companies/{ticker}/research-answer", response_model=ResearchAnswer)
def deterministic_research_answer(ticker: str, request: ResearchAnswerRequest):
    validate_research_input(request.question)
    with read_session(HttpSessionLocal) as session:
        try:
            return answer_research_question(session, ticker, request.question)
        except UnknownCompany:
            raise HTTPException(404, detail={"code": "unknown_company", "ticker": ticker.upper()})


@app.get("/companies/{ticker}/financials/summary", response_model=NormalizedFinancialSummary)
def normalized_financial_summary(ticker: str, period: PeriodKind = "quarter"):
    with read_session(HttpSessionLocal) as session:
        try:
            return load_financial_metrics(session, ticker).summary(period)
        except UnknownCompany:
            raise HTTPException(404, detail={"code": "unknown_company", "ticker": ticker.upper()})


@app.get("/companies/{ticker}/financials/annual", response_model=AnnualFinancialComparison)
def annual_financial_comparison(ticker: str, fiscal_year: int | None = Query(default=None, ge=1900, le=2099)):
    with read_session(HttpSessionLocal) as session:
        try:
            model = load_financial_metrics(session, ticker)
            if model.company.ticker != ticker.upper():
                raise HTTPException(409, detail="Financial company identity could not be verified.")
            return model.annual_comparison(fiscal_year)
        except UnknownCompany:
            raise HTTPException(404, detail={"code": "unknown_company", "ticker": ticker.upper()})


@app.get("/companies/{ticker}/financials/metrics/{metric}", response_model=NormalizedMetricHistory)
def normalized_metric_history(ticker: str, metric: str, period: PeriodKind = "quarter",
                              limit: int = Query(default=40, ge=1, le=200)):
    with read_session(HttpSessionLocal) as session:
        try:
            return load_financial_metrics(session, ticker).history(metric, period, limit)
        except UnknownCompany:
            raise HTTPException(404, detail={"code": "unknown_company", "ticker": ticker.upper()})
        except UnknownMetric:
            raise HTTPException(404, detail={"code": "unknown_metric", "metric": metric})


@app.get(
    "/companies/{ticker}/financial-summary",
    response_model=FinancialSummaryResponse,
)
def get_financial_summary_by_ticker(
    ticker: str,
) -> FinancialSummaryResponse:
    ticker = ticker.upper()

    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == ticker
            )
        )

        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        summary = get_financial_summary(
            session,
            company.cik,
        )

        def build_period_response(data: dict) -> dict:
            result = {
                "period_start": data["period_start"],
                "period_end": data["period_end"],
                "fiscal_year": data["fiscal_year"],
                "fiscal_period": data["fiscal_period"],
                "filed": data["filed"],
                "form": data["form"],
            }

            if "value" in data:
                result["value"] = float(data["value"])

            if "revenue" in data:
                result["revenue"] = float(data["revenue"])

            if "net_income" in data:
                result["net_income"] = float(data["net_income"])

            return result

        return FinancialSummaryResponse(
            company_cik=summary["company_cik"],
            metrics={
                name: {
                    "metric": metric["metric"],
                    "value": float(metric["value"]),
                    "unit": metric["unit"],
                    "current": build_period_response(
                        metric["current"]
                    ),
                    "previous": (
                        build_period_response(
                            metric["previous"]
                        )
                        if metric.get("previous") is not None
                        else None
                    ),
                    "source": metric.get("source"),
                }
                for name, metric in summary["metrics"].items()
            },
        )
@app.get(
    "/companies/{ticker}/financial-snapshot",
    response_model=FinancialSnapshotResponse,
)
def get_financial_snapshot_by_ticker(
    ticker: str,
) -> FinancialSnapshotResponse:
    ticker = ticker.upper()

    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == ticker
            )
        )

        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        snapshot = get_financial_snapshot(
            session,
            company.cik,
        )

        return FinancialSnapshotResponse.model_validate(
            snapshot
        )
@app.get(
    "/companies/{ticker}/financial-history",
    response_model=FinancialHistoryResponse,
)
def get_financial_history_by_ticker(
    ticker: str,
) -> FinancialHistoryResponse:
    ticker = ticker.upper()

    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == ticker
            )
        )

        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        history = get_financial_history(
            session,
            company.cik,
        )

        return FinancialHistoryResponse(
            company_cik=company.cik,
            history=[
                {
                    "period_start": item["period_start"],
                    "period_end": item["period_end"],
                    "fiscal_year": item["fiscal_year"],
                    "fiscal_period": item["fiscal_period"],
                    "filed": item["filed"],
                    "form": item["form"],
                    "revenue": (
                        float(item["revenue"])
                        if item["revenue"] is not None
                        else None
                    ),
                    "net_income": (
                        float(item["net_income"])
                        if item["net_income"] is not None
                        else None
                    ),
                    "diluted_eps": (
                        float(item["diluted_eps"])
                        if item["diluted_eps"] is not None
                        else None
                    ),
                }
                for item in history
            ],
        )
@app.get(
    "/companies/{ticker}/sources",
    response_model=list[FinancialSourceResponse],
)
def get_company_sources(
    ticker: str,
) -> list[FinancialSourceResponse]:
    ticker = ticker.upper()

    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == ticker
            )
        )

        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        facts = session.scalars(
            select(FinancialFact)
            .where(
                FinancialFact.company_cik == company.cik,
                FinancialFact.accession_number.is_not(None),
            )
            .order_by(
                FinancialFact.filed.desc(),
            )
        ).all()

        grouped: dict[str, dict] = {}

        if schema_ready(session.connection()):
            indexed_metadata = session.execute(select(FilingPublication.accession_number, FilingPublication.form,
                FilingPublication.filed).where(FilingPublication.company_cik == company.cik)).all()
        else:
            groups, indexed_metadata = {}, []
            for chunk in research_chunks(session, FilingChunk.company_cik == company.cik):
                groups.setdefault(chunk.accession_number, []).append(chunk)
            for accession, chunks in groups.items():
                try:
                    validate_chunks(chunks)
                    indexed_metadata.append((accession, chunks[0].form, chunks[0].filed))
                except ValueError:
                    pass
        searchable_accessions = {row[0] for row in indexed_metadata}

        for fact in facts:
            accession = fact.accession_number

            if accession not in grouped:
                grouped[accession] = {
                    "accession_number": accession,
                    "form": fact.form,
                    "filed": fact.filed,
                    "period_start": fact.period_start,
                    "period_end": fact.period_end,
                    "metrics": set(),
                }

            item = grouped[accession]

            if fact.metric:
                item["metrics"].add(
                    fact.metric
                )

            if (
                fact.period_start is not None
                and (
                    item["period_start"] is None
                    or fact.period_start < item["period_start"]
                )
            ):
                item["period_start"] = fact.period_start

            if (
                fact.period_end is not None
                and (
                    item["period_end"] is None
                    or fact.period_end > item["period_end"]
                )
            ):
                item["period_end"] = fact.period_end

        # Filing indexing does not import financial facts. Expose chunk-backed
        # sources without inventing financial periods or metrics.
        for accession, form, filed in indexed_metadata:
            grouped.setdefault(accession, {
                "accession_number": accession, "form": form, "filed": filed,
                "period_start": None, "period_end": None, "metrics": set(),
            })

        sources = []

        for item in grouped.values():
            sources.append(
                FinancialSourceResponse(
                    accession_number=item["accession_number"],
                    form=item["form"],
                    filed=item["filed"],
                    period_start=item["period_start"],
                    period_end=item["period_end"],
                    metrics=sorted(
                        item["metrics"]
                    ),
                    sec_url=build_filing_url(
                        company.cik,
                        item["accession_number"],
                    ),
                    has_filing_chunks=(
                        item["accession_number"] in searchable_accessions
                    ),
                )
            )

        return sorted(sources, key=lambda source: (str(source.filed or ""), source.accession_number), reverse=True)
@app.get("/companies/{ticker}/freshness", response_model=Freshness)
def company_freshness(ticker: str):
    with read_session(HttpSessionLocal) as session:
        return freshness(session, ticker)


def stored_filing(session, ticker, accession):
    company = session.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise HTTPException(404, detail="Unknown company")
    require_published(session, company.cik, accession)
    chunks = research_chunks(session, FilingChunk.company_cik == company.cik,
                             FilingChunk.accession_number == accession)
    if not chunks:
        raise inconsistent_evidence()
    first = chunks[0]
    return company, chunks, {
        "ticker": company.ticker, "company_name": company.name, "company_cik": company.cik,
        "accession_number": accession, "form": first.form, "filed": first.filed,
        "filename": first.filename, "sec_url": first.sec_url,
    }


@app.get("/companies/{ticker}/filings/{accession_number}/chunks/{chunk_id}/tone",
         response_model=FilingToneResponse)
def get_filing_chunk_tone(ticker: str, accession_number: str, chunk_id: str, request: Request):
    """Explainable lexical tone proxy, not investment sentiment, risk or prediction.

    Offsets index the returned exact passage in Unicode code points, never the
    full filing or JavaScript UTF-16. Overlapping passages are not aggregated.
    """
    pins = request.headers.getlist("X-FinLens-Data-Version")
    if len(pins) != 1 or request.query_params:
        raise HTTPException(422, "Invalid filing tone selector or publication pin.",
                            headers={"X-FinLens-Error-Code": "TONE_INVALID_INPUT"})
    pin = pins[0]
    validate_tone_request(ticker, accession_number, chunk_id, pin)
    with read_session(HttpSessionLocal) as session:
        passage = resolve_published_passage(session, ticker, accession_number, chunk_id, pin)
    return score_published_passage(passage)


@app.get("/companies/{ticker}/filings/{accession_number}/text")
def get_company_filing_text(ticker: str, accession_number: str):
    with read_session(HttpSessionLocal) as session:
        company, chunks, result = stored_filing(session, ticker, accession_number)
        body = stored_research_text(session, company.cik, accession_number)
        return {**result, "text": body, "text_length": len(body),
                "raw_url": build_filing_raw_url(company.cik, accession_number)}


@app.get("/companies/{ticker}/filings/{accession_number}/chunks")
def get_company_filing_chunks(ticker: str, accession_number: str):
    with read_session(HttpSessionLocal) as session:
        _, chunks, result = stored_filing(session, ticker, accession_number)
        return {**result, "chunk_count": len(chunks), "chunks": [
            {"chunk_id": c.chunk_id, "text": c.text, "start_char": c.start_char, "end_char": c.end_char,
             "ticker": result["ticker"], "company_name": result["company_name"],
             "accession_number": c.accession_number, "filename": c.filename, "form": c.form,
             "filed": c.filed, "sec_url": c.sec_url} for c in chunks]}


@app.get(
    "/companies/{ticker}/filings/{accession_number}/search"
)
def search_company_filing(
    ticker: str,
    accession_number: str,
    q: ResearchQuery,
    limit: ResearchLimit = 5,
):
    validate_research_input(q, limit)
    ticker = ticker.upper()

    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(
                Company.ticker == ticker
            )
        )

        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        require_published(session, company.cik, accession_number)
        results = search_filing_chunks(
            session,
            company.cik,
            accession_number,
            q,
            limit,
)

        results = [
            chunk
            for chunk in results
            if chunk.accession_number
            == accession_number
        ]

        return {
            "ticker": company.ticker,
            "company_name": company.name,
            "accession_number": accession_number,
            "query": q,
            "result_count": len(results),
            "results": [
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "form": chunk.form,
                    "filename": chunk.filename,
                    "filed": chunk.filed,
                    "sec_url": chunk.sec_url,
                }
                for chunk in results
            ],
        }


@app.get(
    "/companies/{ticker}/filings/{accession_number}/semantic-search"
)
def semantic_search_company_filing(
    ticker: str,
    accession_number: str,
    q: ResearchQuery,
    limit: ResearchLimit = 5,
):
    validate_research_input(q, limit)
    ticker = ticker.upper()

    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(Company.ticker == ticker)
        )
        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        require_published(session, company.cik, accession_number)
        results = search_filing_chunks_semantic(
            session,
            company.cik,
            accession_number,
            q,
            limit,
        )
        return {
            "ticker": company.ticker,
            "company_name": company.name,
            "accession_number": accession_number,
            "query": q,
            "result_count": len(results),
            "results": [
                {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "form": chunk.form,
                    "filename": chunk.filename,
                    "filed": chunk.filed,
                    "sec_url": chunk.sec_url,
                    "similarity": similarity,
                }
                for chunk, similarity in results
            ],
        }


@app.get("/companies/{ticker}/context")
def get_company_context(ticker: str, q: ResearchQuery, limit: ResearchLimit = 5):
    validate_research_input(q, limit)
    with read_session(HttpSessionLocal) as session:
        company = session.scalar(select(Company).where(Company.ticker == ticker.upper()))
        if company is None:
            raise HTTPException(404, detail="Unknown company")
        return {"ticker": company.ticker, "company_name": company.name,
                **build_company_context(session, company.cik, q, limit)}


@app.get(
    "/companies/{ticker}/filings/{accession_number}/context"
)
def get_company_filing_context(
    ticker: str,
    accession_number: str,
    q: ResearchQuery,
    limit: ResearchLimit = 5,
):
    validate_research_input(q, limit)
    ticker = ticker.upper()

    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(Company.ticker == ticker)
        )
        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        require_published(session, company.cik, accession_number)
        filing_context = build_filing_context(
            session,
            company.cik,
            accession_number,
            q,
            limit,
        )
        return {
            "ticker": company.ticker,
            "company_name": company.name,
            "accession_number": accession_number,
            **filing_context,
        }


@app.post(
    "/companies/{ticker}/filings/{accession_number}/answer",
    response_model=FilingAnswerResponse,
)
def answer_company_filing_question(
    ticker: str,
    accession_number: str,
    request: FilingAnswerRequest,
):
    validate_research_input(request.question, request.limit)
    ticker = ticker.upper()
    with read_session(HttpSessionLocal) as session:
        company = session.scalar(
            select(Company).where(Company.ticker == ticker)
        )
        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

        require_published(session, company.cik, accession_number)
        filing_context = build_filing_context(
            session,
            company.cik,
            accession_number,
            request.question,
            request.limit,
        )
        metadata = {
            "ticker": company.ticker,
            "company_name": company.name,
            "accession_number": accession_number,
        }
    # Release the read transaction/connection before the remote model request.
    try:
        answer = answer_filing_question(
            request.question,
            filing_context["context"],
            filing_context["citations"],
        )
    except AnswerConfigurationError as exc:
        raise HTTPException(
            status_code=503, detail=str(exc),
            headers={"X-FinLens-Error-Code": "LLM_UNAVAILABLE"},
        ) from exc
    except AnswerTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail=str(exc),
            headers={"X-FinLens-Error-Code": "LLM_TIMEOUT"},
        ) from exc
    except MalformedModelOutputError as exc:
        raise HTTPException(
            status_code=502, detail=str(exc),
            headers={"X-FinLens-Error-Code": "MALFORMED_MODEL_OUTPUT"},
        ) from exc
    except AnswerGenerationError as exc:
        raise HTTPException(
            status_code=502, detail=str(exc),
            headers={"X-FinLens-Error-Code": "UPSTREAM_FAILURE"},
        ) from exc
    return {**metadata, **answer}


# Freeze admission only after all maintained routes have been registered.
app.add_middleware(
    ReleaseAdmissionMiddleware, router=app.router,
    admitted_routes=tuple(route for route in app.router.routes
                          if any((method, getattr(route, "path", None)) in READONLY_ROUTES
                                 for method in getattr(route, "methods", ()))),
)
