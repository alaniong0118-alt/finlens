"""Bounded, read-only composition over the existing canonical financial service."""
from collections import Counter
from copy import deepcopy
import re
from types import SimpleNamespace

from sqlalchemy import String, case, cast, func, literal, or_, select

from app import revenue_scope_authorizations as authorizations
from app import sec_evidence_adapter as adapter
from app.activation_lifecycle import financial_reader
from app.financial_metric_registry import METRICS as DEFINITIONS, REVENUE_CONCEPTS
from app.financial_metric_schemas import FiscalPeriodRequest
from app.financial_metrics_service import (
    ANNUAL_COMPARISON_METRICS, FinancialMetrics, UnknownCompany, original_concept, period_kind, usable,
)
from app.financial_insights_contract import (
    DEPENDENCIES, HEADLINE, LIMITS, METRICS, Budget, Graph, bounded_json, checked_text,
    delta_display, exact_decimal, ordered, percentage_display, precision_hidden, reference, require,
    statement, text_value, transition, validate_statement_limits, validate_statements,
)
from app.financial_insights_schemas import InsightsResponse
from app.models import Company, CompanyRefreshState, FinancialFact

FACT_FIELDS = ("id", "company_cik", "metric", "value", "unit", "period_start", "period_end",
               "period_type", "fiscal_year", "fiscal_period", "form", "filed", "accession_number",
               "frame", "source", "created_at")
SLOTS = (*METRICS, "capital_expenditures")
LABELS = dict(revenue="Revenue", operating_income="Operating income", net_income="Net income",
    operating_margin="Operating margin", net_margin="Net margin", operating_cash_flow="Operating cash flow",
    free_cash_flow="Free cash flow", capital_expenditures="Capital expenditures")


def registry_guard(expected=None):
    # Read the owning modules on every check; never capture imported registry values.
    registries = (authorizations.REVENUE_SELECTION_AUTHORIZATIONS,
                  authorizations.DENOMINATOR_AUTHORIZATIONS,
                  authorizations.AUTHORIZATION_WITHDRAWALS, adapter.PRODUCTION_EVIDENCE_POLICIES)
    require(all(type(r) is tuple and not r for r in registries), "INSIGHTS_CONFIGURATION_UNSUPPORTED")
    if expected is not None:
        require(all(a is b for a, b in zip(registries, expected, strict=True)),
                "INSIGHTS_CONFIGURATION_UNSUPPORTED")
    return registries


def field_limit(name):
    return 400 if name in {"metric", "source"} else 64 if name in {
        "period_start", "period_end", "filed", "created_at"} else 128


def row_stats(row):
    size = 512
    for name in FACT_FIELDS:
        rendered = text_value(getattr(row, name))
        checked_text(rendered, field_limit(name))
        size += len(rendered.encode("utf-8"))
    return size


def preflight_query(cik):
    """LIMIT is inside the aggregate; no fact value is transferred to Python."""
    rendered = []
    for name in FACT_FIELDS:
        col = getattr(FinancialFact, name)
        if name == "created_at":
            value = func.to_char(col, 'YYYY-MM-DD"T"HH24:MI:SS.US')
        elif name in {"period_start", "period_end", "filed"}:
            value = func.to_char(col, "YYYY-MM-DD")
        else:
            value = cast(col, String)
        rendered.append(func.coalesce(value, literal("")).label(name))
    sentinel = select(*rendered).where(FinancialFact.company_cik == cik).order_by(
        FinancialFact.id).limit(LIMITS["facts"]+1).subquery("insights_sentinel")
    lengths = {n: func.octet_length(func.convert_to(sentinel.c[n], "UTF8")) for n in FACT_FIELDS}
    too_long = or_(*(lengths[n] > field_limit(n) for n in FACT_FIELDS))
    return select(func.count().label("count"),
                  func.coalesce(func.sum(512 + sum(lengths.values())), 0).label("bytes"),
                  func.coalesce(func.max(case((too_long, 1), else_=0)), 0).label("invalid"))


