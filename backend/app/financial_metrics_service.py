"""Read-only financial normalization. No SEC client requests or AI dependency."""
from datetime import date, timedelta
from decimal import Decimal, localcontext
import re

from sqlalchemy import select

from app.financial_metric_registry import METRICS, SELECTION_POLICY, REVENUE_CONCEPTS, GROSS_MARGIN_COVERAGE, revenue_bases_compatible
from app.financial_metric_schemas import (
    FactProvenance, FinancialPeriod, MetricInput, NormalizedMetric,
    NormalizedFinancialSummary, NormalizedMetricHistory, HistoryComparability,
    FiscalPeriodRequest, MetricComparison,
    ScopeAuthorizationProvenance,
)
from app.models import Company, FinancialFact
from app.sec_client import build_filing_url
from app.sec_parser import classify_period
from app import revenue_scope_authorizations as scope_permissions


class UnknownCompany(ValueError):
    pass


class UnknownMetric(ValueError):
    pass


def original_concept(fact):
    prefix = "SEC Company Facts API: "
    return fact.source[len(prefix):] if fact.source.startswith(prefix) else None


def period_kind(fact, definition):
    if fact.period_end is None:
        return None
    if definition.kind == "instant":
        return "instant" if fact.period_start is None else None
    if fact.period_start is None or fact.period_start > fact.period_end:
        return None
    kind = classify_period(fact.period_start.isoformat(), fact.period_end.isoformat())
    return kind if kind in {"quarter", "half_year", "nine_months", "annual"} else None


def usable(fact, definition):
    return (original_concept(fact) in definition.concepts
            and fact.unit == definition.source_unit and fact.value.is_finite()
            and fact.form in {"10-Q", "10-Q/A", "10-K", "10-K/A"}
            and fact.filed is not None and fact.period_end is not None
            and fact.filed >= fact.period_end
            and re.fullmatch(r"\d{10}-\d{2}-\d{6}", fact.accession_number or "")
            and period_kind(fact, definition) is not None)


def period_key(point):
    return point.period.kind, point.period.start, point.period.end


