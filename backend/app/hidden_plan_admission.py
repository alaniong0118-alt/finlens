"""Dormant, development-only selection of canonical Insights results.

No route, generation, display or financial policy entry point imports this module.
Trusted Python wiring supplies a controlled read session and explicit constraints;
it must use the existing read-session/cleanup discipline. This is an untrusted
JSON boundary, not a sandbox against privileged Python or database writers.

prepare_snapshot alone creates owned state; serialized projections and IDs cannot
create authority. Sessions are never opened, closed or committed here. A later
consumer must call revalidate with a current controlled read session immediately
before its own handoff, and separately satisfy cleanup/publication requirements.
Cooperative checkpoints cannot interrupt an in-progress DB/native operation.
"""
from dataclasses import dataclass
import json
import time
from threading import Event
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select

from app import config, financial_insights_contract as contract
from app import financial_insights_service as insights
from app import financial_metric_registry as registry
from app import financial_insights_schemas as schemas
from app.activation_lifecycle import LaunchRejected, _financial_read
from app.financial_insights_schemas import InsightsResponse
from app.financial_metrics_service import UnknownCompany
from app.models import Company, CompanyRefreshState

VERSION = "hidden-plan-selection-v1"
OPERATIONS = ("VALUE", "CHANGE", "PERCENT_CHANGE")
SNAPSHOT_BYTES = 16 * 1024
RESULT_CELLS = 4
NODES = 128
EDGES = 256
PLAN_BYTES = 4 * 1024
JSON_DEPTH = 4
VISITS = 10_000
SECONDS = 1.0

Status = Literal["admitted_hidden", "model_abstained", "rejected_contract",
                 "cancelled", "limit_exceeded", "snapshot_invalid"]


class ExplicitRequest(BaseModel):
    """Structured constraints only; this is not natural-language recognition.

    VALUE pins one side of the two-year inventory. CHANGE is the existing
    absolute/percentage-point change; PERCENT_CHANGE is existing relative change.
    No caller-supplied source category, facts, support or authorization field.
    """
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    ticker: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.-]{0,9}$")
    company_cik: str = Field(pattern=r"^[0-9]{10}$")
    metric: Literal["revenue", "operating_income", "net_income", "operating_margin",
                    "net_margin", "operating_cash_flow", "free_cash_flow"]
    earlier_fiscal_year: int = Field(ge=1900, le=2099)
    later_fiscal_year: int = Field(ge=1900, le=2099)
    data_version: int = Field(ge=0, le=9_007_199_254_740_991)
    facts_version: int = Field(ge=0, le=9_007_199_254_740_991)
    evidence_version: int = Field(ge=0, le=9_007_199_254_740_991)
    operation: Literal["VALUE", "CHANGE", "PERCENT_CHANGE"]
    value_side: Literal["earlier", "later"] | None = None

    @model_validator(mode="after")
    def constraints(self):
        if (self.earlier_fiscal_year >= self.later_fiscal_year
                or max(self.facts_version, self.evidence_version) > self.data_version
                or (self.operation == "VALUE") != (self.value_side is not None)):
            raise ValueError("Invalid explicit selection constraints")
        return self


@dataclass(frozen=True)
class Diagnostic:
    """Internal and deliberately without display prose, numbers or source URLs.

    model_abstained describes a model decision only; it says nothing about data
    availability. admitted_hidden is never permission to publish an answer.
    """
    status: Status
    snapshot_id: str | None = None
    statement_key: str | None = None
    operation: str | None = None


class _Stop(Exception):
    def __init__(self, status):
        self.status = status


class Cancellation:
    """One-way cancellation shared by trusted preparation/admission wiring."""
    def __init__(self):
        self._event = Event()

    def cancel(self):
        self._event.set()

    def is_set(self):
        return self._event.is_set()


def _expect(condition, status="snapshot_invalid"):
    if not condition:
        raise _Stop(status)