def bounded_load(session, ticker, pin, budget):
    config = registry_guard()
    budget.deadline()
    company_row = session.execute(select(Company.id, Company.ticker, Company.name, Company.cik, Company.exchange,
        CompanyRefreshState.data_version, CompanyRefreshState.facts_version, CompanyRefreshState.evidence_version)
        .join(CompanyRefreshState, CompanyRefreshState.company_cik == Company.cik)
        .where(Company.ticker == ticker)).mappings().one_or_none()
    if company_row is None:
        raise UnknownCompany(ticker)
    company = SimpleNamespace(**{n: company_row[n] for n in ("id", "ticker", "name", "cik", "exchange")})
    checked_text(company.name, 800)
    require(company.ticker == ticker and len(company.cik) == 10 and company.cik.isascii() and company.cik.isdigit())
    versions = tuple(company_row[n] for n in ("data_version", "facts_version", "evidence_version"))
    require(all(type(v) is int and 0 <= v <= 9007199254740991 for v in versions))
    require(versions[0] == pin and max(versions[1:]) <= pin)
    stats = session.execute(preflight_query(company.cik)).mappings().one()
    require(all(type(stats[k]) is int and stats[k] >= 0 for k in ("count", "bytes", "invalid")),
            "INSIGHTS_EVIDENCE_INCOMPLETE")
    budget.check("facts", stats["count"])
    budget.check("input_bytes", stats["bytes"])
    require(stats["invalid"] == 0, "INSIGHTS_RESOURCE_LIMIT")
    # Regular client cursor: LIMIT/byte preflight bounds transfer. Do not use
    # yield_per/stream_results, whose named cursor FETCH calls escape do_execute.
    query = select(*(getattr(FinancialFact, n) for n in FACT_FIELDS)).where(
        FinancialFact.company_cik == company.cik).order_by(FinancialFact.id).limit(LIMITS["facts"]+1)
    result = session.execute(query.execution_options(stream_results=False)).mappings()
    facts, size, previous = [], 0, None
    try:
        while True:
            budget.deadline()
            batch = result.fetchmany(128)
            if not batch:
                break
            require(len(batch) <= 128, "INSIGHTS_EVIDENCE_INCOMPLETE")
            for row in budget.walk(batch):
                budget.check("facts", len(facts)+1)
                fact = SimpleNamespace(**dict(row))
                require(fact.company_cik == company.cik and type(fact.id) is int
                        and (previous is None or fact.id > previous), "INSIGHTS_EVIDENCE_INCOMPLETE")
                previous = fact.id
                size += row_stats(fact)
                budget.check("input_bytes", size)
                facts.append(fact)
    finally:
        result.close()
    require(len(facts) == stats["count"] and size == stats["bytes"], "INSIGHTS_EVIDENCE_INCOMPLETE")
    registry_guard(config)
    return company, versions, facts, config


def admit_input(facts, years, budget):
    """Operational ceilings only; no alternative finance selection."""
    budget.check("facts", len(facts))
    groups, windows = Counter(), set()
    eligible, size = 0, 0
    for fact in budget.walk(facts):
        size += row_stats(fact)
        budget.check("input_bytes", size)
        for name, definition in budget.walk(DEFINITIONS.items()):
            if definition.kind == "derived" or not usable(fact, definition):
                continue
            eligible += 1
            budget.check("eligible", eligible)
            kind = period_kind(fact, definition)
            key = (name, kind, fact.period_start, fact.period_end)
            groups[key] += 1
            budget.check("group", groups[key])
            if name in ANNUAL_COMPARISON_METRICS and kind == "annual":
                windows.add((fact.period_start, fact.period_end))
                budget.check("windows", len(windows))
    for year in budget.walk(years):
        budget.check("year_windows", sum(1 for a, b in budget.walk(windows) if b.year == year))


def window_key(period):
    return None if period is None else f"{period.start}/{period.end}/{period.kind}"


