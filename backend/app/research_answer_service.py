"""Bounded financial value questions, using the existing normalized metric service.

This module has no retrieval, SEC acquisition, provider or configuration dependency.
Language aliases describe questions only; units, formulas and financial semantics
come exclusively from the canonical registry and FinancialMetrics.
"""
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.financial_metric_registry import METRICS, SELECTION_POLICY
from app.financial_metric_schemas import HistoryComparability, NormalizedMetric, FiscalPeriodRequest, MetricComparison
from app.financial_metrics_service import FinancialMetrics, UnknownCompany
from app.models import Company, FinancialFact

PeriodIntent = Literal["quarter", "annual", "latest_available"]
EXPLICIT_YOY = re.compile(r"\b(?:yoy|year (?:over|to) year)\b")
PERIOD_PATTERN = r"\b(?:q([1-4])\s*(?:fy\s*)?((?:19|20)\d{2})|(?:fy\s*)?((?:19|20)\d{2})\s*q([1-4])|(?:fy\s*)?((?:19|20)\d{2}))\b"
OperationKind = Literal["latest_value", "historical_value", "revenue_level_comparison",
                        "metric_level_comparison", "adjacent_year_yoy_growth", "cumulative_period_growth",
                        "percentage_point_difference", "unsupported_growth_rate_comparison",
                        "unsupported_relative_change", "unsupported_annualized_growth", "ambiguous"]

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
    answer_kind: Literal["latest_metric", "historical_metric", "period_comparison"] = "latest_metric"
    requested_period: FiscalPeriodRequest | None = None
    comparison: MetricComparison | None = None
    formatted_absolute_change: str | None = None
    formatted_percentage_change: str | None = None


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


def company_question(question, selected, companies):
    text = words(question)
    mentions = set()
    aliases = [(alias, company.ticker) for company in companies for alias in company_aliases(company)]
    for alias, ticker in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, text):
            mentions.add(ticker)
            text = re.sub(pattern, " ", text)
    if mentions - {selected.ticker}:
        return text, "company_mismatch"
    return text, None


@dataclass(frozen=True)
class MathematicalIntent:
    operation: Literal["value", "level_change", "growth_rate_change", "point_change", "relative_change", "annualized", "unsupported"]
    target: Literal["metric", "growth", "margin"] = "metric"
    operands: Literal["single_or_interval", "growth_observations", "unknown"] = "single_or_interval"
    reason: str | None = None

    @property
    def supported(self):
        return (self.operation not in {"growth_rate_change", "annualized", "unsupported"}
                and not (self.operation == "relative_change" and self.target == "margin"))


def mathematical_text(question):
    """Canonicalize only known equivalent operators; never normalize dates."""
    return question.translate(str.maketrans({"％": "%", "／": "/", "∕": "/", "⁄": "/"}))


def classify_math_intent(question):
    """Bounded preflight, independent of company/metric alias consumption.

    Keep operators while treating apostrophes, hyphens, parentheses and spacing
    as word boundaries. Unknown wording still faces the closed grammar below.
    This classifies requests only; it never selects facts or calculates values.
    """
    question = mathematical_text(question)
    # Unknown symbols cannot disappear into the word-only grammar. Hyphens,
    # apostrophes and normal sentence punctuation remain ordinary boundaries.
    if any(unicodedata.category(char).startswith("S") or char in "*\\^‰‱٪"
           or char.isnumeric() and not char.isascii() for char in question):
        return MathematicalIntent("unsupported", operands="unknown", reason="Unknown mathematical notation.")
    tokens = re.findall(r"[a-z0-9]+|[%/]", question.lower())
    vocabulary = set(tokens)
    phrases = " ".join(tokens)
    # Slash operands stay visible even in '/ (fiscal-year)'. Division is not
    # supported by this answer grammar, so unknown slash operations also abstain.
    per_year = bool(re.search(r"(?:/|\bper)\s+(?:(?:fiscal|calendar)\s+)?(?:year|yr)\b", phrases))
    if per_year or vocabulary & {"annualized", "annualised", "cagr"}:
        return MathematicalIntent("annualized")
    if "/" in vocabulary:
        return MathematicalIntent("unsupported")
    # Repeated period-labelled growth operands, and explicit comparisons of
    # growth observations, are not one growth calculation over an interval.
    if "growth" in vocabulary and (tokens.count("growth") > 1
                                   or vocabulary & {"compare", "vs", "versus"}):
        return MathematicalIntent("growth_rate_change", "growth", "growth_observations",
                                  "Comparing separate growth observations is unsupported.")
    change_verbs = {"change", "changed", "increase", "increased", "decrease", "decreased", "grow", "grew"}
    changing = bool(vocabulary & change_verbs)
    # 'Growth' is the operand of a change verb regardless of word order:
    # revenue's growth, growth in revenue, or revenue growth. A compound request
    # with both targets is ambiguous and also abstains rather than guessing.
    if "growth" in vocabulary and (changing or vocabulary & {"rate", "rates"}):
        return MathematicalIntent("growth_rate_change", "growth")
    target = "margin" if "margin" in vocabulary else "metric"
    comparison = (changing or bool(vocabulary & {"growth", "compare", "vs", "versus", "between"})
                  or len(re.findall(r"\b(?:19|20)\d{2}\b", phrases)) == 2)
    points = bool(re.search(r"(?:\bpercent(?:age)?|%)\s+points?\b", phrases))
    if points:
        return MathematicalIntent("point_change" if target == "margin" and comparison else "unsupported", target)
    if comparison and vocabulary & {"%", "percent", "percentage"}:
        return MathematicalIntent("relative_change", target)
    if comparison:
        return MathematicalIntent("point_change" if target == "margin" else "level_change", target)
    return MathematicalIntent("value", target)


