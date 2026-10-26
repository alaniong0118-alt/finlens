"""Synthetic FIN-DEPTH-01 tests. Invoke the guarded runner, never plain pytest."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app import main, database, freshness_service, activation_lifecycle
from app.financial_insights_contract import (
    Budget, Graph, InsightsFailure, LIMITS, bounded_json, budget_scope, reference, transition,
    validate_statements, checked_text, precision_hidden,
)
from app.financial_insights_service import (
    Composition, admit_input, bounded_load, compose, preflight_query, registry_guard, row_stats,
    validate_result, METRICS, HEADLINE, FACT_FIELDS,
)
from app.financial_metrics_service import FinancialMetrics, ANNUAL_COMPARISON_METRICS
from app import revenue_scope_authorizations as auth, sec_evidence_adapter as adapter

COMPANY = SimpleNamespace(id=1, ticker="TEST", cik="0000000001", name="Synthetic company", exchange="TEST")


def fact(concept="Revenues", value="100", year=2025, **changes):
    args = dict(id=1, company_cik=COMPANY.cik, metric=concept, value=Decimal(value), unit="USD",
        period_start=date(year, 1, 1), period_end=date(year, 12, 31), period_type="annual",
        fiscal_year=year+1, fiscal_period="FY", form="10-K", filed=date(year+1, 2, 1),
        accession_number=f"0000000001-{str(year+1)[-2:]}-000001", frame=None,
        source="SEC Company Facts API: "+concept, created_at=datetime(year+1, 2, 1))
    args.update(changes)
    return SimpleNamespace(**args)


def dataset():
    facts = []
    for year, values in [(2024, ("100", "10", "8", "14", "4")), (2025, ("120", "18", "12", "20", "5"))]:
        for concept, value in zip(("Revenues", "OperatingIncomeLoss", "NetIncomeLoss",
                                  "NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquirePropertyPlantAndEquipment"), values):
            facts.append(fact(concept, value, year, id=len(facts)+1))
    return facts


def context(facts=None):
    budget = Budget()
    rows = dataset() if facts is None else facts
    admit_input(rows, (2024, 2025), budget)
    model = FinancialMetrics(COMPANY, rows, budget=budget)
    return Composition(model, (7, 6, 5), 2024, 2025, budget).build()


@pytest.mark.parametrize("name,limit", LIMITS.items())
def test_all_numeric_resource_boundaries(name, limit):
    b = Budget()
    b.check(name, limit)
    with pytest.raises(InsightsFailure) as caught:
        b.check(name, limit+1)
    assert caught.value.code == "INSIGHTS_RESOURCE_LIMIT"


@pytest.mark.parametrize("limit", [64, 128, 192, 400, 800, 1024, 2048])
def test_utf8_field_boundaries(limit):
    checked_text("a"*limit, limit)
    with pytest.raises(InsightsFailure):
        checked_text("a"*(limit-1)+"é", limit)


def test_discovery_and_seven_metric_composition_preserve_canonical_results():
    ctx = context()
    assert tuple(ctx.comparisons) == METRICS
    assert len(ANNUAL_COMPARISON_METRICS) == 11
    for metric, result in ctx.comparisons.items():
        from app.financial_metric_schemas import FiscalPeriodRequest
        expected = ctx.model.compare_fiscal(metric, FiscalPeriodRequest(fiscal_year=2024), FiscalPeriodRequest(fiscal_year=2025))
        assert result.model_dump(mode="json") == expected.model_dump(mode="json")
    assert ctx.comparisons["operating_margin"].absolute_change == Decimal(".05")
    assert ctx.comparisons["free_cash_flow"].absolute_change == 5
    overall = next(s for s in ctx.statements() if s.rule == "OVERALL")
    assert overall.outcome == "all_increased"
    assert {r.metric for r in overall.financial if r.kind == "comparison"} == set(HEADLINE)
    assert all(r.category == "F" for r in overall.financial)


@pytest.mark.parametrize("concept", ["GrossProfit", "OperatingIncomeLoss", "NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquirePropertyPlantAndEquipment"])
def test_discovery_does_not_narrow_eleven_metric_policy(concept):
    rows = [fact(concept)]
    model = FinancialMetrics(COMPANY, rows)
    result = compose(model, (0, 0, 0), "discover", None, None, Budget())
    assert result.fiscal_years == model.annual_comparison().fiscal_years == [2025]
    assert result.statements == result.evidence == []


def test_hidden_negative_capex_is_diagnostic_and_never_fcf_support():
    rows = dataset()
    rows[-1].value = Decimal("-5")
    ctx = context(rows)
    assert ctx.comparisons["free_cash_flow"].status == "unavailable"
    assert ctx.refs[("capital_expenditures", "later")][1] is None
    assert ctx.refs[("free_cash_flow", "later")][1] is None
    source = next(n for n in ctx.graph.nodes.values() if n.ref.kind == "source" and n.ref.category == "D" and n.data["id"] == "10")
    assert source.data["value"] == "-5"
    missing = next(s for s in ctx.statements() if s.key == "unavailable:free_cash_flow")
    assert not missing.financial and source.ref in missing.diagnostic
    assert next(s for s in ctx.statements() if s.key == "overall").outcome == "not_assessable"


@pytest.mark.parametrize("metric_id", [1, 2, 4, 5])
@pytest.mark.parametrize("reverse", [False, True])
def test_selected_source_conflicts_reject_dependent_claims(metric_id, reverse):
    rows = dataset()
    duplicate = deepcopy(rows[metric_id-1])
    duplicate.id = 11
    duplicate.value += 1
    rows.append(duplicate)
    if reverse:
        rows.reverse()
    ctx = context(rows)
    name = {1: "revenue", 2: "operating_income", 4: "operating_cash_flow", 5: "capital_expenditures"}[metric_id]
    assert ctx.refs[(name, "earlier")][1] is None


def test_identical_duplicates_and_later_vintages_preserve_selection():
    rows = dataset()
    rows.append(deepcopy(rows[0]))
    rows[-1].id = 11
    assert context(rows).comparisons["revenue"].status == "available"
    rows[-1].filed = date(2026, 2, 1)
    rows[-1].accession_number = "0000000001-26-000002"
    rows[-1].value = Decimal("110")
    assert context(rows).comparisons["revenue"].earlier.value == 110


@pytest.mark.parametrize("x,y,word", [
    (-10,-5,"less negative"),(-5,-10,"more negative"),(-5,-5,"unchanged and negative"),
    (-5,0,"negative value to zero"),(-5,5,"negative to positive"),
    (0,-5,"zero to a negative"),(0,0,"unchanged at zero"),(0,5,"zero to a positive"),
    (5,-5,"positive to negative"),(5,0,"positive value to zero"),(5,6,"increased and remained positive"),
    (6,5,"decreased and remained positive"),(5,5,"unchanged and positive")])
def test_sign_wording(x, y, word):
    direction = "increase" if y>x else "decrease" if y<x else "no_change"
    assert word in transition(Decimal(x), Decimal(y), direction)


def test_tiny_change_never_becomes_unchanged():
    rows = dataset()
    rows[5].value = Decimal("100.0001")
    ctx = context(rows)
    assert precision_hidden(ctx.comparisons["revenue"])
    s = next(s for s in ctx.statements() if s.key == "precision:revenue")
    assert "100.0001" in s.text and "0.0001" in s.text


@pytest.mark.parametrize("mutation", ["extra", "duplicate", "diagnostic", "side", "scope", "false", "missing"])
def test_statement_exact_sets_and_predicates(mutation):
    ctx = context()
    expected = ctx.statements()
    actual = deepcopy(expected)
    s = next(s for s in actual if s.key == "change:revenue")
    if mutation == "extra":
        s.financial.append(ctx.ref("F", "comparison", "net_income"))
    elif mutation == "duplicate":
        s.financial.append(s.financial[0])
    elif mutation == "diagnostic":
        s.financial = []
        s.diagnostic = ctx.dc("revenue")
    elif mutation == "side":
        s.financial[0] = s.financial[0].model_copy(update={"side": "later"})
    elif mutation == "scope":
        s.financial[0] = s.financial[0].model_copy(update={"scope": "OTHER"})
    elif mutation == "false":
        s.text = "Revenue decreased."
    else:
        s.financial.pop()
    with pytest.raises(InsightsFailure):
        validate_statements(actual, expected, ctx.budget)


def test_graph_broken_reference_and_cycle():
    for cycle in (False, True):
        g = Graph("scope", Budget())
        a = reference("scope", "D", "observation", "net_margin", "earlier")
        b = reference("scope", "D", "operand", "net_margin", "earlier", "revenue")
        g.put(a, {}, [b])
        if cycle:
            # A forged role cannot smuggle a back edge into the dependency DAG.
            g.put(b, {}, [a])
        with pytest.raises(InsightsFailure):
            g.validate()


def test_preflight_is_genuinely_limited_null_safe_and_utf8():
    sql = str(preflight_query(COMPANY.cik).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "LIMIT 10001" in sql and sql.index("LIMIT 10001") < sql.index(") AS insights_sentinel")
    assert "coalesce" in sql and "convert_to" in sql and "UTF8" in sql and "to_char" in sql


class Rows:
    def __init__(self, rows):
        self.rows, self.offset, self.closed = rows, 0, False
    def mappings(self):
        return self
    def one_or_none(self):
        return self.rows[0] if self.rows else None
    def one(self):
        assert len(self.rows) == 1
        return self.rows[0]
    def fetchmany(self, count):
        assert count == 128
        batch = self.rows[self.offset:self.offset+count]
        self.offset += len(batch)
        return batch
    def close(self):
        self.closed = True


def session_for(rows=None, stats=None):
    rows = dataset() if rows is None else rows
    company = dict(vars(COMPANY), data_version=7, facts_version=6, evidence_version=5)
    size = sum(row_stats(f) for f in rows)
    complete = Rows([vars(f) for f in rows])
    session = Mock()
    session.execute.side_effect = [Rows([company]), Rows([stats or {"count":len(rows), "bytes":size, "invalid":0}]), complete]
    return session, complete


@pytest.mark.parametrize("stats", [
    {"count":10001,"bytes":0,"invalid":0},
    {"count":1,"bytes":8*1024*1024+1,"invalid":0},
    {"count":1,"bytes":1,"invalid":1}])
def test_preflight_rejects_before_materialization(stats):
    session, result = session_for(stats=stats)
    with pytest.raises(InsightsFailure):
        bounded_load(session, "TEST", 7, Budget())
    assert session.execute.call_count == 2 and result.offset == 0


@pytest.mark.parametrize("offset", ["count", "bytes"])
def test_incomplete_input_never_normalized(offset, monkeypatch):
    from app import financial_insights_service as service
    rows = dataset()
    stats = {"count":len(rows), "bytes":sum(row_stats(f) for f in rows), "invalid":0}
    stats[offset] += 1
    session, result = session_for(rows, stats)
    called = Mock(side_effect=AssertionError("Normalization forbidden"))
    monkeypatch.setattr(service, "FinancialMetrics", called)
    with pytest.raises(InsightsFailure) as error:
        service.build_insights(session, "TEST", 7, "compare", 2024, 2025, Budget())
    assert error.value.code == "INSIGHTS_EVIDENCE_INCOMPLETE"
    assert result.closed and not called.called


def test_bounded_complete_load_matches_original_and_does_not_filter_years():
    rows = dataset()+[fact(year=2010, id=11)]
    session, result = session_for(rows)
    _, _, loaded, _ = bounded_load(session, "TEST", 7, Budget())
    assert [vars(f) for f in loaded] == [vars(f) for f in rows]
    assert result.closed


@pytest.mark.parametrize("owner,name", [(auth,"REVENUE_SELECTION_AUTHORIZATIONS"),
    (auth,"DENOMINATOR_AUTHORIZATIONS"),(auth,"AUTHORIZATION_WITHDRAWALS"),(adapter,"PRODUCTION_EVIDENCE_POLICIES")])
def test_current_owned_registries_reject_before_adapter_io(owner, name, monkeypatch):
    monkeypatch.setattr(owner, name, (object(),))
    with pytest.raises(InsightsFailure) as caught:
        registry_guard()
    assert caught.value.code == "INSIGHTS_CONFIGURATION_UNSUPPORTED"


def test_deadline_and_cursor_query_boundaries():
    now = [0.0]
    b = Budget(lambda:now[0])
    now[0] = 19.999
    b.deadline()
    now[0] = 20
    with pytest.raises(InsightsFailure) as caught:
        b.deadline()
    assert caught.value.code == "INSIGHTS_DEADLINE_EXCEEDED"
    for resource in ("cursors", "research_queries", "work"):
        b = Budget()
        b.counts[resource] = LIMITS[resource]-1
        b.add(resource)
        with pytest.raises(InsightsFailure):
            b.add(resource)


def test_bounded_utf8_serialization_exact_boundary():
    # Each short UTF-8 string is bounded; test aggregate encoding independently.
    n = (LIMITS["output_bytes"]-2)//4
    values = ["a"]*n
    values[-1] = "aaé"
    expected = json.dumps(values, ensure_ascii=False, separators=(",",":")).encode()
    assert len(expected) == LIMITS["output_bytes"]
    # Large generic arrays would consume the work budget; this test verifies the
    # streaming byte counter separately, with visits mocked, not production caps.
    b = Budget(); b.visit = lambda:None
    assert bounded_json(values, b) == expected
    values[-1] = "aaaé"  # exactly one additional encoded UTF-8 byte
    with pytest.raises(InsightsFailure) as caught:
        bounded_json(values, b)
    assert caught.value.code == "INSIGHTS_RESOURCE_LIMIT"


def test_api_pin_zero_stale_validation_and_cleanup(monkeypatch):
    from app import financial_insights_service as service
    session = Mock()
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = 0
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _:True)
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda:session)
    config = registry_guard()
    builder = Mock(return_value=(b'{"fixture":true}', config))
    monkeypatch.setattr(main, "build_insights", builder)
    with TestClient(main.app) as client:
        path = "/companies/TEST/financials/insights?mode=discover"
        response = client.get(path, headers={"X-FinLens-Data-Version":"0"})
        assert response.status_code == 200 and response.headers["X-FinLens-Data-Version"] == "0"
        assert session.close.called
        assert client.get(path).status_code == 422
        assert client.get(path, headers={"X-FinLens-Data-Version":"00"}).status_code == 422
        builder.reset_mock()
        stale = client.get(path, headers={"X-FinLens-Data-Version":"1"})
        assert stale.status_code == 409 and not builder.called
        session.close.side_effect = RuntimeError("secret path /private SQL credentials")
        failed = client.get(path, headers={"X-FinLens-Data-Version":"0"})
        assert failed.status_code == 500 and b"secret" not in failed.content


def test_optional_budget_instruments_nested_work_and_preserves_all_results():
    rows = dataset()+[fact(year=2026, id=11, period_start=date(2026,1,1), period_end=date(2026,6,30), form="10-Q")]
    plain = FinancialMetrics(COMPANY, rows)
    b = Budget()
    bounded = FinancialMetrics(COMPANY, rows, budget=b)
    for mode in ("annual", "quarter", "half_year"):
        assert plain.summary(mode).model_dump(mode="json") == bounded.summary(mode).model_dump(mode="json")
    b.counts["work"] = LIMITS["work"]
    with pytest.raises(InsightsFailure):
        bounded.period("quarter", date(2026,1,1), date(2026,3,31))


def test_entire_loader_to_utf8_response_and_empty_evidence():
    from app.financial_insights_service import build_insights
    for rows in (dataset(), []):
        session, _ = session_for(rows)
        body, _ = build_insights(session, "TEST", 7, "compare", 2024, 2025, Budget())
        payload = json.loads(body)
        assert set(payload["comparisons"]) == set(METRICS)
        assert payload["data_version"] == 7
        assert next(s for s in payload["statements"] if s["key"] == "overall")["outcome"] == (
            "all_increased" if rows else "not_assessable")


@pytest.mark.parametrize("change", ["revenue_scope", "ytd", "margin_missing", "negative_baseline", "zero_baseline"])
def test_financial_scope_duration_and_availability_abstentions(change):
    rows = dataset()
    if change == "revenue_scope":
        rows[5].source = "SEC Company Facts API: RevenueFromContractWithCustomerExcludingAssessedTax"
    elif change == "ytd":
        rows[8].period_end = date(2025, 9, 30)
    elif change == "margin_missing":
        rows.pop(7)
    else:
        rows[2].value = Decimal("-8" if change == "negative_baseline" else "0")
    ctx = context(rows)
    if change in {"negative_baseline", "zero_baseline"}:
        comp = ctx.comparisons["net_income"]
        assert comp.absolute_change is not None and comp.percentage_change is None
        assert next(s for s in ctx.statements() if s.key == "percentage-unavailable:net_income")
    else:
        assert next(s for s in ctx.statements() if s.key == "overall").outcome == "not_assessable"


def test_impossible_all_admitted_without_revenue_percentage_is_not_abstention():
    ctx = context()
    ctx.comparisons["revenue"].percentage_change = None
    ctx.comparisons["revenue"].percentage_status = "unavailable"
    with pytest.raises(InsightsFailure) as error:
        ctx.statements()
    assert error.value.code == "INSIGHTS_CONTRACT_INVALID"


def test_collector_source_and_candidate_limits_do_not_truncate():
    rows = [fact(id=i+1) for i in range(257)]
    with pytest.raises(InsightsFailure) as error:
        admit_input(rows, (2024,2025), Budget())
    assert error.value.code == "INSIGHTS_RESOURCE_LIMIT"
    rows = [fact("Unmapped", id=i+1) for i in range(10001)]
    with pytest.raises(InsightsFailure):
        admit_input(rows, (), Budget())
    admit_input(rows[:10000], (), Budget())


def test_registry_change_during_normalization_is_rejected(monkeypatch):
    from app import financial_insights_service as service
    original = service.FinancialMetrics
    def changed(*args, **kwargs):
        model = original(*args, **kwargs)
        monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (object(),))
        return model
    monkeypatch.setattr(service, "FinancialMetrics", changed)
    session, _ = session_for()
    with pytest.raises(InsightsFailure) as error:
        service.build_insights(session, "TEST", 7, "compare", 2024, 2025, Budget())
    assert error.value.code == "INSIGHTS_CONFIGURATION_UNSUPPORTED"


def test_actual_driver_cursor_entrypoint_accounts_before_delegate(monkeypatch):
    import psycopg
    delegated = Mock(return_value="executed")
    monkeypatch.setattr(psycopg.Cursor, "execute", delegated)
    class Cursor(database.InsightsCursor):
        @property
        def connection(self):
            return None
        def __del__(self):
            pass
    cursor = object.__new__(Cursor)
    budget = Budget()
    with budget_scope(budget):
        assert cursor.execute("SHOW transaction_isolation") == "executed"
        assert cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY") == "executed"
        for _ in range(5):
            cursor.execute("SELECT 42")
        assert budget.counts["cursors"] == 7 and budget.counts["research_queries"] == 5
        with pytest.raises(InsightsFailure):
            cursor.execute("SELECT 43")
        assert delegated.call_count == 7
        with pytest.raises(InsightsFailure):
            cursor.execute("INSERT INTO forbidden VALUES (1)")
        with pytest.raises(InsightsFailure):
            cursor.executemany("SELECT 1", [])
    # Real psycopg client fetchmany reads PGresult rows, never runs FETCH SQL.
    source = inspect.getsource(psycopg.Cursor.fetchmany)
    assert ".execute(" not in source and "_exec_command" not in source


def test_bounded_factory_actual_sqlalchemy_cursor_and_cleanup(monkeypatch):
    from test_http_database_runtime import synthetic_pool
    from sqlalchemy import text
    engine, connections = synthetic_pool()
    original = engine.pool._creator
    fetches = []
    def creator():
        connection = original()
        raw_cursor = connection.cursor
        def cursor():
            result = raw_cursor()
            raw_execute = result.execute
            remaining = []
            def execute(sql, params=None):
                database._insights_cursor_execution(sql)
                if str(sql) == "SELECT 42":
                    result.description = (("answer", None, None, None, None, None, None),)
                    remaining[:] = [(42,)]
                return raw_execute(sql, params)
            def fetchmany(count):
                fetches.append(count)
                rows = remaining[:count]
                del remaining[:count]
                return rows
            result.execute = execute
            result.fetchmany = fetchmany
            return result
        connection.cursor = cursor
        return connection
    engine.pool._creator = creator
    captured = {}
    def create(url, **options):
        captured.update(options)
        return engine
    monkeypatch.setattr(database, "_insights_factory", None)
    monkeypatch.setattr(database, "create_engine", create)
    budget = Budget()
    with budget_scope(budget):
        factory = database.insights_session_factory()
        with freshness_service.read_session(factory) as session:
            for _ in range(5):
                result = session.execute(text("SELECT 42"))
                assert [tuple(r) for r in result.fetchmany(128)] == [(42,)]
                assert result.fetchmany(128) == []
            with pytest.raises(InsightsFailure):
                session.execute(text("SELECT 43"))
    assert captured["connect_args"]["cursor_factory"] is database.InsightsCursor
    assert captured["connect_args"]["connect_timeout"] == 2
    assert captured["connect_args"]["options"] == "-c statement_timeout=1500 -c lock_timeout=250"
    assert captured["pool_timeout"] == captured["pool_size"] == 1 and captured["max_overflow"] == 0
    assert captured["use_native_hstore"] is False
    assert len(connections[0].statements) == 7  # probe, SET, five SELECTs; no sixth SELECT
    assert fetches == [128]*10 and not any("FETCH" in str(s) for s in connections[0].statements)
    assert engine.pool.checkedout() == 0
    engine.dispose()


@pytest.mark.parametrize("version", [0, 7])
def test_real_api_composition_and_publication_uses_reader_through_cleanup(monkeypatch, version):
    session, _ = session_for()
    company = dict(vars(COMPANY), data_version=version, facts_version=version, evidence_version=version)
    rows = dataset()
    session.execute.side_effect = [Mock(), Rows([company]), Rows([{
        "count":len(rows),"bytes":sum(row_stats(f) for f in rows),"invalid":0}]), Rows([vars(f) for f in rows])]
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = version
    def close():
        assert activation_lifecycle._readers > 0
    session.close.side_effect = close
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda:session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _:True)
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/insights?mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025",
            headers={"X-FinLens-Data-Version":str(version)})
    assert response.status_code == 200
    assert response.json()["data_version"] == version
    assert response.headers["X-FinLens-Data-Version"] == str(version)
    assert activation_lifecycle._readers == 0


@pytest.mark.parametrize("code,status", [
    ("INSIGHTS_RESOURCE_LIMIT",503),("INSIGHTS_EVIDENCE_INCOMPLETE",503),
    ("INSIGHTS_CONFIGURATION_UNSUPPORTED",503),("INSIGHTS_CONTRACT_INVALID",500),
    ("INSIGHTS_DEADLINE_EXCEEDED",504),(None,500)])
def test_versioned_route_error_contract_is_small_and_sanitized(monkeypatch, code, status):
    session = Mock()
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = 0
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda:session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _:True)
    failure = InsightsFailure(code) if code else TypeError("SECRET /private/file SQL password")
    monkeypatch.setattr(main, "build_insights", Mock(side_effect=failure))
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/insights?mode=discover", headers={"X-FinLens-Data-Version":"0"})
    assert response.status_code == status
    assert response.headers["X-FinLens-Error-Code"] == (code or "INSIGHTS_CONTRACT_INVALID")
    assert len(response.content) <= 512 and b"SECRET" not in response.content
    assert set(response.json()) == {"detail"} and session.close.called


def test_no_late_publication_after_cleanup_deadline(monkeypatch):
    now = [0.0]
    b = Budget(lambda:now[0])
    monkeypatch.setattr(main, "Budget", lambda:b)
    session = Mock()
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = 0
    session.close.side_effect = lambda:now.__setitem__(0,20)
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda:session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _:True)
    monkeypatch.setattr(main, "build_insights", Mock(return_value=(b'{"assessment":"forbidden"}',registry_guard())))
    with TestClient(main.app) as client:
        response = client.get("/companies/TEST/financials/insights?mode=discover", headers={"X-FinLens-Data-Version":"0"})
    assert response.status_code == 504 and b"assessment" not in response.content


def test_canonical_ast_changes_are_only_budget_instrumentation():
    import ast
    from pathlib import Path
    import subprocess
    baseline = subprocess.run(["git","show","HEAD:backend/app/financial_metrics_service.py"],
        capture_output=True,text=True,check=True).stdout
    current = Path("app/financial_metrics_service.py").read_text()
    def financial_class(source):
        return next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=="FinancialMetrics")
    class Strip(ast.NodeTransformer):
        def visit_Call(self,node):
            node = self.generic_visit(node)
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=="self":
                if node.func.attr=="_walk": return node.args[0]
            return node
        def visit_UnaryOp(self,node):
            node=self.generic_visit(node)
            if isinstance(node.op,ast.Not) and isinstance(node.operand,ast.Call) and isinstance(node.operand.func,ast.Attribute) and node.operand.func.attr=="_contains":
                return ast.Compare(left=node.operand.args[1],ops=[ast.NotIn()],comparators=[node.operand.args[0]])
            return node
    original=financial_class(baseline)
    updated=financial_class(current)
    updated.body=[n for n in updated.body if not isinstance(n,ast.FunctionDef) or n.name not in {"_tick","_walk","_contains"}]
    for method in updated.body:
        if isinstance(method,ast.FunctionDef):
            if method.name=="__init__":
                method.args.kwonlyargs.pop();method.args.kw_defaults.pop()
            method.body=[n for n in method.body if not (
                isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and t.attr=="_budget" for t in n.targets)) and not (
                isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=="_tick")]
    updated=Strip().visit(updated)
    assert ast.dump(updated,include_attributes=False)==ast.dump(original,include_attributes=False)


@pytest.mark.parametrize("target,direction,outcome", [
    ("revenue", "decrease", "revenue_not_increased"),
    ("revenue", "no_change", "revenue_not_increased"),
    ("operating_cash_flow", "decrease", "mixed")])
def test_closed_overall_predicates(target, direction, outcome):
    rows = dataset()
    if target == "revenue":
        rows[5].value = Decimal("90" if direction == "decrease" else "100")
    else:
        rows[8].value = Decimal("13")
    ctx = context(rows)
    overall = next(s for s in ctx.statements() if s.key == "overall")
    assert overall.outcome == outcome
    assert len([r for r in overall.financial if r.kind == "comparison"]) == 5


def test_not_assessable_has_exact_blocking_roots_and_no_financial_refs():
    rows = dataset(); rows[-1].value = Decimal("-5")
    ctx = context(rows)
    overall = next(s for s in ctx.statements() if s.key == "overall")
    assert not overall.financial
    assert [r.metric for r in overall.diagnostic if r.kind == "comparison"] == ["free_cash_flow"]
    assert overall.diagnostic == ctx.dc("free_cash_flow")
    assert not any(n.ref.category == "F" and n.ref.kind == "operand" and n.ref.metric == "free_cash_flow"
                   and n.ref.side == "later" for n in ctx.graph.nodes.values())


def test_graph_exact_supported_depth_and_window_bounds():
    g=Graph("scope",Budget())
    refs=[reference("scope","D","comparison","net_margin"),
          reference("scope","D","observation","net_margin","earlier"),
          reference("scope","D","operand","net_margin","earlier","net_income"),
          reference("scope","D","observation","net_income","earlier"),
          reference("scope","D","rejection",suffix="r"),
          reference("scope","D","candidate",suffix="c"),
          reference("scope","D","source",suffix="s")]
    for index,ref in enumerate(refs):
        g.put(ref,{},refs[index+1:index+2])
    assert len(g.closure([refs[0]]))==7
    for count in (16,17):
        rows=[fact(id=i+1,period_start=date(2025,1,1)+__import__("datetime").timedelta(days=i)) for i in range(count)]
        if count==16:
            admit_input(rows,(2025,),Budget())
        else:
            with pytest.raises(InsightsFailure):admit_input(rows,(2025,),Budget())
    for count in (256,257):
        rows=[fact(id=i+1,year=1900+i) for i in range(count)]
        if count==256:
            admit_input(rows,(),Budget())
        else:
            with pytest.raises(InsightsFailure):admit_input(rows,(),Budget())


def test_empty_query_probe_and_total_cursor_limit(monkeypatch):
    b=Budget()
    with budget_scope(b):
        for _ in range(20): database._insights_cursor_execution(";")
        with pytest.raises(InsightsFailure): database._insights_cursor_execution(";")
    assert b.counts["cursors"]==20 and "research_queries" not in b.counts


def test_exact_get_route_admission_and_body_contract(monkeypatch):
    from app import config
    monkeypatch.setattr(config,"_SERVER_PROFILE",config.ServerProfile("sec_readonly"))
    factory=Mock(side_effect=AssertionError("No request was admitted"))
    monkeypatch.setattr(main,"InsightsSessionLocal",factory)
    with TestClient(main.app) as client:
        assert client.post("/companies/TEST/financials/insights").status_code==403
        assert client.get("/companies/TEST/financials/insights-alias").status_code==403
        assert client.get("/companies/TEST/financials/insights?mode=discover").status_code==422
    assert not factory.called


@pytest.mark.parametrize("direction", [-1,1])
def test_tiny_percentage_cannot_publish_unqualified_zero(direction):
    rows=dataset()
    rows[0].value=Decimal("1000000000000")
    rows[5].value=rows[0].value+direction*100
    ctx=context(rows)
    s=next(s for s in ctx.statements() if s.key=="percentage:revenue")
    assert "0.00%" not in s.text
    assert next(s for s in ctx.statements() if s.key=="precision:revenue")


@pytest.mark.parametrize("metric", ["revenue","net_margin"])
def test_negative_rounding_zero_at_display_boundary_keeps_precision_notice(metric):
    rows=dataset()
    if metric=="revenue":
        rows[0].value=Decimal("100.0150");rows[5].value=Decimal("100.0149")
    else:
        rows[5].value=rows[0].value
        rows[2].value=Decimal("100.0150");rows[7].value=Decimal("100.0149")
    ctx=context(rows)
    assert ctx.comparisons[metric].direction=="decrease"
    assert next(s for s in ctx.statements() if s.key=="precision:"+metric)


def capex_endpoint_response(rows, monkeypatch):
    """Exercise the real route/loader/composer; only the read-only session is fake."""
    session, _ = session_for(rows)
    statements = list(session.execute.side_effect)
    session.execute.side_effect = [Mock(), *statements]  # read_session SET TRANSACTION
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = 7
    monkeypatch.setattr(main, "InsightsSessionLocal", lambda: session)
    monkeypatch.setattr(freshness_service, "schema_ready", lambda _: True)
    with TestClient(main.app) as client:
        response = client.get(
            "/companies/TEST/financials/insights?mode=compare&earlier_fiscal_year=2024&later_fiscal_year=2025",
            headers={"X-FinLens-Data-Version": "7"})
    assert session.close.called
    return response


@pytest.mark.parametrize("side,index", [("earlier", 4), ("later", 9)])
@pytest.mark.parametrize("with_valid", [True, False], ids=["selected", "only"])
@pytest.mark.parametrize("nonfinite", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_nonfinite_capex_endpoint_diagnostics(side, index, with_valid, nonfinite, monkeypatch):
    rows = dataset()
    selected_id = rows[index].id
    selected_value = rows[index].value
    rejected = deepcopy(rows[index])
    rejected.value = Decimal(nonfinite)
    if with_valid:
        rejected.id = 11  # Same source identity, later ID; must never win ranking.
        rows.append(rejected)
    else:
        rows[index] = rejected
    canonical = FinancialMetrics(COMPANY, rows)
    annual = canonical.annual_comparison(2024 if side == "earlier" else 2025)
    if with_valid:
        assert annual.metrics["capital_expenditures"].value == selected_value
        assert annual.metrics["capital_expenditures"].provenance[0].fact_id == selected_id
        assert annual.metrics["free_cash_flow"].value == Decimal("10" if side == "earlier" else "15")
    else:
        assert annual.metrics["capital_expenditures"].status == "unavailable"
        assert annual.metrics["free_cash_flow"].status == "unavailable"

    response = capex_endpoint_response(rows, monkeypatch)
    assert response.status_code == 200, response.text
    assert response.headers["X-FinLens-Data-Version"] == "7"
    def reject_constant(value):
        raise AssertionError("Nonfinite JSON number: " + value)
    payload = json.loads(response.content, parse_constant=reject_constant)
    sources = [node for node in payload["evidence"] if node["ref"]["kind"] == "source"
               and node["data"]["id"] == str(rejected.id)]
    assert len(sources) == 1 and sources[0]["ref"]["category"] == "D"
    assert sources[0]["data"]["value"] == nonfinite  # Approved textual diagnostic value.
    assert sources[0]["data"]["accession_number"] == rejected.accession_number
    candidate = next(node for node in payload["evidence"] if node["ref"]["kind"] == "candidate"
                     and node["ref"]["metric"] == "capital_expenditures" and node["ref"]["side"] == side
                     and sources[0]["ref"] in node["edges"])
    assert candidate["data"]["dispositions"] == ["nonfinite_value"]
    # A same-identity unusable value is neither an equivalent duplicate nor a
    # negative payment. It is diagnostic-only, even when a valid winner exists.
    for node in payload["evidence"]:
        if node["ref"]["category"] == "F" and node["ref"]["kind"] == "source":
            assert node["data"]["id"] != str(rejected.id)
    for item in payload["statements"]:
        assert all(ref["category"] == "F" for ref in item["financial"])
        assert not any(ref["kind"] == "source" and ref["key"].rsplit("|", 1)[-1] == str(rejected.id)
                       for ref in item["financial"])
    if with_valid:
        from app.financial_metric_schemas import FiscalPeriodRequest
        ordinary = FinancialMetrics(COMPANY, dataset())
        for metric in METRICS:
            expected = ordinary.compare_fiscal(metric, FiscalPeriodRequest(fiscal_year=2024),
                                              FiscalPeriodRequest(fiscal_year=2025))
            assert payload["comparisons"][metric] == expected.model_dump(mode="json")
        observation = next(node for node in payload["evidence"] if node["ref"]["category"] == "F"
                           and node["ref"]["kind"] == "observation"
                           and node["ref"]["metric"] == "capital_expenditures" and node["ref"]["side"] == side)
        assert Decimal(observation["data"]["canonical"]["value"]) == selected_value
        assert observation["data"]["canonical"]["provenance"][0]["fact_id"] == selected_id
    else:
        fcf = payload["comparisons"]["free_cash_flow"]
        assert fcf["status"] == "unavailable" and fcf["absolute_change"] is None
        assert fcf[side]["status"] == "unavailable" and fcf[side]["value"] is None
        unavailable = next(item for item in payload["statements"] if item["key"] == "unavailable:free_cash_flow")
        assert not unavailable["financial"] and sources[0]["ref"] in unavailable["diagnostic"]
        assert next(item for item in payload["statements"] if item["key"] == "overall")["outcome"] == "not_assessable"
        assert not any(node["ref"]["category"] == "F" and node["ref"]["kind"] == "observation"
                       and node["ref"]["metric"] in {"capital_expenditures", "free_cash_flow"}
                       and node["ref"]["side"] == side for node in payload["evidence"])


@pytest.mark.parametrize("side,index", [("earlier", 4), ("later", 9)])
@pytest.mark.parametrize("value", ["-5", "0", "ordinary"])
def test_finite_capex_endpoint_classification_unchanged(side, index, value, monkeypatch):
    rows = dataset()
    if value != "ordinary":
        rows[index].value = Decimal(value)
    response = capex_endpoint_response(rows, monkeypatch)
    assert response.status_code == 200, response.text
    payload = response.json()
    fcf = payload["comparisons"]["free_cash_flow"]
    candidate = next(node for node in payload["evidence"] if node["ref"]["kind"] == "candidate"
                     and node["ref"]["metric"] == "capital_expenditures" and node["ref"]["side"] == side)
    assert "nonfinite_value" not in candidate["data"]["dispositions"]
    if value == "-5":
        assert "negative_capex_payment" in candidate["data"]["dispositions"]
        assert fcf[side]["status"] == "unavailable" and fcf[side]["value"] is None
    else:
        assert "negative_capex_payment" not in candidate["data"]["dispositions"]
        expected = ("14" if side == "earlier" else "20") if value == "0" else ("10" if side == "earlier" else "15")
        assert fcf["status"] == "available" and Decimal(fcf[side]["value"]) == Decimal(expected)