class _Work:
    def __init__(self, checkpoint, clock):
        self.checkpoint, self.clock = checkpoint, clock
        self.started, self.visits = clock(), 0

    def deadline(self):
        self.checkpoint()
        _expect(self.clock() - self.started < SECONDS, "limit_exceeded")

    def visit(self):
        self.visits += 1
        _expect(self.visits <= VISITS, "limit_exceeded")
        self.deadline()

    def walk(self, values):
        for value in values:
            self.visit()
            yield value

    def check(self, name, value):
        # Graph closure uses the inherited canonical depth, never a new policy.
        _expect(name == "depth" and 0 <= value <= contract.LIMITS["depth"])


class _PreparationBudget(contract.Budget):
    def __init__(self, checkpoint, clock):
        self.checkpoint = checkpoint
        super().__init__(clock)

    def deadline(self, reserve=0):
        self.checkpoint()
        super().deadline(reserve)

    def visit(self):
        self.checkpoint()
        super().visit()


class _Reads:
    """Check both sides of native reads; never return a late cancelled result."""
    def __init__(self, session, budget):
        self.session, self.budget = session, budget

    def execute(self, *args, **kwargs):
        self.budget.deadline()
        value = self.session.execute(*args, **kwargs)
        try:
            self.budget.deadline()
        except BaseException:
            # This result alone is owned here. The caller still owns session
            # cleanup, including invalidation if closing its transaction fails.
            try:
                value.close()
            except Exception:
                pass
            raise
        return value


def _policy():
    profile = config.server_profile()
    _expect(profile.name == "development")
    configuration = insights.registry_guard()
    # Capture owning-module values, not caller assertions or imported copies.
    return (profile, configuration, registry.SELECTION_POLICY,
            tuple(registry.METRICS.items()), tuple(registry.REVENUE_CONCEPTS.items()),
            registry.REVENUE_EQUIVALENCES, tuple(contract.DEPENDENCIES.items()),
            registry.GROSS_MARGIN_COVERAGE, contract.METRICS, contract.HEADLINE,
            tuple(contract.LIMITS.items()), schemas.InsightStatement.model_fields["ruleset"].default, VERSION)


def _policy_matches(expected):
    current = _policy()
    _expect(current[0] is expected[0] and current[2:] == expected[2:])
    insights.registry_guard(expected[1])


def _identity(session, request, budget):
    budget.deadline()
    row = _Reads(session, budget).execute(select(
        Company.ticker, Company.cik, CompanyRefreshState.data_version,
        CompanyRefreshState.facts_version, CompanyRefreshState.evidence_version,
    ).join(CompanyRefreshState, CompanyRefreshState.company_cik == Company.cik)
        .where(Company.ticker == request.ticker).limit(2)).mappings().one_or_none()
    _expect(row is not None)
    expected = (request.ticker, request.company_cik, request.data_version,
                request.facts_version, request.evidence_version)
    actual = tuple(row[k] for k in ("ticker", "cik", "data_version", "facts_version", "evidence_version"))
    _expect(actual == expected and all(type(v) is int for v in actual[2:]))
    budget.deadline()


def _fields(value, budget, max_depth):
    stack = [(value, 0)]
    while stack:
        budget.visit()
        item, depth = stack.pop()
        _expect(depth <= max_depth, "limit_exceeded")
        if type(item) is dict:
            for key, child in budget.walk(item.items()):
                _expect(type(key) is str, "rejected_contract")
                stack.append((child, depth + 1))
        elif type(item) is list:
            stack.extend((child, depth + 1) for child in budget.walk(item))
        else:
            _expect(item is None or type(item) in (str, int, bool), "rejected_contract")


def _encode(value, budget, ceiling):
    chunks, size = [], 0
    _fields(value, budget, 32)
    for token in json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":")).iterencode(value):
        budget.visit()
        chunk = token.encode("utf-8")
        size += len(chunk)
        _expect(size <= ceiling, "limit_exceeded")
        chunks.append(chunk)
    budget.deadline()
    return b"".join(chunks)