@dataclass(frozen=True)
class FinancialOperation:
    """Internal recognition contract, retained until calculation dispatch.

    metric is the requested canonical metric, not a substituted calculation.
    Period labels are requests only; FinancialMetrics owns source selection.
    """
    operation: OperationKind
    metric: str | None
    periods: tuple[FiscalPeriodRequest, ...]
    operands: Literal["single_observation", "period_interval", "growth_observations", "unknown"]
    status: Literal["supported", "unsupported", "ambiguous"]
    math: MathematicalIntent
    period_intent: PeriodIntent = "latest_available"
    explicit_yoy: bool = False
    reason: str | None = None


def operation_category(metric, periods, math, explicit_yoy=False) -> OperationKind | None:
    """Finite operation binding; no observations or arithmetic involved."""
    if not math.supported or math.operands != "single_or_interval":
        return None
    if not periods:
        single_value = math.operation == "value" or (metric == "revenue_growth_yoy" and math.operation == "level_change")
        return "latest_value" if single_value else None
    if len(periods) == 1:
        single_value = math.operation == "value" or (metric == "revenue_growth_yoy" and math.operation == "level_change")
        return "historical_value" if single_value else None
    if len(periods) != 2 or periods[0] == periods[1]:
        return None
    if (periods[0].quarter != periods[1].quarter
            or periods[0].fiscal_year >= periods[1].fiscal_year):
        return None
    if metric.endswith("_margin"):
        return "percentage_point_difference" if math.operation == "point_change" else None
    if math.operation not in {"level_change", "relative_change"}:
        return None
    if metric == "diluted_eps" and math.operation == "relative_change":
        # The shared service deliberately cannot establish EPS percentage
        # comparability. Do not substitute its absolute EPS difference.
        return None
    if explicit_yoy:
        return "adjacent_year_yoy_growth" if metric == "revenue_growth_yoy" and periods[1].fiscal_year - periods[0].fiscal_year == 1 else None
    if metric in {"revenue", "revenue_growth_yoy"}:
        return "cumulative_period_growth" if periods[1].fiscal_year - periods[0].fiscal_year > 1 else "revenue_level_comparison"
    return "metric_level_comparison"


def operation_agrees(intent):
    """Fail closed if recognition's operation/metric/operands disagree.

    This is the mandatory handoff gate before any FinancialMetrics dispatch.
    It prevents a supported flag alone from authorizing another calculation.
    Actual financial comparability remains exclusively FinancialMetrics' job.
    """
    expected_operands = "period_interval" if len(intent.periods) == 2 else "single_observation"
    return (intent.status == "supported" and intent.metric in METRICS
            and intent.operands == expected_operands
            and intent.operation == operation_category(intent.metric, intent.periods, intent.math, intent.explicit_yoy))


def bind_operation(metric, periods, math, period_intent="latest_available", explicit_yoy=False):
    periods = tuple(periods)
    category = operation_category(metric, periods, math, explicit_yoy)
    return FinancialOperation(category or "ambiguous", metric, periods,
                              "period_interval" if len(periods) == 2 else "single_observation",
                              "supported" if category else "ambiguous", math,
                              period_intent, explicit_yoy,
                              None if category else "Requested operation cannot be safely bound to these operands.")


def requested_periods(text):
    periods = []
    for match in re.finditer(PERIOD_PATTERN, text):
        q1, y1, y2, q2, year = match.groups()
        periods.append(FiscalPeriodRequest(fiscal_year=int(y1 or y2 or year),
                                          quarter=int(q1 or q2) if q1 or q2 else None))
    return periods


