from datetime import timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FinancialFact
from app.sec_client import build_filing_url


def get_quarterly_revenue(
    session: Session,
    company_cik: str,
) -> list[FinancialFact]:
    """
    Get quarterly Revenue records for a company.
    """
    stmt = (
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == company_cik,
            FinancialFact.metric == "Revenues",
            FinancialFact.period_type == "quarter",
        )
        .order_by(
            FinancialFact.period_end.asc(),
            FinancialFact.period_start.asc(),
        )
    )

    return list(session.scalars(stmt).all())


def calculate_yoy_growth(
    current_value: Decimal,
    previous_value: Decimal,
) -> Decimal:
    """
    Calculate year-over-year growth percentage.
    """
    if previous_value == 0:
        raise ValueError(
            "Previous-period value cannot be zero."
        )

    return (
        (current_value - previous_value)
        / previous_value
        * Decimal("100")
    )
def build_metric_source(
    company_cik: str,
    record: FinancialFact,
) -> dict | None:
    """
    Build a source reference for a FinancialFact record.
    """
    if not record.accession_number:
        return None

    return {
        "accession_number": record.accession_number,
        "form": record.form,
        "filed": record.filed,
        "sec_url": build_filing_url(
            company_cik,
            record.accession_number,
        ),
    }
def find_previous_year_record(
    records: list[FinancialFact],
    latest: FinancialFact,
) -> FinancialFact | None:
    """
    Find the comparable quarter from roughly one fiscal year earlier.

    We match by fiscal period and reporting-period dates rather than
    relying on the SEC `fy` value, because `fy` describes filing context
    and can point to the filing year rather than the period being compared.
    """
    if latest.period_end is None:
        return None

    candidates = []

    for record in records:
        if record is latest:
            continue

        if record.period_end is None:
            continue

        if record.period_end >= latest.period_end:
            continue

        if (
            latest.fiscal_period is not None
            and record.fiscal_period != latest.fiscal_period
        ):
            continue

        day_difference = (
            latest.period_end - record.period_end
        ).days

        # Allow normal 52/53-week fiscal calendars and leap years.
        if 330 <= day_difference <= 400:
            candidates.append(
                (
                    abs(day_difference - 364),
                    record,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0][1]


def get_revenue_yoy_growth(
    session: Session,
    company_cik: str,
) -> dict:
    """
    Calculate Revenue YoY growth for the latest quarter.
    """
    records = get_quarterly_revenue(
        session,
        company_cik,
    )

    if not records:
        raise ValueError(
            f"No quarterly Revenue data found for CIK {company_cik}."
        )

    latest = records[-1]

    previous = find_previous_year_record(
        records,
        latest,
    )

    if previous is None:
        raise ValueError(
            "Could not find the comparable quarter "
            "from the previous fiscal year."
        )

    growth = calculate_yoy_growth(
        latest.value,
        previous.value,
    )

    return {
        "metric": "Revenue YoY Growth",
        "value": growth,
        "unit": "%",
        "current": {
            "value": latest.value,
            "period_start": latest.period_start,
            "period_end": latest.period_end,
            "fiscal_year": latest.fiscal_year,
            "fiscal_period": latest.fiscal_period,
            "filed": latest.filed,
            "form": latest.form,
        },
        "previous": {
            "value": previous.value,
            "period_start": previous.period_start,
            "period_end": previous.period_end,
            "fiscal_year": previous.fiscal_year,
            "fiscal_period": previous.fiscal_period,
            "filed": previous.filed,
            "form": previous.form,
        },
        "source": {
            "accession_number": latest.accession_number,
            "form": latest.form,
            "filed": latest.filed,
            "sec_url": build_filing_url(
                company_cik,
                latest.accession_number,
            ),
        },
    }
def get_quarterly_net_income(
    session: Session,
    company_cik: str,
) -> list[FinancialFact]:
    """
    Get quarterly Net Income records for a company.
    """
    stmt = (
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == company_cik,
            FinancialFact.metric == "NetIncomeLoss",
            FinancialFact.period_type == "quarter",
        )
        .order_by(
            FinancialFact.period_end.asc(),
            FinancialFact.period_start.asc(),
        )
    )

    return list(session.scalars(stmt).all())