class FinancialMetrics:
    """Normalize an already loaded company dataset; shared by API and coverage audit."""

    def __init__(self, company, facts, *, authorization_evidence=()):
        self.company = company
        self.facts = [f for f in facts if f.company_cik == company.cik]
        # No production adapter infers XBRL context/dimensions from stored facts.
        self.authorization_evidence = tuple(authorization_evidence)
        self.selection_approvals = {}
        self.selection_rejections = {}
        self.base = {name: [] for name, definition in METRICS.items() if definition.kind != "derived"}
        # Dates of usable revenue observations establish reporting boundaries;
        # their economic scopes are resolved separately before selecting values.
        revenue = [f for f in self.facts if usable(f, METRICS["revenue"])]
        self.annual_bounds = sorted({(f.period_start, f.period_end) for f in revenue
                                     if period_kind(f, METRICS["revenue"]) == "annual"})
        self.ytd_starts = {f.period_start for f in revenue
                           if period_kind(f, METRICS["revenue"]) in {"half_year", "nine_months"}}
        self.bank_revenue = any(original_concept(f) == "RevenuesNetOfInterestExpense" for f in revenue)
        for name, definition in METRICS.items():
            if definition.kind == "derived":
                continue
            groups = {}
            for fact in self.facts:
                if usable(fact, definition):
                    key = (period_kind(fact, definition), fact.period_start, fact.period_end)
                    groups.setdefault(key, []).append(fact)
            for key, candidates in groups.items():
                eligible = candidates
                if name == "revenue":
                    eligible = self.revenue_candidates(candidates)
                    if not eligible:
                        point = self.missing(name, "Incompatible revenue scopes; no unambiguous canonical observation.", self.period(*key))
                        rejected = self.selection_rejections.get(key)
                        if rejected:
                            point.reason = f"Revenue selection authorization rejected: {rejected}."
                            candidates = self.authorization_facts(("revenue",), key[0], key[2])
                        point.alternatives = [self.source(name, f) for f in sorted(candidates, key=lambda f: f.id)]
                        self.base[name].append(point)
                        continue
                ranked = sorted(eligible, key=lambda f: (
                    f.filed, -definition.concepts.index(original_concept(f)),
                    (f.form.startswith("10-K") if key[0] == "annual" else f.form.startswith("10-Q")),
                    f.form.endswith("/A"), f.accession_number, f.id,
                ), reverse=True)
                chosen = ranked[0]
                self.base[name].append(NormalizedMetric(
                    metric=name, unit=definition.unit, status="available", value=chosen.value,
                    period=self.period(*key), provenance=[self.source(name, chosen)],
                    alternatives=[self.source(name, f) for f in ranked[1:]],
                    revenue_basis=REVENUE_CONCEPTS[original_concept(chosen)].basis if name == "revenue" else None,
                ))
                if name == "revenue":
                    approval = self.selection_approvals.get((key[0], key[1], key[2]))
                    if approval:
                        self.base[name][-1].scope_authorization = self.approval_provenance(approval)
                    self.base[name][-1].alternatives.extend(self.source(name, f) for f in sorted(candidates, key=lambda f: f.id) if f not in eligible)
            self.base[name].sort(key=lambda p: (p.period.end, p.period.start or date.min))

    def revenue_candidates(self, candidates):
        bases = {REVENUE_CONCEPTS[original_concept(f)].basis for f in candidates}
        if all(revenue_bases_compatible(left, right) for left in bases for right in bases):
            return candidates
        # Before/after interest expense are different canonical banking bases.
        # Neither recency nor a matching numeric value establishes equivalence.
        if "net_interest" in bases:
            return []
        if "total_revenue" in bases:
            return [f for f in candidates if REVENUE_CONCEPTS[original_concept(f)].basis == "total_revenue"]
        if not scope_permissions.REVENUE_SELECTION_AUTHORIZATIONS:
            return []
        # Only this otherwise ambiguous component branch admits a new selection
        # permission. Existing total/net-interest selection remains unchanged.
        first = candidates[0]
        kind = period_kind(first, METRICS["revenue"])
        raw = self.authorization_sources(("revenue",), kind, first.period_end)
        target = scope_permissions.SourceIdentity.from_fact(first).period_scope()
        decision = scope_permissions.authorize_selection(target, raw, self.authorization_evidence)
        if not decision.accepted:
            if decision.reason != "no_authorization":
                self.selection_rejections[(kind, first.period_start, first.period_end)] = decision.reason
            return []
        self.selection_approvals[(kind, first.period_start, first.period_end)] = decision.ref
        return [f for f in candidates if scope_permissions.SourceIdentity.from_fact(f) == decision.selected]

    def authorization_sources(self, names, kind, end):
        return tuple(scope_permissions.SourceIdentity.from_fact(f) for f in self.authorization_facts(names, kind, end))

    def authorization_facts(self, names, kind, end):
        # Include same-end/kind observations with changed starts, not just the
        # already selected rows. New fiscal boundaries must invalidate review.
        return [f for f in self.facts if any(usable(f, METRICS[n]) and period_kind(f, METRICS[n]) == kind
                                            and f.period_end == end for n in names)]

    @staticmethod
    def approval_provenance(ref):
        return ScopeAuthorizationProvenance(permission=ref.permission, approval_id=ref.approval_id, version=ref.version)

    def period(self, kind, start, end):
        period = FinancialPeriod(kind=kind, start=start, end=end)
        if kind == "annual":
            return period.model_copy(update={"fiscal_year": end.year, "fiscal_period": "FY",
                                             "fiscal_label_basis": "annual_period_end_year"})
        if kind == "instant":
            return period
        bounds = [(a, b) for a, b in self.annual_bounds if a <= start <= end <= b]
        if len(bounds) == 1:
            anchor, year = bounds[0][0], bounds[0][1].year
            basis = "observed_annual_boundary"
        elif bounds:
            return period  # Ambiguous overlapping fiscal boundaries.
        else:
            anchors = [a for a in self.ytd_starts if a <= start <= end and (end-a).days < 390]
            candidates = [a for a in anchors for _, b in self.annual_bounds
                          if a == b + timedelta(days=1)]
            if len(set(candidates)) != 1:
                return period
            anchor = candidates[0]
            # A previous full 52/53-week or calendar year supports a 364–371
            # day projection; transition/stub calendars do not. Near Dec/Jan
            # even that range spans two end years, so preserve uncertainty.
            prior_lengths = {(b-a).days+1 for a, b in self.annual_bounds if anchor == b + timedelta(days=1)}
            end_years = {(anchor + timedelta(days=days-1)).year for days in range(364, 372)}
            year = (next(iter(end_years)) if len(end_years) == 1
                    and all(364 <= days <= 371 for days in prior_lengths) else None)
            basis = "ytd_start_after_observed_annual_end"
            # Two consecutive full calendar years with the same month/day
            # boundaries distinguish a calendar schedule from a week calendar.
            # This retains Jan–Dec issuer labels without assuming every Jan
            # start ends in December or incrementing the previous end year.
            calendar_years = set()
            for a, b in self.annual_bounds:
                if anchor != b + timedelta(days=1) or (b-a).days+1 not in {365, 366}:
                    continue
                for previous_start, previous_end in self.annual_bounds:
                    if (previous_end + timedelta(days=1) == a
                            and (previous_end-previous_start).days+1 in {365, 366}
                            and (previous_start.month, previous_start.day) == (a.month, a.day)
                            and (previous_end.month, previous_end.day) == (b.month, b.day)):
                        calendar_years.add(anchor.year + ((b.month, b.day) < (anchor.month, anchor.day)))
            if len(calendar_years) == 1:
                year = calendar_years.pop()
                basis = "ytd_start_with_observed_calendar_year_pattern"
        if kind == "quarter":
            offsets = [i for i in range(4) if abs((start-anchor).days - 91*i) <= 14]
            label = f"Q{offsets[0]+1}" if len(offsets) == 1 else None
        else:
            label = {"half_year": "Q2", "nine_months": "Q3"}.get(kind) if start == anchor else None
        if label:
            period = period.model_copy(update={"fiscal_year": year, "fiscal_period": label,
                                               "fiscal_label_basis": basis})
        return period

    def source(self, name, fact):
        return FactProvenance(
            fact_id=fact.id, canonical_metric=name, company_cik=fact.company_cik,
            stored_metric=fact.metric, original_concept=original_concept(fact), value=fact.value,
            unit=fact.unit, period_start=fact.period_start, period_end=fact.period_end,
            stored_period_type=fact.period_type, source_fiscal_year=fact.fiscal_year,
            source_fiscal_period=fact.fiscal_period, frame=fact.frame, filed=fact.filed,
            form=fact.form, accession_number=fact.accession_number, source=fact.source,
            sec_url=build_filing_url(fact.company_cik, fact.accession_number), stored_at=fact.created_at,
        )

    def missing(self, name, reason, period=None, status="unavailable"):
        return NormalizedMetric(metric=name, unit=METRICS[name].unit, status=status,
                                reason=reason, period=period, formula=METRICS[name].formula)

    def observation(self, name, period):
        if self.bank_revenue and name in {"gross_profit", "gross_margin"}:
            return self.missing(name, "Gross profit/margin is not applicable to the observed net-interest revenue basis.", period, "not_applicable")
        if name in self.base:
            for point in self.base[name]:
                if (point.period.start == period.start and point.period.end == period.end
                        and point.period.kind == period.kind):
                    if name == "capital_expenditures" and point.value < 0:
                        return self.missing(name, "Negative payment fact conflicts with positive-outflow CapEx convention.", period)
                    return point
            return self.missing(name, "No compatible stored SEC fact for this period, concept and unit.", period)
        if name == "revenue_growth_yoy":
            current = self.observation("revenue", period)
            prior = [p for p in self.base["revenue"] if p.period.kind == period.kind
                     and p.period.start is not None and period.start is not None
                     and 357 <= (period.end-p.period.end).days <= 378
                     and 357 <= (period.start-p.period.start).days <= 378
                     and abs((period.end-period.start).days - (p.period.end-p.period.start).days) <= 9
                     and (not period.fiscal_period or not p.period.fiscal_period
                          or period.fiscal_period == p.period.fiscal_period)]
            if len(prior) != 1:
                return self.missing(name, "No unique comparable prior-year period.", period)
            if (current.status == "available" and prior[0].status == "available"
                    and not revenue_bases_compatible(current.revenue_basis, prior[0].revenue_basis)):
                return self.missing(name, "Current/prior revenue economic bases are not explicitly comparable.", period)
            return self.calculate(name, [current, prior[0]], period, ["current", "prior"])
        operands = {"gross_margin": ("gross_profit", "revenue"),
                    "operating_margin": ("operating_income", "revenue"),
                    "net_margin": ("net_income", "revenue"),
                    "free_cash_flow": ("operating_cash_flow", "capital_expenditures")}[name]
        return self.calculate(name, [self.observation(n, period) for n in operands], period, list(operands))

    def reviewed_gross_margin_scope(self, gross_profit, revenue):
        """Exact source-pair authorization; no ticker or global basis exception."""
        if len(gross_profit.provenance) != 1 or len(revenue.provenance) != 1:
            return False
        gp, rev = gross_profit.provenance[0], revenue.provenance[0]
        for coverage in GROSS_MARGIN_COVERAGE:
            if (self.company.cik == gp.company_cik == rev.company_cik == coverage.company_cik
                    and gp.accession_number == rev.accession_number == coverage.accession
                    and gp.period_start == rev.period_start == coverage.start
                    and gp.period_end == rev.period_end == coverage.end
                    and gp.unit == rev.unit == coverage.unit
                    and gp.form == rev.form == coverage.form
                    and gp.filed == rev.filed == coverage.filed
                    and gp.original_concept == coverage.gross_profit_concept
                    and rev.original_concept == coverage.revenue_concept
                    and gross_profit.value == gp.value == coverage.gross_profit
                    and revenue.value == rev.value == coverage.revenue):
                # Inspect raw eligible candidates, independently of row-ID ranking.
                # Calendar frames/fiscal labels are annotations, not extra scopes.
                for name, source in (("gross_profit", gp), ("revenue", rev)):
                    values = {f.value for f in self.facts
                              if usable(f, METRICS[name])
                              and original_concept(f) == source.original_concept
                              and f.accession_number == source.accession_number
                              and f.period_start == source.period_start
                              and f.period_end == source.period_end
                              and f.unit == source.unit
                              and f.form == source.form and f.filed == source.filed}
                    if values != {source.value}:
                        return False
                return True
        return False

    def calculate(self, name, operands, period, roles):
        denominator_approval = None
        if any(p.status != "available" for p in operands):
            return self.missing(name, "Missing or invalid compatible inputs.", period)
        first, second = operands
        if name == "gross_margin" and (
                first.provenance[0].accession_number != second.provenance[0].accession_number):
            return self.missing(name, "Gross profit and revenue must come from the same filing accession.", period)
        if name.endswith("margin"):
            concept = second.provenance[0].original_concept
            approved = REVENUE_CONCEPTS[concept].margin_denominator
            if name == "gross_margin" and not approved:
                approved = self.reviewed_gross_margin_scope(first, second)
            if name == "net_margin" and not approved and scope_permissions.DENOMINATOR_AUTHORIZATIONS:
                revenue = next((f for f in self.facts if f.id == second.provenance[0].fact_id), None)
                numerator = next((f for f in self.facts if f.id == first.provenance[0].fact_id), None)
                if revenue is not None and numerator is not None:
                    decision = scope_permissions.authorize_denominator(
                        name, scope_permissions.SourceIdentity.from_fact(revenue),
                        scope_permissions.SourceIdentity.from_fact(numerator),
                        self.authorization_sources(("revenue", "net_income"), period.kind, period.end),
                        self.authorization_evidence)
                    if decision.accepted:
                        approved, denominator_approval = True, decision.ref
                    elif decision.reason != "no_authorization":
                        rejected = self.missing(name, f"Revenue denominator authorization rejected: {decision.reason}.", period)
                        raw = self.authorization_facts(("revenue", "net_income"), period.kind, period.end)
                        rejected.alternatives = [self.source(n, f) for f in sorted(raw, key=lambda f: f.id)
                                                 for n in ("revenue", "net_income")
                                                 if original_concept(f) in METRICS[n].concepts]
                        return rejected
            if not approved or (self.bank_revenue and second.revenue_basis != "net_interest"):
                return self.missing(name, "Selected revenue scope does not establish an approved total/net-interest margin denominator.", period)
        if name != "free_cash_flow" and second.value <= 0:
            return self.missing(name, "Denominator must be positive; zero/negative revenue growth or margin bases are unavailable.", period)
        with localcontext() as context:
            context.prec = 28
            if name == "free_cash_flow":
                value = first.value - second.value
            elif name == "revenue_growth_yoy":
                value = (first.value - second.value) / second.value
            else:
                value = first.value / second.value
        return NormalizedMetric(
            metric=name, unit=METRICS[name].unit, status="available", value=value,
            period=period, formula=METRICS[name].formula,
            provenance=[source for p in operands for source in p.provenance],
            inputs=[MetricInput(role=role, metric=p.metric, value=p.value, unit=p.unit,
                                period=p.period, fact_ids=[s.fact_id for s in p.provenance], revenue_basis=p.revenue_basis)
                    for role, p in zip(roles, operands, strict=True)],
            scope_authorization=self.approval_provenance(denominator_approval) if denominator_approval else None,
        )

    def metric_periods(self, name, kind):
        """Shared normalized anchors; never infer a quarter from annual/YTD."""
        anchor_name = name if name in self.base else ("operating_cash_flow" if name == "free_cash_flow" else "revenue")
        return [p.period for p in self.base[anchor_name] if p.period.kind == kind]

    def reporting_periods(self, kind):
        anchors = self.metric_periods("revenue", kind)
        return anchors or [p.period for points in self.base.values() for p in points if p.period.kind == kind]

    def fiscal_observation(self, name, requested: FiscalPeriodRequest):
        """Exact requested normalized fiscal label, with existing vintage selection."""
        definition = METRICS[name]
        kind = "quarter" if requested.quarter else "annual"
        anchors = (self.reporting_periods(kind) if definition.kind == "instant"
                   else self.metric_periods(name, kind) or self.reporting_periods(kind))
        matches = {(p.kind, p.start, p.end): p for p in anchors
                   if p.fiscal_year == requested.fiscal_year
                   and p.fiscal_period == (f"Q{requested.quarter}" if requested.quarter else "FY")}
        if len(matches) != 1:
            reason = ("Multiple stored reporting periods have this fiscal label; selection is ambiguous."
                      if matches else "No unique stored reporting period with the requested fiscal year/quarter label. Annual, YTD and unlabeled periods are not substituted.")
            return self.missing(name, reason)
        period = next(iter(matches.values()))
        if definition.kind == "instant":
            period = self.period("instant", None, period.end)
        return self.observation(name, period)

    def compare_fiscal(self, name, earlier: FiscalPeriodRequest, later: FiscalPeriodRequest):
        """Read-only comparisons over canonical observations, including input scope."""
        left, right = self.fiscal_observation(name, earlier), self.fiscal_observation(name, later)
        result = MetricComparison(status="unavailable", earlier_period=earlier, later_period=later,
                                  earlier=left, later=right)
        if left.status != "available" or right.status != "available":
            result.status = "not_applicable" if "not_applicable" in {left.status, right.status} else "unavailable"
            result.reason = "; ".join(f"{request.label}: {point.reason}" for request, point in [(earlier, left), (later, right)] if point.status != "available")
            return result
        if (left.unit != right.unit or left.period.kind != right.period.kind
                or earlier.quarter != later.quarter
                or (earlier.fiscal_year, earlier.quarter or 0) >= (later.fiscal_year, later.quarter or 0)):
            result.reason = "Comparison requires chronological, matching annual or same fiscal-quarter bases and units."
            return result
        year_gap = later.fiscal_year - earlier.fiscal_year
        tolerance = 14 + year_gap // 4 + 1  # week calendars and accumulated leap days
        gaps = [(right.period.end-left.period.end).days]
        if left.period.start is not None and right.period.start is not None:
            gaps.append((right.period.start-left.period.start).days)
        if any(abs(gap - 365 * year_gap) > tolerance for gap in gaps):
            result.reason = "Fiscal reporting boundaries do not align across the requested years."
            return result
        if left.period.start is not None and right.period.start is not None:
            if abs((left.period.end-left.period.start).days - (right.period.end-right.period.start).days) > 9:
                result.reason = "Reporting durations are not comparable."
                return result
        if name == "revenue" and not revenue_bases_compatible(left.revenue_basis, right.revenue_basis):
            result.reason = "Earlier/later revenue economic bases are not explicitly comparable."
            return result
        left_inputs = {(i.role, i.metric, i.unit): i for i in left.inputs}
        right_inputs = {(i.role, i.metric, i.unit): i for i in right.inputs}
        if left_inputs.keys() != right_inputs.keys() or any(
            i.metric == "revenue" and not revenue_bases_compatible(i.revenue_basis, right_inputs[key].revenue_basis)
            for key, i in left_inputs.items()
        ):
            result.reason = "Derived input economic bases or roles are not explicitly comparable."
            return result
        with localcontext() as context:
            context.prec = 28
            result.absolute_change = right.value - left.value
            result.direction = "increase" if result.absolute_change > 0 else "decrease" if result.absolute_change < 0 else "no_change"
            result.status = "available"
            if left.unit == "ratio":
                result.percentage_status = "not_applicable"
                result.percentage_reason = "Ratio comparisons use percentage-point change, not percentage growth."
            elif name == "diluted_eps":
                result.percentage_status = "not_applicable"
                result.percentage_reason = "EPS is reported as filed; stock-split/restatement share-basis comparability is unverified."
            elif left.value <= 0:
                result.percentage_reason = "Percentage change requires a positive earlier value; zero/negative baselines use absolute change only."
            else:
                result.percentage_change = result.absolute_change / left.value
                result.percentage_status = "available"
        return result

    def history(self, name, kind="quarter", limit=40):
        if name not in METRICS:
            raise UnknownMetric(name)
        anchors = self.metric_periods(name, kind)
        observations = [self.observation(name, period) for period in anchors]
        history = observations[-limit:]
        status = "available" if any(p.status == "available" for p in history) else "unavailable"
        reason = None if status == "available" else "No compatible stored SEC observations or inputs."
        if self.bank_revenue and name in {"gross_profit", "gross_margin"}:
            status, reason = "not_applicable", "Observed net-interest revenue basis."
        return NormalizedMetricHistory(ticker=self.company.ticker, company_cik=self.company.cik,
                                       metric=name, unit=METRICS[name].unit, requested_period=kind,
                                       status=status, reason=reason, selection_policy=SELECTION_POLICY, history=history,
                                       comparability=HistoryComparability() if name == "diluted_eps" else None)

    def summary(self, kind="quarter"):
        anchors = self.reporting_periods(kind)
        anchor = max(anchors, key=lambda p: (p.end, p.start or date.min)) if anchors else None
        metrics = {}
        for name, definition in METRICS.items():
            if anchor is None:
                metrics[name] = self.missing(name, "No compatible stored reporting period.")
            elif definition.kind == "instant":
                metrics[name] = self.observation(name, self.period("instant", None, anchor.end))
            else:
                metrics[name] = self.observation(name, anchor)
        return NormalizedFinancialSummary(ticker=self.company.ticker, company_name=self.company.name,
                                          company_cik=self.company.cik, period=anchor, requested_period=kind,
                                          selection_policy=SELECTION_POLICY, metrics=metrics)


def load_financial_metrics(session, ticker):
    company = session.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise UnknownCompany(ticker)
    facts = list(session.scalars(select(FinancialFact).where(FinancialFact.company_cik == company.cik).order_by(FinancialFact.id)))
    return FinancialMetrics(company, facts)