def source_identity(fact):
    return (fact.company_cik, fact.source, original_concept(fact), fact.period_start, fact.period_end,
            fact.unit, fact.accession_number, fact.form, fact.filed)


class Composition:
    def __init__(self, model, versions, earlier, later, budget):
        self.model, self.budget = model, budget
        self.years = {"earlier": earlier, "later": later}
        self.versions = versions
        self.scope = f"{model.company.cik}:{':'.join(map(str, versions))}:{earlier}:{later}"
        self.graph = Graph(self.scope, budget)
        self.annual = {side: model.annual_comparison(year) for side, year in self.years.items()}
        self.observations, self.admitted, self.refs = {}, {}, {}
        self.facts = {f.id: f for f in budget.walk(model.facts)}
        require(len(self.facts) == len(model.facts), "INSIGHTS_EVIDENCE_INCOMPLETE")
        self.source_ids, self.candidates = set(), 0
        self.rejections, self.operands = 0, 0
        self.comparisons = {}
        self.failure_reasons = {}

    def ref(self, category, kind, metric=None, side=None, role=None, suffix=None, period=None):
        if period is None and side is not None:
            period = self.annual[side].period
        return reference(self.scope, category, kind, metric, side, role, window_key(period), suffix)

    def raw_source(self, fact, category):
        if fact.id not in self.source_ids:
            self.budget.check("sources", len(self.source_ids)+1)
            self.source_ids.add(fact.id)
        ref = self.ref(category, "source", suffix=str(fact.id))
        data = {n: None if getattr(fact, n) is None else text_value(getattr(fact, n)) for n in FACT_FIELDS}
        data["original_concept"] = original_concept(fact)
        # Invalid accession metadata is retained; never manufacture a source URL.
        data["sec_url"] = None
        if fact.accession_number and re.fullmatch(r"\d{10}-\d{2}-\d{6}", fact.accession_number):
            from app.sec_urls import build_filing_url
            data["sec_url"] = checked_text(build_filing_url(fact.company_cik, fact.accession_number), 192)
        return self.graph.put(ref, data)

    def reject(self, metric, side, code, reason, edges=()):
        self.rejections += 1
        self.budget.check("rejections", self.rejections)
        ref = self.ref("D", "rejection", metric, side, suffix=code)
        return self.graph.put(ref, {"code": code, "reason": checked_text(reason, 1024)}, edges)

    def candidates_for(self, metric, side):
        definition = DEFINITIONS[metric]
        point = self.observations[(metric, side)]
        referenced = {p.fact_id for p in (*point.provenance, *point.alternatives)}
        out = []
        for fact in self.budget.walk(self.model.facts):
            known = original_concept(fact) in definition.concepts or fact.metric in definition.concepts
            relevant = fact.period_end is not None and fact.period_end.year == self.years[side]
            relevant |= fact.period_end is None and fact.fiscal_year == self.years[side]
            if fact.id in referenced or known and relevant:
                self.budget.check("slot_candidates", len(out)+1)
                out.append(fact)
        return out

    def observation(self, metric, side):
        key = (metric, side)
        if key in self.refs:
            return self.refs[key]
        self.budget.check("observations", len(self.refs)+1)
        annual = self.annual[side]
        point = annual.metrics.get(metric) if metric in annual.metrics else None
        if point is None:
            point = self.model.missing(metric, annual.period_reason or "No unique annual window.")
        self.observations[key] = point
        dependencies = DEPENDENCIES.get(metric, ())
        diagnostic_edges, financial_edges = [], []
        pending_operands, pending_sources = [], []
        failures = []
        if dependencies:
            for role in self.budget.walk(dependencies):
                dchild, fchild = self.observation(role, side)
                self.operands += 1
                self.budget.check("operands", self.operands)
                doperand = self.ref("D", "operand", metric, side, role)
                diagnostic_edges.append(self.graph.put(doperand, {"required_metric": role,
                    "expected_unit": DEFINITIONS[role].unit,
                    "expected_period": None if annual.period is None else annual.period.model_dump(mode="json"),
                    "admitted_for_parent": fchild is not None and point.status == "available",
                    "parent_reason": point.reason}, [dchild]))
                if fchild is None:
                    failures.append("Required operand is not admitted: " + role + ".")
                else:
                    pending_operands.append((role, fchild))
        else:
            candidates = self.candidates_for(metric, side)
            selected = {s.fact_id for s in point.provenance}
            # Preserve the pre-rejection negative CapEx winner from canonical base.
            for base in self.budget.walk(self.model.base[metric]):
                if base.period == annual.period:
                    selected.update(s.fact_id for s in base.provenance)
            chosen = [self.facts[n] for n in self.budget.walk(sorted(selected))]
            selected_identities = {source_identity(f) for f in chosen}
            identity_values = {}
            for f in self.budget.walk(candidates):
                if usable(f, DEFINITIONS[metric]):
                    identity_values.setdefault(source_identity(f), set()).add(f.value)
            for fact in self.budget.walk(candidates):
                self.candidates += 1
                self.budget.check("candidates", self.candidates)
                cand = self.ref("D", "candidate", metric, side, suffix=str(fact.id))
                dispositions = []
                finite_value = fact.value.is_finite()
                if fact.id in selected:
                    dispositions.append("selected_by_existing_normalization")
                if finite_value and source_identity(fact) in selected_identities:
                    if len(identity_values.get(source_identity(fact), ())) > 1:
                        dispositions.append("conflicting_value")
                    elif fact.id not in selected:
                        dispositions.append("equivalent_duplicate")
                elif usable(fact, DEFINITIONS[metric]) and annual.period is not None and (
                        fact.period_start == annual.period.start and fact.period_end == annual.period.end):
                    if metric == "revenue" and point.revenue_basis is not None and (
                            REVENUE_CONCEPTS[original_concept(fact)].basis != point.revenue_basis):
                        dispositions.append("scope_excluded")
                    elif chosen:
                        dispositions.append("alternative_vintage")
                    elif metric == "revenue":
                        dispositions.append("scope_ambiguous")
                if not finite_value:
                    dispositions.append("nonfinite_value")
                elif not usable(fact, DEFINITIONS[metric]):
                    dispositions.append("invalid_source_unit_period_or_metadata")
                if annual.period is None or fact.period_start != annual.period.start or fact.period_end != annual.period.end:
                    dispositions.append("outside_selected_annual_window")
                if metric == "capital_expenditures" and finite_value and fact.value < 0:
                    dispositions.append("negative_capex_payment")
                if not dispositions:
                    dispositions.append("alternative_candidate")
                diagnostic_edges.append(self.graph.put(cand, {"dispositions": dispositions,
                    "duration_kind": period_kind(fact, DEFINITIONS[metric])},
                                                       [self.raw_source(fact, "D")]))
            if point.status == "available":
                require(len(point.provenance) == 1)
                source = point.provenance[0]
                fact = self.facts.get(source.fact_id)
                require(fact is not None and self.model.source(metric, fact) == source)
                values = {f.value for f in self.budget.walk(self.model.facts)
                          if usable(f, DEFINITIONS[metric]) and source_identity(f) == source_identity(fact)}
                if len(values) != 1:
                    failures.append("Conflicting values share the selected source identity.")
                pending_sources.append(fact)
        if annual.period is None or point.period != annual.period:
            failures.append(annual.period_reason or "Observation does not match the shared annual window.")
        if point.status != "available":
            failures.append(point.reason or "No admitted observation.")
        elif dependencies:
            require(tuple(i.role for i in point.inputs) == dependencies)
            for role, inp in self.budget.walk(zip(dependencies, point.inputs, strict=True)):
                operand = self.observations[(role, side)]
                require(inp.metric == role and inp.value == operand.value and inp.unit == operand.unit
                        and inp.period == operand.period and inp.revenue_basis == operand.revenue_basis
                        and inp.fact_ids == [s.fact_id for s in operand.provenance])
            require(point.formula == DEFINITIONS[metric].formula and point.provenance == [
                source for role in dependencies for source in self.observations[(role, side)].provenance])
        admitted = not failures
        for edge in diagnostic_edges:
            if edge.kind == "operand":
                self.graph.nodes[edge.key].data["admitted_for_parent"] = admitted
        self.failure_reasons[key] = failures
        self.admitted[key] = admitted
        if failures:
            diagnostic_edges.append(self.reject(metric, side, "observation_not_admitted", " ".join(failures)))
        dref = self.ref("D", "observation", metric, side)
        self.graph.put(dref, {"canonical": point.model_dump(mode="json"), "admitted": admitted}, diagnostic_edges)
        fref = None
        if admitted:
            require(point.value is not None and point.value.is_finite()
                    and point.unit == DEFINITIONS[metric].unit)
            for role, child in self.budget.walk(pending_operands):
                foperand = self.ref("F", "operand", metric, side, role)
                financial_edges.append(self.graph.put(foperand, {"required_metric": role}, [child]))
            for fact in self.budget.walk(pending_sources):
                financial_edges.append(self.raw_source(fact, "F"))
            fref = self.ref("F", "observation", metric, side)
            self.graph.put(fref, {"canonical": point.model_dump(mode="json"), "admitted": True}, financial_edges)
        self.refs[key] = dref, fref
        return dref, fref

    def build(self):
        for side in self.budget.walk(self.years):
            for metric in self.budget.walk(METRICS):
                self.observation(metric, side)
        for metric in self.budget.walk(METRICS):
            canonical = self.model.compare_fiscal(metric, FiscalPeriodRequest(fiscal_year=self.years["earlier"]),
                                                  FiscalPeriodRequest(fiscal_year=self.years["later"]))
            aligned = canonical.earlier == self.observations[(metric, "earlier")] and canonical.later == self.observations[(metric, "later")]
            admitted = canonical.status == "available" and aligned and all(
                self.admitted[(metric, side)] for side in self.years)
            reasons = []
            if not admitted:
                if canonical.reason:
                    reasons.append(canonical.reason)
                if not aligned:
                    reasons.append("Comparison operands differ from the shared annual windows.")
                for side in self.years:
                    reasons.extend(side + ": " + reason for reason in self.failure_reasons[(metric, side)])
                if not reasons:
                    reasons.append("Comparison or required annual evidence is not admitted.")
            result = canonical.model_copy(deep=True)
            if not admitted:
                # Detailed side/operand failures remain separate diagnostic
                # records. Do not repeatedly concatenate them into one field.
                result.status = canonical.status if canonical.status != "available" else "unavailable"
                result.reason = canonical.reason or reasons[0]
                result.absolute_change = result.percentage_change = result.direction = None
                result.percentage_status, result.percentage_reason = "unavailable", result.reason
            self.comparisons[metric] = result
            dreference = self.ref("D", "comparison", metric)
            dedges = [self.refs[(metric, s)][0] for s in self.years]
            if not admitted:
                dedges.append(self.reject(metric, None, "comparison_not_admitted", result.reason))
            # Complete annual ambiguity evidence from the unchanged eleven anchors.
            for side, year in self.budget.walk(self.years.items()):
                if self.annual[side].period is None:
                    windows = {}
                    for name in self.budget.walk(ANNUAL_COMPARISON_METRICS):
                        for p in self.budget.walk(self.model.metric_periods(name, "annual")):
                            if p.fiscal_year == year:
                                windows[window_key(p)] = p
                    for p in self.budget.walk(windows.values()):
                        wr = self.ref("D", "window", side=side, period=p)
                        sources = {}
                        for name, points in self.budget.walk(self.model.base.items()):
                            for point in self.budget.walk(points):
                                if point.period == p and name in ANNUAL_COMPARISON_METRICS:
                                    for src in self.budget.walk((*point.provenance, *point.alternatives)):
                                        source_ref = self.raw_source(self.facts[src.fact_id], "D")
                                        sources[source_ref.key] = source_ref
                        dedges.append(self.graph.put(wr, p.model_dump(mode="json"), sources.values()))
            self.graph.put(dreference, {"canonical": canonical.model_dump(mode="json"), "admitted": admitted}, dedges)
            if admitted:
                self.graph.put(self.ref("F", "comparison", metric), result.model_dump(mode="json"),
                               [self.refs[(metric, s)][1] for s in self.years])
        self.graph.validate()
        return self

    def fo(self, metric, side):
        return self.graph.closure([self.refs[(metric, side)][1]])

    def fc(self, metric):
        return self.graph.closure([self.ref("F", "comparison", metric)])

    def dc(self, metric):
        return self.graph.closure([self.ref("D", "comparison", metric)])

    def statements(self):
        out, clauses = [], {}
        for metric in self.budget.walk(METRICS):
            label = LABELS[metric]
            for side in self.years:
                if self.admitted[(metric, side)]:
                    p = self.observations[(metric, side)]
                    meaning = "calculated" if metric in DEPENDENCIES else "reported"
                    out.append(statement("VALUE", f"value:{metric}:{side}",
                        f"{label}: {exact_decimal(p.value)} {p.unit}, {side} FY{self.years[side]} {window_key(p.period)}; {meaning}.",
                        self.fo(metric, side), metric=metric, side=side))
            comp = self.comparisons[metric]
            if comp.status != "available":
                out.append(statement("UNAVAILABLE", f"unavailable:{metric}",
                    f"Cannot compare {label} for FY{self.years['earlier']} and FY{self.years['later']}: {comp.reason}",
                    diagnostic=self.dc(metric), metric=metric))
                continue
            x, y = comp.earlier.value, comp.later.value
            clauses[metric] = f"{label} {transition(x, y, comp.direction)}"
            out.append(statement("CHANGE", f"change:{metric}", clauses[metric] +
                f". {exact_decimal(x)} to {exact_decimal(y)} {comp.earlier.unit}; change {delta_display(comp.absolute_change, comp.earlier.unit, True)}.",
                self.fc(metric), metric=metric))
            if comp.earlier.unit == "USD":
                if x > 0:
                    require(comp.percentage_status == "available" and comp.percentage_change is not None)
                    require((comp.absolute_change == 0) == (comp.percentage_change == 0))
                    out.append(statement("PERCENT_CHANGE", f"percentage:{metric}",
                        "Percentage change: " + percentage_display(comp.percentage_change) + ".",
                        self.fc(metric), metric=metric))
                else:
                    require(comp.percentage_status == "unavailable" and comp.percentage_change is None)
                    out.append(statement("PERCENT_UNAVAILABLE", f"percentage-unavailable:{metric}",
                        "Percentage change unavailable: the earlier value is zero or negative.", self.fc(metric), metric=metric))
            if precision_hidden(comp):
                out.append(statement("PRECISION_NOTICE", f"precision:{metric}",
                    "Difference is smaller than the rounded display precision. Exact values: "
                    f"{exact_decimal(x)} to {exact_decimal(y)} {comp.earlier.unit}; exact change "
                    + delta_display(comp.absolute_change, comp.earlier.unit, True) + ".", self.fc(metric), metric=metric))
        blocking = [m for m in HEADLINE if self.comparisons[m].status != "available"]
        financial, diagnostic = {}, {}
        if blocking:
            outcome = "not_assessable"
            text = "The overall question cannot be assessed: " + "; ".join(
                LABELS[m]+": comparison evidence is not admitted" for m in blocking) + ". See the linked rejection evidence."
            for m in blocking:
                diagnostic.update((r.key, r) for r in self.dc(m))
        else:
            revenue = self.comparisons["revenue"]
            require(revenue.earlier.value > 0 and revenue.percentage_status == "available"
                    and revenue.percentage_change is not None)
            for m in HEADLINE:
                financial.update((r.key, r) for r in self.fc(m))
            if revenue.direction != "increase":
                outcome, prefix = "revenue_not_increased", "The selected periods do not show a revenue increase. "
            elif all(self.comparisons[m].direction == "increase" for m in HEADLINE):
                outcome, prefix = "all_increased", "Numerical increases occurred across the selected annual intervals. "
            else:
                outcome, prefix = "mixed", "Revenue increased; the other headline measures did not all increase. "
            text = prefix + "; ".join(clauses[m] for m in HEADLINE) + "."
        out.append(statement("OVERALL", "overall", text, financial.values(), diagnostic.values(), outcome=outcome))
        out.append(statement("LIMITATION", "limitation", "Numerical co-occurrence does not establish causality, unchanged business perimeter or comprehensive accounting comparability."))
        validate_statement_limits(out, self.budget)
        return out