def get_net_income_yoy_growth(
    session: Session,
    company_cik: str,
) -> dict:
    """
    Calculate Net Income YoY growth for the latest quarter.
    """
    records = get_quarterly_net_income(
        session,
        company_cik,
    )

    if not records:
        raise ValueError(
            f"No quarterly Net Income data found for CIK {company_cik}."
        )

    latest = records[-1]

    previous = find_previous_year_record(
        records,
        latest,
    )

    if previous is None:
        raise ValueError(
            "Could not find the comparable quarter "
            "from the previous fiscal year."
        )

    growth = calculate_yoy_growth(
        latest.value,
        previous.value,
    )

    return {
        "metric": "Net Income YoY Growth",
        "value": growth,
        "unit": "%",
        "current": {
            "value": latest.value,
            "period_start": latest.period_start,
            "period_end": latest.period_end,
            "fiscal_year": latest.fiscal_year,
            "fiscal_period": latest.fiscal_period,
            "filed": latest.filed,
            "form": latest.form,
        },
        "previous": {
            "value": previous.value,
            "period_start": previous.period_start,
            "period_end": previous.period_end,
            "fiscal_year": previous.fiscal_year,
            "fiscal_period": previous.fiscal_period,
            "filed": previous.filed,
            "form": previous.form,
        },
                "source": build_metric_source(
            company_cik,
            latest,
        ),
    }
def get_financial_history(
    session: Session,
    company_cik: str,
) -> list[dict]:
    """
    Return historical quarterly Revenue, Net Income,
    and Diluted EPS data for a company.

    Fiscal year is derived from the company's annual
    reporting periods. When the current fiscal year's
    annual filing does not exist yet, infer the next
    fiscal year from the latest completed annual period.
    """

    metrics = [
        "Revenues",
        "NetIncomeLoss",
        "EarningsPerShareDiluted",
    ]

    quarterly_stmt = (
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == company_cik,
            FinancialFact.metric.in_(metrics),
            FinancialFact.period_type == "quarter",
        )
        .order_by(
            FinancialFact.period_end.asc(),
            FinancialFact.period_start.asc(),
        )
    )

    quarterly_records = list(
        session.scalars(quarterly_stmt).all()
    )

    annual_stmt = (
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == company_cik,
            FinancialFact.metric == "Revenues",
            FinancialFact.period_type == "annual",
        )
        .order_by(
            FinancialFact.period_end.asc()
        )
    )

    annual_records = list(
        session.scalars(annual_stmt).all()
    )

    grouped: dict[tuple, dict] = {}

    for record in quarterly_records:
        key = (
            record.period_start,
            record.period_end,
        )

        if key not in grouped:
            grouped[key] = {
                "period_start": record.period_start,
                "period_end": record.period_end,
                "fiscal_year": None,
                "fiscal_period": None,
                "filed": record.filed,
                "form": record.form,
                "revenue": None,
                "net_income": None,
                "diluted_eps": None,
            }

        if record.fiscal_period in {
            "Q1",
            "Q2",
            "Q3",
        }:
            grouped[key]["fiscal_period"] = (
                record.fiscal_period
            )

        if (
            record.form in {"10-Q", "10-Q/A"}
            and grouped[key]["form"]
            not in {"10-Q", "10-Q/A"}
        ):
            grouped[key]["filed"] = record.filed
            grouped[key]["form"] = record.form

        if record.metric == "Revenues":
            grouped[key]["revenue"] = record.value

        elif record.metric == "NetIncomeLoss":
            grouped[key]["net_income"] = record.value

        elif record.metric == "EarningsPerShareDiluted":
            grouped[key]["diluted_eps"] = record.value

    history = sorted(
        grouped.values(),
        key=lambda item: (
            item["period_end"],
            item["period_start"],
        ),
    )

    # Assign fiscal year from annual period boundaries.
    for item in history:
        matching_annual = None

        for annual in annual_records:
            if (
                annual.period_start
                <= item["period_end"]
                <= annual.period_end
            ):
                matching_annual = annual
                break

        if matching_annual is not None:
            # The fiscal year is represented by the calendar
            # year in which the annual reporting period ends.
            item["fiscal_year"] = (
                matching_annual.period_end.year
            )

        elif annual_records:
            # The current fiscal year may not have a 10-K yet.
            latest_annual = annual_records[-1]

            if (
                item["period_start"]
                > latest_annual.period_end
            ):
                item["fiscal_year"] = (
                    latest_annual.period_end.year + 1
                )

    return history



def get_net_margin(
    session: Session,
    company_cik: str,
) -> dict:
    """
    Calculate Net Income Margin for the latest quarter.
    """
    revenue = get_latest_quarter_metric(
        session,
        company_cik,
        "Revenues",
    )

    net_income = get_latest_quarter_metric(
        session,
        company_cik,
        "NetIncomeLoss",
    )

    if revenue.value == 0:
        raise ValueError(
            "Revenue cannot be zero when calculating Net Margin."
        )

    if (
        revenue.period_start != net_income.period_start
        or revenue.period_end != net_income.period_end
    ):
        raise ValueError(
            "Revenue and Net Income periods do not match."
        )

    margin = (
        net_income.value
        / revenue.value
        * Decimal("100")
    )

    return {
        "metric": "Net Margin",
        "value": margin,
        "unit": "%",
        "current": {
            "revenue": revenue.value,
            "net_income": net_income.value,
            "period_start": revenue.period_start,
            "period_end": revenue.period_end,
            "fiscal_year": revenue.fiscal_year,
            "fiscal_period": revenue.fiscal_period,
            "filed": revenue.filed,
            "form": revenue.form,
        },
        "source": build_metric_source(
            company_cik,
            revenue,
        ),
    }
