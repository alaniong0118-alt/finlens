"""Internal deterministic engine. No persistence, source admission or I/O.

Inputs are explicit immutable observations, not ORM-shaped objects. Eligibility
and source-specific permissions belong to the DB adapter in this increment.
No external/session source is admitted by constructing one of these records.
"""
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
from typing import Protocol

from app.financial_metric_registry import METRICS, REVENUE_CONCEPTS, revenue_bases_compatible


ANNUAL_COMPARISON_METRICS = (
    "revenue", "revenue_growth_yoy", "operating_margin", "net_margin",
    "operating_cash_flow", "capital_expenditures", "free_cash_flow",
    "gross_profit", "operating_income", "net_income", "gross_margin",
)


class UnknownMetric(ValueError):
    pass


SourceScalar = str | int | Decimal | date | datetime | None


@dataclass(frozen=True)
class Observation:
    reference: int  # Real DB row identity in this adapter; never a manufactured ID.
    concept: str | None
    value: Decimal
    unit: str
    start: date | None
    end: date | None
    kind: str | None
    filed: date | None
    form: str | None
    accession: str | None
    eligible_metrics: tuple[str, ...]
    # Opaque adapter projection: immutable scalar fields captured with the value.
    # The engine transports these fields without interpreting or admitting them.
    source_projection: tuple[tuple[str, SourceScalar], ...] = ()


@dataclass(frozen=True)
class Period:
    kind: str
    start: date | None
    end: date
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    fiscal_label_basis: str = "unknown"


@dataclass(frozen=True)
class ObservationRef:
    metric: str
    observation: Observation


@dataclass(frozen=True)
class Approval:
    permission: str
    approval_id: str
    version: int


@dataclass(frozen=True)
class ScopeDecision:
    accepted: bool
    reason: str
    ref: Approval | None = None
    selected: tuple[Observation, ...] = ()


class SourcePermissions(Protocol):
    """Internal DB operations, not caller-issued admission capabilities."""

    def select_revenue(self, candidates: tuple[Observation, ...]) -> ScopeDecision: ...
    def denominator(self, revenue: Observation, numerator: Observation, period: Period) -> ScopeDecision: ...
    def gross_margin(self, gross_profit: "Metric", revenue: "Metric") -> bool: ...
    def inventory(self, names: tuple[str, ...], kind: str, end: date) -> tuple[Observation, ...]: ...


@dataclass(frozen=True)
class Input:
    role: str
    metric: str
    value: Decimal
    unit: str
    period: Period
    references: tuple[ObservationRef, ...]
    revenue_basis: str | None = None


@dataclass(frozen=True)
class Metric:
    metric: str
    unit: str
    status: str
    value: Decimal | None = None
    reason: str | None = None
    period: Period | None = None
    formula: str | None = None
    provenance: tuple[ObservationRef, ...] = ()
    alternatives: tuple[ObservationRef, ...] = ()
    inputs: tuple[Input, ...] = ()
    revenue_basis: str | None = None
    scope_authorization: Approval | None = None


@dataclass(frozen=True)
class FiscalRequest:
    fiscal_year: int
    quarter: int | None = None

    @property
    def label(self):
        return f"Q{self.quarter} FY{self.fiscal_year}" if self.quarter else f"FY{self.fiscal_year}"


@dataclass(frozen=True)
class Comparison:
    earlier_period: FiscalRequest
    later_period: FiscalRequest
    earlier: Metric
    later: Metric
    status: str = "unavailable"
    reason: str | None = None
    absolute_change: Decimal | None = None
    percentage_change: Decimal | None = None
    percentage_status: str = "unavailable"
    percentage_reason: str | None = None
    direction: str | None = None
    formula: str = "absolute_change = later - earlier; percentage_change = (later - earlier) / earlier"


@dataclass(frozen=True)
class Annual:
    period: Period | None
    fiscal_years: tuple[int, ...]
    metrics: tuple[tuple[str, Metric], ...]
    reason: str | None


def period_key(point):
    return point.period.kind, point.period.start, point.period.end