def _decode_plan(raw, budget):
    _expect(type(raw) in (bytes, str), "rejected_contract")
    _expect(len(raw) <= PLAN_BYTES, "limit_exceeded")
    # Wire contract: strict UTF-8, no BOM or literal NUL. In particular, never
    # let json.loads(bytes) autodetect UTF-16/32 after a different byte scan.
    # Encoding str inputs also rejects literal unpaired Unicode surrogates.
    text = raw.decode("utf-8", errors="strict") if type(raw) is bytes else raw
    size = len(raw) if type(raw) is bytes else len(text.encode("utf-8", errors="strict"))
    _expect(size <= PLAN_BYTES, "limit_exceeded")
    _expect(not text.startswith("\ufeff") and "\x00" not in text, "rejected_contract")
    # Bound nesting BEFORE the native JSON parser, ignoring escaped string data.
    # Both stages must consume exactly this same decoded text.
    depth, string, escaped = 0, False, False
    for char in budget.walk(text):
        if string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                string = False
        elif char == '"':
            string = True
        elif char in ("[", "{"):
            depth += 1
            _expect(depth <= JSON_DEPTH, "limit_exceeded")
        elif char in ("]", "}"):
            depth -= 1
            _expect(depth >= 0, "rejected_contract")

    def pairs(items):
        result = {}
        for key, value in budget.walk(items):
            _expect(key not in result, "rejected_contract")
            result[key] = value
        return result

    def constant(_):
        raise _Stop("rejected_contract")

    result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    _fields(result, budget, JSON_DEPTH)
    _expect(type(result) is dict, "rejected_contract")
    budget.deadline()
    return result


def _closure(graph, statement, category):
    roots = statement.financial if category == "F" else statement.diagnostic
    _expect(all(r.category == category for r in graph.budget.walk(roots)))
    closure = graph.closure(roots)
    # Every canonical statement supplies the entire exact closure. Do not repair
    # a missing source or silently accept extraneous same-scope references.
    _expect(roots == closure)
    return closure


def _project(result, request, snapshot_id, budget):
    _expect((result.ticker, result.company_cik, result.data_version, result.facts_version,
             result.evidence_version, result.earlier_fiscal_year, result.later_fiscal_year) == (
        request.ticker, request.company_cik, request.data_version, request.facts_version,
        request.evidence_version, request.earlier_fiscal_year, request.later_fiscal_year))
    _expect(result.mode == "compare" and result.selection_policy == registry.SELECTION_POLICY)
    graph = contract.Graph(result.scope, budget)
    for node in budget.walk(result.evidence):
        _expect(node.ref.key not in graph.nodes and node.ref.scope == result.scope)
        graph.nodes[node.ref.key] = node
    cells, limitations, retained = {}, {}, {}
    for statement in budget.walk(result.statements):
        selectable = statement.metric == request.metric and statement.rule in OPERATIONS
        limitation = (statement.rule == "LIMITATION" or statement.metric == request.metric
                      and statement.rule in {"UNAVAILABLE", "PERCENT_UNAVAILABLE", "PRECISION_NOTICE"})
        if not (selectable or limitation):
            continue
        _expect(statement.key not in cells and statement.key not in limitations)
        financial = _closure(graph, statement, "F")
        diagnostic = _closure(graph, statement, "D")
        if selectable:
            _expect(bool(financial) and not diagnostic)
            cells[statement.key] = statement
            _expect(len(cells) <= RESULT_CELLS, "limit_exceeded")
        else:
            limitations[statement.key] = statement
        for ref in budget.walk((*financial, *diagnostic)):
            retained[ref.key] = graph.nodes[ref.key]
            _expect(len(retained) <= NODES, "limit_exceeded")
    _expect(any(s.rule == "LIMITATION" for s in limitations.values()))
    _expect(sum(len(n.edges) for n in budget.walk(retained.values())) <= EDGES, "limit_exceeded")
    # The public projection is bounded selection vocabulary, not transferable
    # authority. Exact canonical statements/node data remain in owned state.
    projection = _encode(dict(version=VERSION, snapshot_id=snapshot_id,
        request=request.model_dump(), selection_policy=result.selection_policy,
        ruleset=schemas.InsightStatement.model_fields["ruleset"].default,
        results=[dict(statement_key=s.key, operation=s.rule, side=s.side) for s in cells.values()],
        limitations=[s.key for s in limitations.values()],
        node_count=len(retained), edge_count=sum(len(n.edges) for n in retained.values())), budget, SNAPSHOT_BYTES)
    return projection, cells, limitations, retained