def compose(model, versions, mode, earlier, later, budget):
    registry_guard()
    discovery = model.annual_comparison()
    require(len(discovery.fiscal_years) <= 200)
    scope = f"{model.company.cik}:{':'.join(map(str, versions))}:{earlier}:{later}"
    context = None
    if mode == "compare":
        context = Composition(model, versions, earlier, later, budget).build()
    available = 0 if context is None else sum(context.comparisons[m].status == "available" for m in HEADLINE)
    result = InsightsResponse(mode=mode, ticker=model.company.ticker, company_cik=model.company.cik,
        company_name=model.company.name, data_version=versions[0], facts_version=versions[1], evidence_version=versions[2],
        scope=scope, fiscal_years=discovery.fiscal_years, earlier_fiscal_year=earlier, later_fiscal_year=later,
        periods={} if context is None else {s: a.period for s, a in context.annual.items()},
        selection_policy=discovery.selection_policy, completeness=None if context is None else
            "complete" if available == len(HEADLINE) else "partial" if available else "unavailable",
        comparisons={} if context is None else deepcopy(context.comparisons),
        evidence=[] if context is None else deepcopy(sorted(context.graph.nodes.values(), key=lambda n: n.ref.key)),
        statements=[] if context is None else deepcopy(context.statements()))
    validate_result(result, context, budget)
    return result