class FinancialMetricEngine:
    """One algorithm over adapter-eligible observations and narrow permissions."""

    def __init__(self, observations: tuple[Observation, ...], permissions: SourcePermissions, *, budget=None):
        self._budget = budget
        self._tick()
        self.observations = observations
        self.permissions = permissions
        self.selection_approvals = {}
        self.selection_rejections = {}
        base = {name: [] for name, definition in self._walk(METRICS.items()) if definition.kind != "derived"}
        revenue = [f for f in self._walk(observations) if "revenue" in f.eligible_metrics]
        self.annual_bounds = tuple(sorted({(f.start, f.end) for f in self._walk(revenue) if f.kind == "annual"}))
        self.ytd_starts = frozenset(f.start for f in self._walk(revenue) if f.kind in {"half_year", "nine_months"})
        self.bank_revenue = any(f.concept == "RevenuesNetOfInterestExpense" for f in self._walk(revenue))
        for name, definition in self._walk(METRICS.items()):
            if definition.kind == "derived":
                continue
            groups = {}
            for fact in self._walk(observations):
                if name in fact.eligible_metrics:
                    groups.setdefault((fact.kind, fact.start, fact.end), []).append(fact)
            for key, candidates in self._walk(groups.items()):
                eligible = candidates
                if name == "revenue":
                    eligible = self.revenue_candidates(candidates)
                    if not eligible:
                        point = self.missing(name, "Incompatible revenue scopes; no unambiguous canonical observation.", self.period(*key))
                        rejected = self.selection_rejections.get(key)
                        if rejected:
                            point = replace(point, reason=f"Revenue selection authorization rejected: {rejected}.")
                            candidates = self.permissions.inventory(("revenue",), key[0], key[2])
                        point = replace(point, alternatives=tuple(self.source(name, f) for f in self._walk(sorted(candidates, key=lambda f: f.reference))))
                        base[name].append(point)
                        continue
                ranked = sorted(eligible, key=lambda f: (
                    f.filed, -definition.concepts.index(f.concept),
                    (f.form.startswith("10-K") if key[0] == "annual" else f.form.startswith("10-Q")),
                    f.form.endswith("/A"), f.accession, f.reference,
                ), reverse=True)
                chosen = ranked[0]
                alternatives = tuple(self.source(name, f) for f in self._walk(ranked[1:]))
                approval = None
                if name == "revenue":
                    approval = self.selection_approvals.get(key)
                    alternatives += tuple(self.source(name, f) for f in self._walk(sorted(candidates, key=lambda f: f.reference)) if not self._contains(eligible, f))
                base[name].append(Metric(
                    metric=name, unit=definition.unit, status="available", value=chosen.value,
                    period=self.period(*key), provenance=(self.source(name, chosen),), alternatives=alternatives,
                    revenue_basis=REVENUE_CONCEPTS[chosen.concept].basis if name == "revenue" else None,
                    scope_authorization=approval,
                ))
            base[name].sort(key=lambda p: (p.period.end, p.period.start or date.min))
        # Results and their nested references are immutable; the facade projects
        # its own public mutable Pydantic objects for existing DB consumers.
        self.base = {name: tuple(self._walk(points)) for name, points in self._walk(base.items())}

    def _tick(self):
        if self._budget is not None:
            self._budget.visit()

    def _walk(self, values):
        return self._budget.walk(values) if self._budget is not None else values

    def _contains(self, values, needle):
        if self._budget is None:
            return needle in values
        return any(value is needle or value == needle for value in self._walk(values))

    def revenue_candidates(self, candidates):
        bases = {REVENUE_CONCEPTS[f.concept].basis for f in self._walk(candidates)}
        if all(revenue_bases_compatible(left, right) for left in self._walk(bases) for right in self._walk(bases)):
            return candidates
        if "net_interest" in bases:
            return []
        if "total_revenue" in bases:
            return [f for f in self._walk(candidates) if REVENUE_CONCEPTS[f.concept].basis == "total_revenue"]
        decision = self.permissions.select_revenue(tuple(self._walk(candidates)))
        first = candidates[0]
        key = (first.kind, first.start, first.end)
        if not decision.accepted:
            if decision.reason != "no_authorization":
                self.selection_rejections[key] = decision.reason
            return []
        self.selection_approvals[key] = decision.ref
        return list(self._walk(decision.selected))

    def source(self, name, observation):
        self._tick()
        return ObservationRef(name, observation)

    def period(self, kind, start, end):
        self._tick()
        period = Period(kind=kind, start=start, end=end)
        if kind == "annual":
            return replace(period, fiscal_year=end.year, fiscal_period="FY",
                           fiscal_label_basis="annual_period_end_year")
        if kind == "instant":
            return period
        bounds = [(a, b) for a, b in self._walk(self.annual_bounds) if a <= start <= end <= b]
        if len(bounds) == 1:
            anchor, year = bounds[0][0], bounds[0][1].year
            basis = "observed_annual_boundary"
        elif bounds:
            return period  # Ambiguous overlapping fiscal boundaries.
        else:
            anchors = [a for a in self._walk(self.ytd_starts) if a <= start <= end and (end-a).days < 390]
            candidates = [a for a in self._walk(anchors) for _, b in self._walk(self.annual_bounds)
                          if a == b + timedelta(days=1)]
            if len(set(candidates)) != 1:
                return period
            anchor = candidates[0]
            # A previous full 52/53-week or calendar year supports a 364–371
            # day projection; transition/stub calendars do not. Near Dec/Jan
            # even that range spans two end years, so preserve uncertainty.
            prior_lengths = {(b-a).days+1 for a, b in self._walk(self.annual_bounds) if anchor == b + timedelta(days=1)}
            end_years = {(anchor + timedelta(days=days-1)).year for days in self._walk(range(364, 372))}
            year = (next(iter(end_years)) if len(end_years) == 1
                    and all(364 <= days <= 371 for days in self._walk(prior_lengths)) else None)
            basis = "ytd_start_after_observed_annual_end"
            # Two consecutive full calendar years with the same month/day
            # boundaries distinguish a calendar schedule from a week calendar.
            # This retains Jan–Dec issuer labels without assuming every Jan
            # start ends in December or incrementing the previous end year.
            calendar_years = set()
            for a, b in self._walk(self.annual_bounds):
                if anchor != b + timedelta(days=1) or (b-a).days+1 not in {365, 366}:
                    continue
                for previous_start, previous_end in self._walk(self.annual_bounds):
                    if (previous_end + timedelta(days=1) == a
                            and (previous_end-previous_start).days+1 in {365, 366}
                            and (previous_start.month, previous_start.day) == (a.month, a.day)
                            and (previous_end.month, previous_end.day) == (b.month, b.day)):
                        calendar_years.add(anchor.year + ((b.month, b.day) < (anchor.month, anchor.day)))
            if len(calendar_years) == 1:
                year = calendar_years.pop()
                basis = "ytd_start_with_observed_calendar_year_pattern"
        if kind == "quarter":
            offsets = [i for i in self._walk(range(4)) if abs((start-anchor).days - 91*i) <= 14]
            label = f"Q{offsets[0]+1}" if len(offsets) == 1 else None
        else:
            label = {"half_year": "Q2", "nine_months": "Q3"}.get(kind) if start == anchor else None
        if label:
            period = replace(period, fiscal_year=year, fiscal_period=label, fiscal_label_basis=basis)
        return period

    def missing(self, name, reason, period=None, status="unavailable"):
        self._tick()
        return Metric(metric=name, unit=METRICS[name].unit, status=status,
                                reason=reason, period=period, formula=METRICS[name].formula)

    def observation(self, name, period):
        self._tick()
        if self.bank_revenue and name in {"gross_profit", "gross_margin"}:
            return self.missing(name, "Gross profit/margin is not applicable to the observed net-interest revenue basis.", period, "not_applicable")
        if name in self.base:
            for point in self._walk(self.base[name]):
                if (point.period.start == period.start and point.period.end == period.end
                        and point.period.kind == period.kind):
                    if name == "capital_expenditures" and point.value < 0:
                        return self.missing(name, "Negative payment fact conflicts with positive-outflow CapEx convention.", period)
                    return point
            return self.missing(name, "No compatible stored SEC fact for this period, concept and unit.", period)
        if name == "revenue_growth_yoy":
            current = self.observation("revenue", period)
            prior = [p for p in self._walk(self.base["revenue"]) if p.period.kind == period.kind
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
        return self.calculate(name, [self.observation(n, period) for n in self._walk(operands)], period, list(operands))

    def calculate(self, name, operands, period, roles):
        self._tick()
        denominator_approval = None
        if any(p.status != "available" for p in self._walk(operands)):
            failures = []
            for role, operand in self._walk(zip(roles, operands, strict=True)):
                if operand.status != "available":
                    label = f"{role} {operand.metric}" if role in {"current", "prior"} else role
                    failures.append(f"{label.replace('_', ' ').capitalize()}: {operand.reason or 'No failure reason supplied.'}")
            return self.missing(name, "Missing or invalid compatible inputs. " + " ".join(failures), period)
        first, second = operands
        if name == "gross_margin" and (
                first.provenance[0].observation.accession != second.provenance[0].observation.accession):
            return self.missing(name, "Gross profit and revenue must come from the same filing accession.", period)
        if name.endswith("margin"):
            concept = second.provenance[0].observation.concept
            approved = REVENUE_CONCEPTS[concept].margin_denominator
            if name == "gross_margin" and not approved:
                approved = self.permissions.gross_margin(first, second)
            if name == "net_margin" and not approved:
                decision = self.permissions.denominator(second.provenance[0].observation,
                                                       first.provenance[0].observation, period)
                if decision.accepted:
                    approved, denominator_approval = True, decision.ref
                elif decision.reason != "no_authorization":
                    rejected = self.missing(name, f"Revenue denominator authorization rejected: {decision.reason}.", period)
                    raw = self.permissions.inventory(("revenue", "net_income"), period.kind, period.end)
                    return replace(rejected, alternatives=tuple(self.source(n, f) for f in self._walk(sorted(raw, key=lambda f: f.reference))
                                       for n in self._walk(("revenue", "net_income")) if f.concept in METRICS[n].concepts))
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
        return Metric(
            metric=name, unit=METRICS[name].unit, status="available", value=value,
            period=period, formula=METRICS[name].formula,
            provenance=tuple(source for p in self._walk(operands) for source in self._walk(p.provenance)),
            inputs=tuple(Input(role=role, metric=p.metric, value=p.value, unit=p.unit,
                                period=p.period, references=tuple(self._walk(p.provenance)), revenue_basis=p.revenue_basis)
                    for role, p in self._walk(zip(roles, operands, strict=True))),
            scope_authorization=denominator_approval if denominator_approval else None,
        )

    def metric_periods(self, name, kind):
        """Shared normalized anchors; never infer a quarter from annual/YTD."""
        anchor_name = name if name in self.base else ("operating_cash_flow" if name == "free_cash_flow" else "revenue")
        return [p.period for p in self._walk(self.base[anchor_name]) if p.period.kind == kind]

    def reporting_periods(self, kind):
        anchors = self.metric_periods("revenue", kind)
        return anchors or [p.period for points in self._walk(self.base.values()) for p in self._walk(points) if p.period.kind == kind]

    def fiscal_observation(self, name, requested: FiscalRequest):
        """Exact requested normalized fiscal label, with existing vintage selection."""
        definition = METRICS[name]
        kind = "quarter" if requested.quarter else "annual"
        anchors = (self.reporting_periods(kind) if definition.kind == "instant"
                   else self.metric_periods(name, kind) or self.reporting_periods(kind))
        matches = {(p.kind, p.start, p.end): p for p in self._walk(anchors)
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

    def compare_fiscal(self, name, earlier: FiscalRequest, later: FiscalRequest):
        """Read-only comparisons over canonical observations, including input scope."""
        left, right = self.fiscal_observation(name, earlier), self.fiscal_observation(name, later)
        result = Comparison(earlier_period=earlier, later_period=later, earlier=left, later=right)
        if left.status != "available" or right.status != "available":
            status = "not_applicable" if "not_applicable" in {left.status, right.status} else "unavailable"
            reason = "; ".join(f"{request.label}: {point.reason}"
                               for request, point in self._walk([(earlier, left), (later, right)])
                               if point.status != "available")
            return replace(result, status=status, reason=reason)
        if (left.unit != right.unit or left.period.kind != right.period.kind
                or earlier.quarter != later.quarter
                or (earlier.fiscal_year, earlier.quarter or 0) >= (later.fiscal_year, later.quarter or 0)):
            return replace(result, reason="Comparison requires chronological, matching annual or same fiscal-quarter bases and units.")
        year_gap = later.fiscal_year - earlier.fiscal_year
        tolerance = 14 + year_gap // 4 + 1  # week calendars and accumulated leap days
        gaps = [(right.period.end - left.period.end).days]
        if left.period.start is not None and right.period.start is not None:
            gaps.append((right.period.start - left.period.start).days)
        if any(abs(gap - 365 * year_gap) > tolerance for gap in self._walk(gaps)):
            return replace(result, reason="Fiscal reporting boundaries do not align across the requested years.")
        if left.period.start is not None and right.period.start is not None:
            if abs((left.period.end - left.period.start).days - (right.period.end - right.period.start).days) > 9:
                return replace(result, reason="Reporting durations are not comparable.")
        if name == "revenue" and not revenue_bases_compatible(left.revenue_basis, right.revenue_basis):
            return replace(result, reason="Earlier/later revenue economic bases are not explicitly comparable.")
        left_inputs = {(i.role, i.metric, i.unit): i for i in self._walk(left.inputs)}
        right_inputs = {(i.role, i.metric, i.unit): i for i in self._walk(right.inputs)}
        if left_inputs.keys() != right_inputs.keys() or any(
            i.metric == "revenue" and not revenue_bases_compatible(i.revenue_basis, right_inputs[key].revenue_basis)
            for key, i in self._walk(left_inputs.items())
        ):
            return replace(result, reason="Derived input economic bases or roles are not explicitly comparable.")
        with localcontext() as context:
            context.prec = 28
            result = replace(result, absolute_change=right.value - left.value)
            direction = "increase" if result.absolute_change > 0 else "decrease" if result.absolute_change < 0 else "no_change"
            result = replace(result, direction=direction, status="available")
            if left.unit == "ratio":
                result = replace(result, percentage_status="not_applicable",
                                 percentage_reason="Ratio comparisons use percentage-point change, not percentage growth.")
            elif name == "diluted_eps":
                result = replace(result, percentage_status="not_applicable",
                                 percentage_reason="EPS is reported as filed; stock-split/restatement share-basis comparability is unverified.")
            elif left.value <= 0:
                result = replace(result, percentage_reason="Percentage change requires a positive earlier value; zero/negative baselines use absolute change only.")
            else:
                result = replace(result, percentage_change=result.absolute_change / left.value, percentage_status="available")
        return result

    def annual_comparison(self, fiscal_year=None):
        """Discover observed labels or resolve one exact annual reporting window.

        Fiscal labels follow period(), including fiscal end-year labeling for week
        calendars. Filing-context FY annotations are not reporting-period labels.
        No latest-period or per-metric period fallback is permitted here.
        """
        # Comparison coverage is the union of its metrics' existing annual anchors.
        # Revenue-first reporting_periods remains unchanged for other endpoints.
        anchors = [p for name in self._walk(ANNUAL_COMPARISON_METRICS)
                   for p in self._walk(self.metric_periods(name, "annual"))]
        years = sorted({p.fiscal_year for p in self._walk(anchors)
                        if p.fiscal_year is not None and 1900 <= p.fiscal_year <= 2099}, reverse=True)
        anchor, reason, metrics = None, None, {}
        if fiscal_year is not None:
            matches = {(p.start, p.end): p for p in self._walk(anchors)
                       if p.fiscal_year == fiscal_year and p.fiscal_period == "FY"}
            if len(matches) == 1:
                anchor = next(iter(matches.values()))
                metrics = {name: self.observation(name, anchor) for name in self._walk(ANNUAL_COMPARISON_METRICS)}
            else:
                reason = ("Multiple stored annual reporting windows have this fiscal end-year; selection is ambiguous."
                          if matches else "No stored annual reporting window for the requested fiscal end-year. Other years, quarterly and YTD observations are not substituted.")
                metrics = {name: self.missing(name, reason) for name in self._walk(ANNUAL_COMPARISON_METRICS)}
        return Annual(anchor, tuple(self._walk(years)), tuple(self._walk(metrics.items())), reason)
