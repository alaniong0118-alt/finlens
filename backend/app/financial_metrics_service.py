"""Read-only financial normalization. No SEC client requests or AI dependency."""
from datetime import date
import re

from sqlalchemy import select
from app.activation_lifecycle import financial_reader

from app.financial_metric_registry import METRICS, SELECTION_POLICY, GROSS_MARGIN_COVERAGE
from app.financial_metric_schemas import (
    FactProvenance, FinancialPeriod, MetricInput, NormalizedMetric,
    NormalizedFinancialSummary, NormalizedMetricHistory, HistoryComparability,
    FiscalPeriodRequest, MetricComparison,
    ScopeAuthorizationProvenance,
    AnnualFinancialComparison,
)
from app.models import Company, FinancialFact
from app.sec_urls import build_filing_url
from app.sec_parser import classify_period
from app import revenue_scope_authorizations as scope_permissions
from app import financial_metric_engine as engine
from app.financial_metric_engine import ANNUAL_COMPARISON_METRICS, UnknownMetric


class UnknownCompany(ValueError):
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
    """DB compatibility facade over the shared deterministic engine.

    Original rows remain available for authorization and Insights diagnostics.
    Conversion does not infer dimensional, accounting or source admission.
    """

    @financial_reader
    def __init__(self, company, facts, *, authorization_evidence=(), budget=None):
        self._budget = budget
        self._tick()
        self.company = company
        self.facts = [f for f in self._walk(facts) if f.company_cik == company.cik]
        self.authorization_evidence = tuple(self._walk(authorization_evidence))
        self._rows = {}
        observations = []
        for fact in self._walk(self.facts):
            self._rows[fact.id] = fact
            eligible = tuple(name for name, definition in self._walk(METRICS.items())
                             if definition.kind != "derived" and usable(fact, definition))
            if eligible:
                # Capture the complete source once, then derive engine values and
                # dates from that same projection rather than rereading the row.
                observations.append(self._capture_source(self.source(eligible[0], fact), eligible))
            else:
                observations.append(engine.Observation(fact.id, original_concept(fact), fact.value,
                    fact.unit, fact.period_start, fact.period_end, None, fact.filed, fact.form,
                    fact.accession_number, eligible))
        self._observations = {o.reference: o for o in self._walk(observations)}
        self.selection_approvals = {}  # Keep the DB evaluator's original ApprovalRef values.
        self._engine = engine.FinancialMetricEngine(tuple(self._walk(observations)), _DBPermissions(self), budget=budget)
        self.selection_rejections = self._engine.selection_rejections
        self.annual_bounds = list(self._walk(self._engine.annual_bounds))
        self.ytd_starts = set(self._walk(self._engine.ytd_starts))
        self.bank_revenue = self._engine.bank_revenue
        self.base = {name: [self._project(p) for p in self._walk(points)]
                     for name, points in self._walk(self._engine.base.items())}

    def _public_period(self, period):
        self._tick()
        return None if period is None else FinancialPeriod(kind=period.kind, start=period.start,
            end=period.end, fiscal_year=period.fiscal_year, fiscal_period=period.fiscal_period,
            fiscal_label_basis=period.fiscal_label_basis)

    def _internal_period(self, period):
        self._tick()
        return None if period is None else engine.Period(period.kind, period.start, period.end,
            period.fiscal_year, period.fiscal_period, period.fiscal_label_basis)

    def _capture_source(self, source, eligible_metrics=()):
        self._tick()
        kind = None
        if eligible_metrics:
            kind = ("instant" if source.period_start is None else
                    classify_period(source.period_start.isoformat(), source.period_end.isoformat()))
        return engine.Observation(source.fact_id, source.original_concept, source.value, source.unit,
            source.period_start, source.period_end, kind, source.filed, source.form,
            source.accession_number, eligible_metrics,
            tuple(self._walk(source.model_dump(mode="python").items())))

    def _project_source(self, ref):
        self._tick()
        if not ref.observation.source_projection:
            raise ValueError("Missing captured source projection.")
        fields = dict(self._walk(ref.observation.source_projection))
        fields["canonical_metric"] = ref.metric
        return FactProvenance(**fields)

    def _project(self, point):
        self._tick()
        return NormalizedMetric(metric=point.metric, unit=point.unit, status=point.status,
            value=point.value, reason=point.reason, period=self._public_period(point.period),
            formula=point.formula,
            provenance=[self._project_source(r) for r in self._walk(point.provenance)],
            alternatives=[self._project_source(r) for r in self._walk(point.alternatives)],
            inputs=[MetricInput(role=i.role, metric=i.metric, value=i.value, unit=i.unit,
                period=self._public_period(i.period), fact_ids=[r.observation.reference for r in self._walk(i.references)],
                revenue_basis=i.revenue_basis) for i in self._walk(point.inputs)],
            revenue_basis=point.revenue_basis,
            scope_authorization=self.approval_provenance(point.scope_authorization) if point.scope_authorization else None)

    def _unproject(self, point):
        self._tick()
        def refs(sources):
            # A matching ID does not replace submitted accession/concept/value or
            # any other source field before the original calculation checks.
            return tuple(engine.ObservationRef(s.canonical_metric, self._capture_source(s))
                         for s in self._walk(sources))
        return engine.Metric(metric=point.metric, unit=point.unit, status=point.status,
            value=point.value, reason=point.reason, period=self._internal_period(point.period), formula=point.formula,
            provenance=refs(point.provenance), alternatives=refs(point.alternatives),
            # This conversion serves calculate(), whose historical behavior uses
            # immediate operands/provenance, not their previous input ancestry.
            revenue_basis=point.revenue_basis,
            scope_authorization=_approval(point.scope_authorization))

    @financial_reader
    def period(self, kind, start, end):
        return self._public_period(self._engine.period(kind, start, end))

    @financial_reader
    def missing(self, name, reason, period=None, status="unavailable"):
        return self._project(self._engine.missing(name, reason, self._internal_period(period), status))

    @financial_reader
    def observation(self, name, period):
        return self._project(self._engine.observation(name, self._internal_period(period)))

    @financial_reader
    def calculate(self, name, operands, period, roles):
        return self._project(self._engine.calculate(name, tuple(self._unproject(p) for p in self._walk(operands)),
                                                   self._internal_period(period), roles))

    @financial_reader
    def metric_periods(self, name, kind):
        return [self._public_period(p) for p in self._walk(self._engine.metric_periods(name, kind))]

    @financial_reader
    def reporting_periods(self, kind):
        return [self._public_period(p) for p in self._walk(self._engine.reporting_periods(kind))]

    @financial_reader
    def fiscal_observation(self, name, requested: FiscalPeriodRequest):
        return self._project(self._engine.fiscal_observation(name, engine.FiscalRequest(requested.fiscal_year, requested.quarter)))

    @financial_reader
    def compare_fiscal(self, name, earlier: FiscalPeriodRequest, later: FiscalPeriodRequest):
        result = self._engine.compare_fiscal(name, engine.FiscalRequest(earlier.fiscal_year, earlier.quarter),
                                            engine.FiscalRequest(later.fiscal_year, later.quarter))
        self._tick()
        return MetricComparison(status=result.status, reason=result.reason, earlier_period=earlier, later_period=later,
            earlier=self._project(result.earlier), later=self._project(result.later),
            absolute_change=result.absolute_change, percentage_change=result.percentage_change,
            percentage_status=result.percentage_status, percentage_reason=result.percentage_reason,
            direction=result.direction, formula=result.formula)

    @financial_reader
    def annual_comparison(self, fiscal_year=None):
        result = self._engine.annual_comparison(fiscal_year)
        return AnnualFinancialComparison(ticker=self.company.ticker, company_name=self.company.name,
            company_cik=self.company.cik, period=self._public_period(result.period), selection_policy=SELECTION_POLICY,
            metrics={name: self._project(p) for name, p in self._walk(result.metrics)},
            requested_fiscal_year=fiscal_year, fiscal_years=list(self._walk(result.fiscal_years)), period_reason=result.reason)

    @financial_reader
    def revenue_candidates(self, candidates):
        selected = self._engine.revenue_candidates([self._observations[f.id] for f in self._walk(candidates)])
        return [self._rows[o.reference] for o in self._walk(selected)]

    def _tick(self):
        if self._budget is not None:
            self._budget.visit()

    def _walk(self, values):
        return self._budget.walk(values) if self._budget is not None else values

    def _contains(self, values, needle):
        if self._budget is None:
            return needle in values
        return any(value is needle or value == needle for value in self._walk(values))

    @financial_reader
    def authorization_sources(self, names, kind, end):
        return tuple(scope_permissions.SourceIdentity.from_fact(f) for f in self._walk(self.authorization_facts(names, kind, end)))

    @financial_reader
    def authorization_facts(self, names, kind, end):
        # Include same-end/kind observations with changed starts, not just the
        # already selected rows. New fiscal boundaries must invalidate review.
        return [f for f in self._walk(self.facts) if any(usable(f, METRICS[n]) and period_kind(f, METRICS[n]) == kind
                                            and f.period_end == end for n in self._walk(names))]

    @staticmethod
    def approval_provenance(ref):
        return ScopeAuthorizationProvenance(permission=ref.permission, approval_id=ref.approval_id, version=ref.version)

    @financial_reader
    def source(self, name, fact):
        self._tick()
        return FactProvenance(
            fact_id=fact.id, canonical_metric=name, company_cik=fact.company_cik,
            stored_metric=fact.metric, original_concept=original_concept(fact), value=fact.value,
            unit=fact.unit, period_start=fact.period_start, period_end=fact.period_end,
            stored_period_type=fact.period_type, source_fiscal_year=fact.fiscal_year,
            source_fiscal_period=fact.fiscal_period, frame=fact.frame, filed=fact.filed,
            form=fact.form, accession_number=fact.accession_number, source=fact.source,
            sec_url=build_filing_url(fact.company_cik, fact.accession_number), stored_at=fact.created_at,
        )

    @financial_reader
    def reviewed_gross_margin_scope(self, gross_profit, revenue):
        """Exact source-pair authorization; no ticker or global basis exception."""
        if len(gross_profit.provenance) != 1 or len(revenue.provenance) != 1:
            return False
        gp, rev = gross_profit.provenance[0], revenue.provenance[0]
        for coverage in self._walk(GROSS_MARGIN_COVERAGE):
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
                for name, source in self._walk((("gross_profit", gp), ("revenue", rev))):
                    values = {f.value for f in self._walk(self.facts)
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

    @financial_reader
    def history(self, name, kind="quarter", limit=40):
        if name not in METRICS:
            raise UnknownMetric(name)
        anchors = self.metric_periods(name, kind)
        observations = [self.observation(name, period) for period in self._walk(anchors)]
        history = observations[-limit:]
        status = "available" if any(p.status == "available" for p in self._walk(history)) else "unavailable"
        reason = None if status == "available" else "No compatible stored SEC observations or inputs."
        if self.bank_revenue and name in {"gross_profit", "gross_margin"}:
            status, reason = "not_applicable", "Observed net-interest revenue basis."
        return NormalizedMetricHistory(ticker=self.company.ticker, company_cik=self.company.cik,
                                       metric=name, unit=METRICS[name].unit, requested_period=kind,
                                       status=status, reason=reason, selection_policy=SELECTION_POLICY, history=history,
                                       comparability=HistoryComparability() if name == "diluted_eps" else None)

    @financial_reader
    def summary(self, kind="quarter"):
        anchors = self.reporting_periods(kind)
        anchor = max(anchors, key=lambda p: (p.end, p.start or date.min)) if anchors else None
        metrics = {}
        for name, definition in self._walk(METRICS.items()):
            if anchor is None:
                metrics[name] = self.missing(name, "No compatible stored reporting period.")
            elif definition.kind == "instant":
                metrics[name] = self.observation(name, self.period("instant", None, anchor.end))
            else:
                metrics[name] = self.observation(name, anchor)
        return NormalizedFinancialSummary(ticker=self.company.ticker, company_name=self.company.name,
                                          company_cik=self.company.cik, period=anchor, requested_period=kind,
                                          selection_policy=SELECTION_POLICY, metrics=metrics)


def _approval(ref):
    return None if ref is None else engine.Approval(ref.permission, ref.approval_id, ref.version)


class _DBPermissions:
    """Source-specific operations retain the complete original eligible rows."""

    def __init__(self, facade):
        self.facade = facade

    def inventory(self, names, kind, end):
        f = self.facade
        # Rejection diagnostics historically project the original rows at the
        # time of that operation, rather than an earlier selected/base snapshot.
        return tuple(f._capture_source(f.source(names[0], row),
                     tuple(name for name in f._walk(names) if usable(row, METRICS[name])))
                     for row in f._walk(f.authorization_facts(names, kind, end)))

    def select_revenue(self, candidates):
        if not scope_permissions.REVENUE_SELECTION_AUTHORIZATIONS:
            return engine.ScopeDecision(False, "no_authorization")
        f = self.facade
        first = f._rows[candidates[0].reference]
        kind = period_kind(first, METRICS["revenue"])
        raw = f.authorization_sources(("revenue",), kind, first.period_end)
        decision = scope_permissions.authorize_selection(scope_permissions.SourceIdentity.from_fact(first).period_scope(),
                                                          raw, f.authorization_evidence)
        selected = tuple(o for o in f._walk(candidates)
                         if decision.accepted and scope_permissions.SourceIdentity.from_fact(f._rows[o.reference]) == decision.selected)
        if decision.accepted:
            f.selection_approvals[(kind, first.period_start, first.period_end)] = decision.ref
        return engine.ScopeDecision(decision.accepted, decision.reason, _approval(decision.ref), selected)

    def denominator(self, revenue, numerator, period):
        if not scope_permissions.DENOMINATOR_AUTHORIZATIONS:
            return engine.ScopeDecision(False, "no_authorization")
        f = self.facade
        revenue_row = next((row for row in f._walk(f.facts) if row.id == revenue.reference), None)
        numerator_row = next((row for row in f._walk(f.facts) if row.id == numerator.reference), None)
        if revenue_row is None or numerator_row is None:
            return engine.ScopeDecision(False, "no_authorization")
        decision = scope_permissions.authorize_denominator("net_margin",
            scope_permissions.SourceIdentity.from_fact(revenue_row),
            scope_permissions.SourceIdentity.from_fact(numerator_row),
            f.authorization_sources(("revenue", "net_income"), period.kind, period.end), f.authorization_evidence)
        return engine.ScopeDecision(decision.accepted, decision.reason, _approval(decision.ref))

    def gross_margin(self, gross_profit, revenue):
        f = self.facade
        return f.reviewed_gross_margin_scope(f._project(gross_profit), f._project(revenue))


@financial_reader
def load_financial_metrics(session, ticker):
    company = session.scalar(select(Company).where(Company.ticker == ticker.upper()))
    if company is None:
        raise UnknownCompany(ticker)
    facts = list(session.scalars(select(FinancialFact).where(FinancialFact.company_cik == company.cik).order_by(FinancialFact.id)))
    from app.sec_evidence_adapter import load_production_evidence
    return FinancialMetrics(company, facts, authorization_evidence=load_production_evidence(session, company.cik, facts))