def validate_result(result, context, budget):
    if context is None:
        require(result.mode == "discover" and not result.evidence and not result.statements and not result.comparisons
                and result.earlier_fiscal_year is None and result.later_fiscal_year is None
                and not result.periods and result.completeness is None)
        return
    require(result.scope == context.scope and result.comparisons == context.comparisons)
    company = context.model.company
    require((result.ticker, result.company_cik, result.company_name) == (company.ticker, company.cik, company.name)
            and (result.data_version, result.facts_version, result.evidence_version) == context.versions
            and result.mode == "compare" and result.earlier_fiscal_year == context.years["earlier"]
            and result.later_fiscal_year == context.years["later"]
            and result.periods == {s: a.period for s, a in context.annual.items()}
            and result.fiscal_years == context.model.annual_comparison().fiscal_years
            and result.selection_policy == context.annual["earlier"].selection_policy)
    count = sum(context.comparisons[m].status == "available" for m in HEADLINE)
    require(result.completeness == ("complete" if count == 5 else "partial" if count else "unavailable"))
    # Collector owns the expected graph from full canonical inputs. Existing
    # arbitrary same-scope references cannot enlarge a required closure.
    require(result.evidence == sorted(context.graph.nodes.values(), key=lambda n: n.ref.key))
    context.graph.validate()
    validate_statements(result.statements, context.statements(), budget)


@financial_reader
def build_insights(session, ticker, pin, mode, earlier, later, budget):
    company, versions, facts, config = bounded_load(session, ticker, pin, budget)
    admit_input(facts, () if mode == "discover" else (earlier, later), budget)
    registry_guard(config)
    # Empty registries are the adapter's exact early-return path; no adapter I/O.
    model = FinancialMetrics(company, facts, authorization_evidence=(), budget=budget)
    result = compose(model, versions, mode, earlier, later, budget)
    registry_guard(config)
    return bounded_json(result.model_dump(mode="json"), budget), config