@dataclass(frozen=True)
class _CanonicalSelection:
    """Owned canonical content for future internal consumers; never wire output."""
    statement: bytes
    financial_nodes: bytes
    limitations: bytes
    limitation_financial_nodes: bytes
    diagnostic_nodes: bytes


class HiddenSnapshot:
    """Factory-owned, cancellable state. Projection/ID are correlation only.

    There is intentionally no deserialize/import constructor and no public
    method that returns display content. revalidate returns a diagnostic again.
    """
    def __init__(self):
        raise TypeError("Use prepare_snapshot with a controlled session")

    def cancel(self):
        self._cancel.cancel()  # irreversible for this snapshot's lifetime

    @property
    def snapshot_id(self):
        return self._snapshot_id

    @property
    def projection(self):
        return self._projection

    def _checkpoint(self):
        _expect(not self._cancel.is_set(), "cancelled")
        _expect(self._valid)
        with _financial_read():
            pass
        _policy_matches(self._policy)

    def _run(self, session, raw=None, diagnostic=None):
        self._selection = None
        work = _Work(self._checkpoint, self._clock)
        try:
            with _financial_read(), contract.budget_scope(_PreparationBudget(self._checkpoint, self._clock)):
                work.deadline()
                _identity(session, self._request, work)
                if diagnostic is None:
                    plan = _decode_plan(raw, work)
                    base = {"version", "snapshot_id", "decision"}
                    _expect(plan.get("version") == VERSION and plan.get("snapshot_id") == self.snapshot_id,
                            "rejected_contract")
                    if plan.get("decision") == "abstain":
                        _expect(set(plan) == base, "rejected_contract")
                        outcome = Diagnostic("model_abstained", self.snapshot_id)
                    else:
                        _expect(plan.get("decision") == "select" and set(plan) == base | {"operation", "statement_key"},
                                "rejected_contract")
                        _expect(type(plan["operation"]) is str and type(plan["statement_key"]) is str,
                                "rejected_contract")
                        _expect(plan["operation"] == self._request.operation, "rejected_contract")
                        outcome = self._select(plan["statement_key"], plan["operation"], work)
                else:
                    # Identity-owned diagnostic, not a caller-created status flag.
                    _expect(diagnostic is self._last and diagnostic.status == "admitted_hidden")
                    outcome = self._select(diagnostic.statement_key, diagnostic.operation, work)
                _identity(session, self._request, work)
                work.deadline()
            work.deadline()  # includes lifecycle exit; never deliver late results
            self._last = outcome
            return outcome
        except _Stop as error:
            return self._failure(error.status)
        except (contract.InsightsFailure, LaunchRejected, UnknownCompany) as error:
            return self._failure(_status(error))
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            return self._failure("rejected_contract" if diagnostic is None else "snapshot_invalid")
        except Exception:
            return self._failure("snapshot_invalid")

    def _failure(self, status):
        if status in {"cancelled", "snapshot_invalid"}:
            self._valid = False
        self._selection = self._last = None
        return Diagnostic(status, self.snapshot_id)

    def _select(self, key, operation, work):
        statement = self._cells.get(key)
        _expect(statement is not None and statement.rule == operation and operation == self._request.operation,
                "rejected_contract")
        _expect(operation != "VALUE" or statement.side == self._request.value_side, "rejected_contract")
        graph = contract.Graph(self._scope, work)
        graph.nodes = self._nodes
        financial = _closure(graph, statement, "F")
        _expect(bool(financial) and not statement.diagnostic)
        _expect(any(s.rule == "LIMITATION" for s in self._limitations.values()))
        diagnostics, limitation_financial = {}, {}
        for limitation in work.walk(self._limitations.values()):
            for ref in work.walk(_closure(graph, limitation, "F")):
                limitation_financial[ref.key] = graph.nodes[ref.key]
            for ref in work.walk(_closure(graph, limitation, "D")):
                diagnostics[ref.key] = graph.nodes[ref.key]
        # Recover the entire canonical closure and every limitation server-side.
        # Diagnostic nodes stay in a separate slot, never financial support.
        self._selection = _CanonicalSelection(
            _encode(statement.model_dump(mode="json"), work, contract.LIMITS["output_bytes"]),
            _encode([graph.nodes[r.key].model_dump(mode="json") for r in financial], work, contract.LIMITS["output_bytes"]),
            _encode([s.model_dump(mode="json") for s in self._limitations.values()], work, contract.LIMITS["output_bytes"]),
            _encode([n.model_dump(mode="json") for n in limitation_financial.values()], work, contract.LIMITS["output_bytes"]),
            _encode([n.model_dump(mode="json") for n in diagnostics.values()], work, contract.LIMITS["output_bytes"]))
        return Diagnostic("admitted_hidden", self.snapshot_id, key, operation)

    def admit(self, session, raw_plan):
        """Interpret bounded untrusted bytes only after checking owned identity."""
        return self._run(session, raw_plan)

    def revalidate(self, session, diagnostic):
        """Mandatory future handoff gate using a current controlled read session."""
        if type(diagnostic) is not Diagnostic or diagnostic is not self._last:
            return self._failure("snapshot_invalid")
        return self._run(session, diagnostic=diagnostic)