def get_quarterly_diluted_eps(
    session: Session,
    company_cik: str,
) -> list[FinancialFact]:
    """
    Get quarterly diluted EPS records for a company.
    """
    stmt = (
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == company_cik,
            FinancialFact.metric == "EarningsPerShareDiluted",
            FinancialFact.period_type == "quarter",
        )
        .order_by(
            FinancialFact.period_end.asc(),
            FinancialFact.period_start.asc(),
        )
    )

    return list(session.scalars(stmt).all())


def get_diluted_eps_yoy_growth(
    session: Session,
    company_cik: str,
) -> dict:
    """
    Calculate diluted EPS YoY growth for the latest quarter.
    """
    records = get_quarterly_diluted_eps(
        session,
        company_cik,
    )

    if not records:
        raise ValueError(
            f"No quarterly diluted EPS data found "
            f"for CIK {company_cik}."
        )

    latest = records[-1]

    previous = find_previous_year_record(
        records,
        latest,
    )

    if previous is None:
        raise ValueError(
            "Could not find the comparable quarter "
            "from the previous fiscal year."
        )

    growth = calculate_yoy_growth(
        latest.value,
        previous.value,
    )

    return {
        "metric": "Diluted EPS YoY Growth",
        "value": growth,
        "unit": "%",
        "current": {
            "value": latest.value,
            "period_start": latest.period_start,
            "period_end": latest.period_end,
            "fiscal_year": latest.fiscal_year,
            "fiscal_period": latest.fiscal_period,
            "filed": latest.filed,
            "form": latest.form,
        },
        "previous": {
            "value": previous.value,
            "period_start": previous.period_start,
            "period_end": previous.period_end,
            "fiscal_year": previous.fiscal_year,
            "fiscal_period": previous.fiscal_period,
            "filed": previous.filed,
            "form": previous.form,
        },
                "source": build_metric_source(
            company_cik,
            latest,
        ),
    }
def get_financial_snapshot(
    session: Session,
    company_cik: str,
) -> dict:
    """
    Return the latest quarterly financial snapshot
    together with core analysis metrics.
    """
    revenue = get_latest_quarter_metric(
        session,
        company_cik,
        "Revenues",
    )

    net_income = get_latest_quarter_metric(
        session,
        company_cik,
        "NetIncomeLoss",
    )

    try:
        eps = get_latest_quarter_metric(
            session,
            company_cik,
            "EarningsPerShareDiluted",
        )
    except ValueError:
        eps = None

    return {
        "company_cik": company_cik,
        "period": {
            "period_start": revenue.period_start,
            "period_end": revenue.period_end,
            "fiscal_year": revenue.fiscal_year,
            "fiscal_period": revenue.fiscal_period,
            "filed": revenue.filed,
            "form": revenue.form,
        },
        "values": {
            "revenue": revenue.value,
            "net_income": net_income.value,
            "diluted_eps": (
                eps.value
                if eps is not None
                else None
            ),
        },
        "analysis": get_financial_summary(
            session,
            company_cik,
        ),
    }


def get_financial_summary(
    session: Session,
    company_cik: str,
) -> dict:
    revenue_growth = get_revenue_yoy_growth(
        session,
        company_cik,
    )

    net_income_growth = get_net_income_yoy_growth(
        session,
        company_cik,
    )

    net_margin = get_net_margin(
        session,
        company_cik,
    )

    metrics = {
        "revenue_yoy_growth": revenue_growth,
        "net_income_yoy_growth": net_income_growth,
        "net_margin": net_margin,
    }

    try:
        eps_growth = get_diluted_eps_yoy_growth(
            session,
            company_cik,
        )
    except ValueError:
        eps_growth = None

    if eps_growth is not None:
        metrics["diluted_eps_yoy_growth"] = eps_growth

    return {
        "company_cik": company_cik,
        "metrics": metrics,
    }


def get_latest_quarter_metric(
    session: Session,
    company_cik: str,
    metric: str,
) -> FinancialFact:
    stmt = (
        select(FinancialFact)
        .where(
            FinancialFact.company_cik == company_cik,
            FinancialFact.metric == metric,
            FinancialFact.period_type == "quarter",
        )
        .order_by(
            FinancialFact.period_end.desc(),
            FinancialFact.period_start.desc(),
        )
    )

    record = session.scalars(stmt).first()

    if record is None:
        raise ValueError(
            f"No quarterly {metric} data found for CIK {company_cik}."
        )

    return record