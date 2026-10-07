"""Bounded financial value questions, using the existing normalized metric service.

This module has no retrieval, SEC acquisition, provider or configuration dependency.
Language aliases describe questions only; units, formulas and financial semantics
come exclusively from the canonical registry and FinancialMetrics.
"""
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.financial_metric_registry import METRICS, SELECTION_POLICY
from app.financial_metric_schemas import HistoryComparability, NormalizedMetric
from app.financial_metrics_service import FinancialMetrics, UnknownCompany
from app.models import Company, FinancialFact

PeriodIntent = Literal["quarter", "annual", "latest_available"]

# Presentation/question vocabulary only, not a second source/concept registry.
QUESTION_TERMS = {
    "revenue": ("Revenue", ("revenue", "sales", "net sales")),
    "gross_profit": ("Gross profit", ("gross profit",)),
    "operating_income": ("Operating income", ("operating income", "operating profit")),
    "net_income": ("Net income", ("net income", "net profit", "earnings", "profit")),
    "diluted_eps": ("Diluted EPS", ("diluted eps", "eps", "earnings per share", "diluted earnings per share")),
    "cash_and_equivalents": ("Cash and equivalents", ("cash", "cash balance", "cash and equivalents", "cash and cash equivalents")),
    "total_assets": ("Total assets", ("total assets", "assets")),
    "total_liabilities": ("Total liabilities", ("total liabilities", "liabilities")),
    "operating_cash_flow": ("Operating cash flow", ("operating cash flow", "cash flow from operations")),
    "capital_expenditures": ("Capital expenditures", ("capital expenditures", "capital expenditure", "capex")),
    "free_cash_flow": ("Free cash flow", ("free cash flow", "fcf")),
    "revenue_growth_yoy": ("Revenue growth YoY", ("revenue growth", "sales growth", "net sales growth", "yoy revenue growth", "year over year revenue growth", "revenue growth yoy")),
    "gross_margin": ("Gross margin", ("gross margin",)),
    "operating_margin": ("Operating margin", ("operating margin",)),
    "net_margin": ("Net margin", ("net margin",)),
}
assert set(QUESTION_TERMS) == set(METRICS)


class ResearchAnswerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


class ResearchAnswer(BaseModel):
    ticker: str
    company_name: str
    question: str
    matched: bool
    status: Literal["available", "unavailable", "not_applicable", "not_matched", "company_mismatch"]
    metric: str | None = None
    metric_label: str | None = None
    period_intent: PeriodIntent | None = None
    formatted_value: str | None = None
    answer_text: str | None = None
    explanation: str | None = None
    observation: NormalizedMetric | None = None
    comparability: HistoryComparability | None = None
    selection_policy: str = SELECTION_POLICY


def words(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def company_aliases(company):
    name = words(company.name)
    short = re.split(r"\b(?:inc|corp|corporation|co|holdings)\b", name)[0].strip()
    aliases = {name, short}
    # A distinctive first name is useful (Apple, Microsoft, JPMorgan), but
    # generic first words must never consume financial/question vocabulary.
    first = name.split()[0]
    if len(first) > 2 and first not in {"bank", "general", "american", "united", "home", "eli", "johnson", "morgan", "goldman", "walt"}:
        aliases.add(first)
    if len(company.ticker) > 1:  # single-letter tickers collide with prose
        aliases.add(company.ticker.lower())
    return {alias for alias in aliases if alias}


def recognize(question, selected, companies):
    """Reject remaining unknown words rather than guessing financial meaning."""
    text = words(question)
    mentions = set()
    aliases = [(alias, company.ticker) for company in companies for alias in company_aliases(company)]
    for alias, ticker in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, text):
            mentions.add(ticker)
            text = re.sub(pattern, " ", text)
    if mentions - {selected.ticker}:
        return None, None, "company_mismatch"

    # A bare "how" asks about method/presentation, not an amount. Require
    # "how much" for every such clause, including compound questions.
    if re.search(r"\bhow\b(?!\s+much\b)", text):
        return None, None, "not_matched"
    # Permit the active verb in clear amount requests ("how much revenue is
    # Apple reporting", "what revenue is Apple reporting"). Keep noun phrases
    # such as "what is revenue reporting" outside the value vocabulary.
    if (re.search(r"\bhow\s+much\b", text)
            or re.match(r"\s*what\s+(?!(?:is|are|was|were|s)\b)", text)):
        text = re.sub(r"\b(?:is|are|was|were)\s+reporting\b", "reported", text)

    candidates = [(alias, name) for name, (_, terms) in QUESTION_TERMS.items() for alias in terms]
    matched = []
    for alias, name in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, text):
            matched.append(name)
            text = re.sub(pattern, " ", text)
    if len(matched) != 1:
        return None, None, "not_matched"
    metric = matched[0]
    quarter = bool(re.search(r"\b(?:quarter|quarterly)\b", text))
    annual = bool(re.search(r"\b(?:annual|annually|yearly|year)\b", text))
    if quarter and annual:
        return None, None, "not_matched"
    intent = "quarter" if quarter else "annual" if annual else "latest_available"
    text = re.sub(r"\b(?:quarter|quarterly|annual|annually|yearly|year|latest|available)\b", " ", text)
    allowed = {"what", "is", "was", "were", "are", "the", "a", "an", "of", "for", "how", "much", "did", "have", "report", "reported", "show", "me", "tell", "please", "s", "its"}
    if set(text.split()) - allowed:
        return None, None, "not_matched"
    return metric, intent, None