def recognize(question, selected, companies, *, math_intent=None):
    """Legacy latest-value grammar; historical recognition is additive."""
    math_intent = math_intent or classify_math_intent(question)
    text, rejection = company_question(question, selected, companies)
    if rejection:
        return None, None, rejection
    if not math_intent.supported:
        return None, None, "not_matched"

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


def recognize_historical(question, selected, companies, *, math_intent=None):
    """One fiscal label or two explicit labels with a comparison connector.

    Unknown qualifiers are rejected; this is not general language reasoning.
    Company mismatch is checked before calling this from the production path.
    """
    math_intent = math_intent or classify_math_intent(question)
    text, rejection = company_question(question, selected, companies)
    if rejection or re.search(r"\bhow\b(?!\s+much\b)", text):
        return None
    if not math_intent.supported:
        return None
    # Capture the qualifier before consuming aliases, which otherwise erase
    # the distinction between cumulative growth and explicit YoY intent.
    explicit_yoy = bool(EXPLICIT_YOY.search(text))
    text = EXPLICIT_YOY.sub(" ", text)
    periods = requested_periods(text)
    if len(periods) not in {1, 2}:
        return None
    text = re.sub(PERIOD_PATTERN, " ", text)
    candidates = [(alias, name) for name, (_, terms) in QUESTION_TERMS.items() for alias in terms]
    matched = []
    for alias, name in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, text):
            matched.append(name)
            text = re.sub(pattern, " ", text)
    if len(matched) != 1:
        return None
    if explicit_yoy and matched[0] != "revenue_growth_yoy":
        return None
    common = {"what", "is", "was", "were", "are", "the", "a", "an", "of", "for", "how", "much", "did", "have", "report", "reported", "show", "me", "tell", "please", "s", "its", "in", "during", "fiscal", "year", "annual"}
    residual = set(text.split())
    if len(periods) == 1:
        if residual - common or (periods[0].quarter and residual & {"annual", "year"}):
            return None
        return bind_operation(matched[0], periods, math_intent, explicit_yoy=explicit_yoy)
    comparative = {"compare", "vs", "versus", "and", "between", "from", "to", "grow", "grew", "growth", "increase", "increased", "decrease", "decreased", "change", "changed"}
    connector = bool(residual & {"compare", "vs", "versus", "between", "from"}) or bool(re.search(r"\b\d{4}\s*[-–]\s*\d{4}\b", question))
    if not connector or residual - common - comparative:
        return None
    if ("annual" in residual and any(p.quarter for p in periods)) or periods[0] == periods[1]:
        return None
    if "from" in residual and (periods[0].fiscal_year, periods[0].quarter or 0) > (periods[1].fiscal_year, periods[1].quarter or 0):
        return None
    if explicit_yoy:
        # A range/from-to can describe one adjacent-year growth interval.
        # Compare/vs/between can instead ask for two independent YoY rates;
        # that analysis is outside this bounded comparison contract.
        if (abs(periods[1].fiscal_year - periods[0].fiscal_year) != 1
                or periods[0].quarter != periods[1].quarter
                or residual & {"compare", "vs", "versus", "between"}):
            return None
    return bind_operation(matched[0], sorted(periods, key=lambda p: (p.fiscal_year, p.quarter or 0)),
                          math_intent, explicit_yoy=explicit_yoy)


