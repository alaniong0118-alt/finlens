from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import distinct, func, select, text
from app.sec_client import (
    build_filing_url,
    build_filing_raw_url,
    get_filing_raw_text,
)
from app.database import engine, SessionLocal
from app.financial_analysis import (
    get_financial_history,
    get_financial_snapshot,
    get_financial_summary,
)
from app.sec_parser import (
    extract_filing_text,
    chunk_filing_text,
)
from app.filing_search_service import (
    search_filing_chunks,
    search_filing_chunks_semantic,
)
from app.rag_context_service import build_filing_context
from app.answer_service import (
    AnswerConfigurationError,
    AnswerGenerationError,
    AnswerTimeoutError,
    MalformedModelOutputError,
    answer_filing_question,
)
from app.models import Company, FinancialFact, FilingChunk
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


class FilingAnswerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=50)


app = FastAPI(
    title="FinLens API",
    version="0.1.0",
    description=(
        "Local development foundation for the "
        "FinLens financial research platform."
    ),
)

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


@app.get(
    "/dbz",
    response_model=DatabaseHealthResponse,
)
def database_health() -> DatabaseHealthResponse:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return DatabaseHealthResponse(
        status="ok",
        database="postgresql",
    )


@app.get(
    "/companies",
    response_model=list[CompanyResponse],
)
def get_companies() -> list[CompanyResponse]:
    indexed_filings = (
        select(
            FilingChunk.company_cik.label("company_cik"),
            func.count(distinct(FilingChunk.accession_number)).label(
                "indexed_filing_count"
            ),
        )
        .where(FilingChunk.embedding.is_not(None))
        .group_by(FilingChunk.company_cik)
        .subquery()
    )
    with SessionLocal() as session:
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


@app.get(
    "/companies/{ticker}/financial-summary",
    response_model=FinancialSummaryResponse,
)
def get_financial_summary_by_ticker(
    ticker: str,
) -> FinancialSummaryResponse:
    ticker = ticker.upper()

    with SessionLocal() as session:
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

    with SessionLocal() as session:
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

    with SessionLocal() as session:
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

    with SessionLocal() as session:
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

        indexed_metadata = session.execute(
            select(FilingChunk.accession_number, FilingChunk.form, FilingChunk.filed)
            .where(FilingChunk.company_cik == company.cik)
            .distinct()
        ).all()
        searchable_accessions = {row.accession_number for row in indexed_metadata}

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
@app.get(
    "/companies/{ticker}/filings/{accession_number}/text"
)
def get_company_filing_text(
    ticker: str,
    accession_number: str,
):
    ticker = ticker.upper()

    with SessionLocal() as session:
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

        filing = session.scalar(
            select(FinancialFact)
            .where(
                FinancialFact.company_cik == company.cik,
                FinancialFact.accession_number
                == accession_number,
            )
            .order_by(
                FinancialFact.filed.desc()
            )
        )

        if filing is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Filing '{accession_number}' "
                    f"not found for company '{ticker}'"
                ),
            )

        raw_text = get_filing_raw_text(
            company.cik,
            accession_number,
        )

        parsed = extract_filing_text(
            raw_text,
            filing.form,
        )

        return {
            "ticker": company.ticker,
            "company_name": company.name,
            "company_cik": company.cik,
            "accession_number": accession_number,
            "form": parsed["form"],
            "filed": filing.filed,
            "filename": parsed["filename"],
            "sec_url": build_filing_url(
                company.cik,
                accession_number,
            ),
            "raw_url": build_filing_raw_url(
                company.cik,
                accession_number,
            ),
            "text_length": len(parsed["text"]),
            "text": parsed["text"],
        }
@app.get(
    "/companies/{ticker}/filings/{accession_number}/chunks"
)
def get_company_filing_chunks(
    ticker: str,
    accession_number: str,
):
    ticker = ticker.upper()

    with SessionLocal() as session:
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

        filing = session.scalar(
            select(FinancialFact)
            .where(
                FinancialFact.company_cik == company.cik,
                FinancialFact.accession_number
                == accession_number,
            )
            .order_by(
                FinancialFact.filed.desc()
            )
        )

        if filing is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Filing '{accession_number}' "
                    f"not found for company '{ticker}'"
                ),
            )

        raw_text = get_filing_raw_text(
            company.cik,
            accession_number,
        )

        parsed = extract_filing_text(
            raw_text,
            filing.form,
        )

        chunks = chunk_filing_text(
            parsed["text"]
        )

        sec_url = build_filing_url(
            company.cik,
            accession_number,
        )

        for chunk in chunks:
            chunk["ticker"] = company.ticker
            chunk["company_name"] = company.name
            chunk["accession_number"] = accession_number
            chunk["form"] = parsed["form"]
            chunk["filename"] = parsed["filename"]
            chunk["filed"] = filing.filed
            chunk["sec_url"] = sec_url

        return {
            "ticker": company.ticker,
            "company_name": company.name,
            "company_cik": company.cik,
            "accession_number": accession_number,
            "form": parsed["form"],
            "filename": parsed["filename"],
            "filed": filing.filed,
            "sec_url": sec_url,
            "chunk_count": len(chunks),
            "chunks": chunks,
    }
@app.get(
    "/companies/{ticker}/filings/{accession_number}/search"
)
def search_company_filing(
    ticker: str,
    accession_number: str,
    q: str,
    limit: int = 5,
):
    ticker = ticker.upper()

    with SessionLocal() as session:
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
    q: str,
    limit: int = 5,
):
    ticker = ticker.upper()
    if limit <= 0 or limit > 50:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 50",
        )

    with SessionLocal() as session:
        company = session.scalar(
            select(Company).where(Company.ticker == ticker)
        )
        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

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


@app.get(
    "/companies/{ticker}/filings/{accession_number}/context"
)
def get_company_filing_context(
    ticker: str,
    accession_number: str,
    q: str,
    limit: int = 5,
):
    ticker = ticker.upper()
    if limit <= 0 or limit > 50:
        raise HTTPException(
            status_code=400,
            detail="limit must be between 1 and 50",
        )

    with SessionLocal() as session:
        company = session.scalar(
            select(Company).where(Company.ticker == ticker)
        )
        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

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
    ticker = ticker.upper()
    with SessionLocal() as session:
        company = session.scalar(
            select(Company).where(Company.ticker == ticker)
        )
        if company is None:
            raise HTTPException(
                status_code=404,
                detail=f"Company '{ticker}' not found",
            )

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