def _status(error):
    return ("limit_exceeded" if isinstance(error, contract.InsightsFailure) and error.code in {
        "INSIGHTS_RESOURCE_LIMIT", "INSIGHTS_DEADLINE_EXCEEDED"} else "snapshot_invalid")


def prepare_snapshot(session, request, *, cancellation=None, clock=time.monotonic):
    """Build canonical evidence internally; return HiddenSnapshot or Diagnostic.

    No caller payload/facts/snapshot/source categories/authorized flag accepted.
    The clock is a trusted test seam, not plan input. Production default is the
    monotonic clock. Caller must preserve controlled read/cleanup discipline.
    """
    try:
        _expect(type(request) is ExplicitRequest)
        request = ExplicitRequest.model_validate(request.model_dump())
        _expect(cancellation is None or type(cancellation) is Cancellation)
        state = object.__new__(HiddenSnapshot)
        state._cancel, state._valid = cancellation or Cancellation(), True
        state._clock, state._request, state._policy = clock, request, _policy()
        state._last = state._selection = None
        state._snapshot_id = uuid4().hex
        budget = _PreparationBudget(state._checkpoint, clock)
        with _financial_read(), contract.budget_scope(budget):
            _identity(session, request, budget)
            body, configuration = insights.build_insights(_Reads(session, budget), request.ticker,
                request.data_version, "compare", request.earlier_fiscal_year, request.later_fiscal_year, budget)
            budget.deadline()
            insights.registry_guard(configuration)
            result = InsightsResponse.model_validate_json(body)
            budget.deadline()
            work = _Work(state._checkpoint, clock)
            state._projection, state._cells, state._limitations, state._nodes = _project(
                result, request, state.snapshot_id, work)
            state._scope = result.scope
            _identity(session, request, budget)
            work.deadline()
            budget.deadline()
        state._checkpoint()
        budget.deadline()
        return state
    except _Stop as error:
        return Diagnostic(error.status)
    except (contract.InsightsFailure, LaunchRejected, UnknownCompany) as error:
        return Diagnostic(_status(error))
    except (ValidationError, ValueError, TypeError, KeyError):
        return Diagnostic("snapshot_invalid")
    except Exception:
        return Diagnostic("snapshot_invalid")