def resolve_historical_answer(service, question, operation):
    # Only these explicitly bound operations may consume revenue levels when
    # the requested metric was growth. Single growth observations retain YoY.
    metric = ("revenue" if operation.operation in {"revenue_level_comparison", "adjacent_year_yoy_growth", "cumulative_period_growth"}
              else operation.metric)
    periods = operation.periods
    request = periods[0]
    intent = "quarter" if request.quarter else "annual"
    label = QUESTION_TERMS[metric][0]
    result = ResearchAnswer(ticker=service.company.ticker, company_name=service.company.name,
                            question=question, matched=True, status="unavailable", metric=metric,
                            metric_label=label, period_intent=intent,
                            answer_kind="historical_metric" if len(periods) == 1 else "period_comparison",
                            requested_period=request,
                            comparability=HistoryComparability() if metric == "diluted_eps" else None)
    if len(periods) == 1:
        point = service.fiscal_observation(metric, request)
        result.observation, result.status = point, point.status
        if point.status == "available":
            result.formatted_value = format_value(point.value, point.unit)
            as_of = f" as of {point.period.end.isoformat()}" if point.period.kind == "instant" else ""
            result.answer_text = f"{service.company.name}'s {request.label} {label.lower()} was {result.formatted_value}{as_of}."
        else:
            result.explanation = point.reason
            result.answer_text = f"{request.label} {label.lower()} is {'not applicable' if point.status == 'not_applicable' else 'unavailable'}. {point.reason}"
        return result
    comparison = service.compare_fiscal(metric, *periods)
    result.comparison, result.status = comparison, comparison.status
    # No single observation represents a comparison. In particular, the
    # presentation layer must not highlight one side as proof of the change.
    if comparison.status != "available":
        result.explanation = comparison.reason
        result.answer_text = f"{label} comparison is {'not applicable' if comparison.status == 'not_applicable' else 'unavailable'}. {comparison.reason}"
        return result
    change = comparison.absolute_change
    sign = "+" if change > 0 else ""
    if comparison.earlier.unit == "ratio":
        result.formatted_absolute_change = f"{sign}{format_value(change, 'ratio')[:-1]} percentage points"
    else:
        result.formatted_absolute_change = sign + format_value(change, comparison.earlier.unit)
    if comparison.percentage_status == "available":
        result.formatted_percentage_change = ("+" if comparison.percentage_change > 0 else "") + format_value(comparison.percentage_change, "ratio")
    result.formatted_value = result.formatted_percentage_change or result.formatted_absolute_change
    action = {"increase": "increased", "decrease": "decreased", "no_change": "was unchanged"}[comparison.direction]
    detail = f" ({result.formatted_percentage_change})" if result.formatted_percentage_change else ""
    prefix = ""
    if re.match(r"\s*did\b", words(question)):
        asked = "increase" if re.search(r"\bincrease\b", words(question)) else "decrease" if re.search(r"\bdecrease\b", words(question)) else None
        if asked:
            prefix = "Yes. " if comparison.direction == asked else "No. "
    result.answer_text = (f"{prefix}{label} {action} from {format_value(comparison.earlier.value, comparison.earlier.unit)} in {periods[0].label} "
                          f"to {format_value(comparison.later.value, comparison.later.unit)} in {periods[1].label}{detail}.")
    if metric == "revenue":
        if operation.operation == "adjacent_year_yoy_growth":
            result.answer_text += " Year-over-year change."
        elif operation.operation == "cumulative_period_growth":
            result.answer_text += " Cumulative period-to-period change."
    return result


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
    operation, rejection = recognize_operation(question, selected, companies)
    if rejection or not operation_agrees(operation):
        return ResearchAnswer(ticker=selected.ticker, company_name=selected.name, question=question,
                              matched=False, status=rejection or "not_matched",
                              explanation=f"This workspace is selected for {selected.name} ({selected.ticker}). Select the company named in your question or ask about this company." if rejection == "company_mismatch" else "This question is outside supported deterministic financial value/comparison questions. Continue with SEC evidence research.")
    facts = list(session.scalars(select(FinancialFact).where(FinancialFact.company_cik == selected.cik).order_by(FinancialFact.id)))
    service = FinancialMetrics(selected, facts)
    return (resolve_answer(service, question, operation.metric, operation.period_intent)
            if operation.operation == "latest_value" else resolve_historical_answer(service, question, operation))


def recognize_operation(question, selected, companies):
    """Keep the typed operation intact across both closed question grammars."""
    math = classify_math_intent(question)
    metric, period_intent, rejection = recognize(question, selected, companies, math_intent=math)
    if rejection == "company_mismatch":
        return None, rejection
    if metric:
        return bind_operation(metric, (), math, period_intent), None
    historical = recognize_historical(question, selected, companies, math_intent=math) if math.supported else None
    if historical is not None:
        return historical, None
    unsupported = {"growth_rate_change": "unsupported_growth_rate_comparison",
                   "relative_change": "unsupported_relative_change", "annualized": "unsupported_annualized_growth"}
    # Diagnostics retain recognizable requested labels/metric even on abstention.
    # They authorize no calculation and are not exposed as an API value.
    text, _ = company_question(question, selected, companies)
    periods = tuple(requested_periods(text))
    candidates = [(alias, name) for name, (_, terms) in QUESTION_TERMS.items() for alias in terms]
    matched = []
    for alias, name in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, text):
            matched.append(name)
            text = re.sub(pattern, " ", text)
    metric = matched[0] if len(matched) == 1 else None
    return FinancialOperation(unsupported.get(math.operation, "ambiguous"), metric, periods,
                              "growth_observations" if math.operands == "growth_observations" else "unknown",
                              "unsupported" if not math.supported else "ambiguous", math,
                              explicit_yoy=bool(EXPLICIT_YOY.search(words(question))),
                              reason=math.reason or "Outside the bounded financial operation grammar."), "not_matched"