def format_value(value: Decimal, unit: str):
    with localcontext() as ctx:
        ctx.prec = max(40, len(value.as_tuple().digits) + abs(value.adjusted()) + 10)
        if unit == "ratio":
            return f"{value * 100:,.2f}%"
        if unit == "USD/share":
            return f"{'-' if value < 0 else ''}${abs(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f} per share"
        absolute = abs(value)
        scale, suffix = next(((scale, suffix) for scale, suffix in [(Decimal('1e12'), 'T'), (Decimal('1e9'), 'B'), (Decimal('1e6'), 'M'), (Decimal('1e3'), 'K')] if absolute >= scale), (Decimal(1), ''))
        rounded = (absolute / scale).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return f"{'-' if value < 0 else ''}${rounded:,.2f}{suffix}"


PERIOD_TEXT = {"quarter": "quarter", "annual": "year", "half_year": "six-month YTD period", "nine_months": "nine-month YTD period"}


def resolve_answer(service, question, metric, intent):
    definition = METRICS[metric]
    if intent in {"quarter", "annual"}:
        point = service.summary(intent).metrics[metric]
    else:
        kinds = ["instant"] if definition.kind == "instant" else ["quarter", "half_year", "nine_months", "annual"]
        histories = [service.history(metric, kind, 1) for kind in kinds]
        points = [p for history in histories for p in history.history]
        # Latest observation, including an unavailable one. Ties prefer the
        # shortest direct period and never relabel YTD as a quarter.
        point = max(points, key=lambda p: (p.period.end, p.period.start or p.period.end)) if points else service.missing(metric, next((h.reason for h in histories if h.reason), "No compatible stored reporting period."), status=histories[0].status)
    label = QUESTION_TERMS[metric][0]
    result = ResearchAnswer(ticker=service.company.ticker, company_name=service.company.name,
                            question=question, matched=True, status=point.status,
                            metric=metric, metric_label=label, period_intent=intent,
                            observation=point, comparability=HistoryComparability() if metric == "diluted_eps" else None)
    if point.status != "available":
        scope = {"quarter": "Quarterly", "annual": "Annual", "latest_available": "Latest available"}[intent]
        result.explanation = point.reason or "No compatible stored SEC observations or inputs."
        result.answer_text = f"{scope} {label.lower().replace('yoy', 'YoY')} for {service.company.name} is {'not applicable' if point.status == 'not_applicable' else 'unavailable'}. {result.explanation}"
        return result
    result.formatted_value = format_value(point.value, point.unit)
    date_label = point.period.end.strftime("%B %d, %Y").replace(" 0", " ")
    period_label = f"as of {date_label}" if point.period.kind == "instant" else f"for the {PERIOD_TEXT[point.period.kind]} ended {date_label}"
    scope = {"quarter": "latest available quarterly", "annual": "latest available annual", "latest_available": "latest available"}[intent]
    if point.period.kind == "instant":
        reporting_date = {"quarter": "latest available quarterly reporting date", "annual": "latest available annual reporting date", "latest_available": "latest available observation"}[intent]
        result.answer_text = f"{service.company.name} reported {result.formatted_value} in {label.lower()} {period_label} ({reporting_date})."
    else:
        result.answer_text = f"{service.company.name}'s {scope} {label.lower()} was {result.formatted_value} {period_label}."
    return result


def answer_research_question(session, ticker, question):
    companies = list(session.scalars(select(Company).order_by(Company.id)))
    selected = next((company for company in companies if company.ticker == ticker.upper()), None)
    if selected is None:
        raise UnknownCompany(ticker)
    metric, intent, rejection = recognize(question, selected, companies)
    if rejection:
        return ResearchAnswer(ticker=selected.ticker, company_name=selected.name, question=question,
                              matched=False, status=rejection,
                              explanation=f"This workspace is selected for {selected.name} ({selected.ticker}). Select the company named in your question or ask about this company." if rejection == "company_mismatch" else "This question is outside supported latest financial value questions. Continue with SEC evidence research.")
    facts = list(session.scalars(select(FinancialFact).where(FinancialFact.company_cik == selected.cik).order_by(FinancialFact.id)))
    return resolve_answer(FinancialMetrics(selected, facts), question, metric, intent)
