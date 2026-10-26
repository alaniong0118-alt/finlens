"""Closed reference graph, resource accounting and bounded wire publication."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal, localcontext
import json
import time
from types import MappingProxyType

from app.financial_insights_schemas import (
    DiagnosticReference, EvidenceNode, FinancialReference, InsightStatement,
)

METRICS = ("revenue", "operating_income", "net_income", "operating_margin", "net_margin",
           "operating_cash_flow", "free_cash_flow")
HEADLINE = ("revenue", "operating_margin", "net_margin", "operating_cash_flow", "free_cash_flow")
DEPENDENCIES = MappingProxyType({"operating_margin": ("operating_income", "revenue"),
                               "net_margin": ("net_income", "revenue"),
                               "free_cash_flow": ("operating_cash_flow", "capital_expenditures")})
LIMITS = MappingProxyType(dict(facts=10000, input_bytes=8*1024*1024, eligible=10000,
    group=256, sources=2048, candidates=4096, slot_candidates=256, windows=256,
    year_windows=16, observations=64, operands=32, rejections=256, nodes=8192,
    edges=16384, statements=35, statement_refs=8192, references=32768, depth=6,
    work=2000000, output_bytes=4*1024*1024, research_queries=5, cursors=20))
FAILURES = MappingProxyType({
    "INSIGHTS_RESOURCE_LIMIT": (503, "Financial insights exceed the supported research limits."),
    "INSIGHTS_EVIDENCE_INCOMPLETE": (503, "Complete financial evidence could not be verified."),
    "INSIGHTS_CONFIGURATION_UNSUPPORTED": (503, "Financial insights are unavailable for this configuration."),
    "INSIGHTS_CONTRACT_INVALID": (500, "Financial insights could not be validated."),
    "INSIGHTS_DEADLINE_EXCEEDED": (504, "Financial insights could not complete in time."),
})


class InsightsFailure(RuntimeError):
    def __init__(self, code="INSIGHTS_CONTRACT_INVALID"):
        self.code = code
        self.status, self.public_message = FAILURES[code]
        super().__init__(self.public_message)


def require(condition, code="INSIGHTS_CONTRACT_INVALID"):
    if not condition:
        raise InsightsFailure(code)


class Budget:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.counts = {}

    def deadline(self, reserve=0):
        require(self.clock() - self.started + reserve < 20, "INSIGHTS_DEADLINE_EXCEEDED")

    def check(self, name, value):
        require(type(value) is int and 0 <= value <= LIMITS[name], "INSIGHTS_RESOURCE_LIMIT")

    def add(self, name, amount=1):
        value = self.counts.get(name, 0) + amount
        self.check(name, value)
        self.counts[name] = value

    def visit(self):
        self.add("work")
        if self.counts["work"] % 128 == 0:
            self.deadline()

    def walk(self, values):
        for value in values:
            self.visit()
            yield value

    def cursor(self, research=False):
        self.deadline(1.5)
        self.add("cursors")
        if research:
            self.add("research_queries")


current_budget = ContextVar("finlens_insights_budget", default=None)


@contextmanager
def budget_scope(budget):
    token = current_budget.set(budget)
    try:
        yield
    finally:
        current_budget.reset(token)


def text_value(value):
    """Matches the loader's explicit PostgreSQL rendering, including NULL."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def checked_text(value, limit):
    require(len(value.encode("utf-8")) <= limit, "INSIGHTS_RESOURCE_LIMIT")
    return value


def ref_key(ref):
    return ref.key


def reference(scope, category, kind, metric=None, side=None, role=None, window=None, suffix=None):
    key = "|".join(str(x or "") for x in (category, kind, metric, side, role, window, suffix))
    checked_text(key, 192)
    checked_text(scope, 192)
    cls = FinancialReference if category == "F" else DiagnosticReference
    require(category == "D" or kind in {"comparison", "observation", "operand", "source"})
    return cls(scope=scope, kind=kind, key=key, metric=metric, side=side, role=role, window=window)


def ordered(refs):
    refs = list(refs)
    require(len({r.key for r in refs}) == len(refs))
    return sorted(refs, key=ref_key)


class Graph:
    def __init__(self, scope, budget):
        self.scope, self.budget = scope, budget
        self.nodes = {}

    def put(self, ref, data, edges=()):
        self.budget.visit()
        edges = ordered(edges)
        node = EvidenceNode(ref=ref, data=data, edges=edges)
        if ref.key in self.nodes:
            require(self.nodes[ref.key] == node)
            return ref
        self.budget.check("nodes", len(self.nodes)+1)
        self.budget.add("edges", len(edges))
        if ref.kind in {"observation", "operand", "rejection", "candidate"}:
            self.budget.add({"observation": "observations", "operand": "operands",
                             "rejection": "rejections", "candidate": "candidates"}[ref.kind])
        self.nodes[ref.key] = node
        return ref

    def closure(self, roots):
        found = {}
        stack = [(r, (), 0) for r in roots]
        while stack:
            self.budget.visit()
            ref, path, depth = stack.pop()
            self.budget.check("depth", depth)
            require(ref.key not in path)
            node = self.nodes.get(ref.key)
            require(node is not None and node.ref == ref and ref.scope == self.scope)
            if ref.key in found:
                continue
            found[ref.key] = ref
            for edge in self.budget.walk(node.edges):
                require(edge.category == ref.category)
                self._edge(ref, edge)
                stack.append((edge, (*path, ref.key), depth+1))
        return ordered(found.values())

    def _edge(self, parent, child):
        allowed = {"comparison": {"observation", "rejection", "window"},
                   "observation": {"operand", "source"}, "operand": {"observation"},
                   "source": set(), "candidate": {"source"},
                   "rejection": {"candidate", "source", "window"}, "window": {"source"}}
        if parent.category == "D":
            allowed["observation"] |= {"candidate", "rejection", "window"}
            allowed["operand"] |= {"candidate", "rejection"}
        require(child.kind in allowed[parent.kind])
        if parent.kind == "comparison" and child.kind == "observation":
            require(child.metric == parent.metric and child.side in {"earlier", "later"})
        if parent.kind == "observation" and child.kind == "operand":
            require(child.metric == parent.metric and child.side == parent.side
                    and child.role in DEPENDENCIES.get(parent.metric, ()))
        if parent.kind == "operand" and child.kind == "observation":
            require(child.metric == parent.role and child.side == parent.side
                    and child.window == parent.window)

    def validate(self):
        for node in self.budget.walk(self.nodes.values()):
            self.closure([node.ref])


def exact_decimal(value):
    return checked_text(str(value), 128)


def transition(x, y, direction):
    require(direction == ("increase" if y > x else "decrease" if y < x else "no_change"))
    if x < 0 and y < 0:
        return {"increase": "became less negative; remained negative", "decrease": "became more negative",
                "no_change": "was unchanged and negative"}[direction]
    if x == y:
        return "was unchanged at zero" if x == 0 else "was unchanged and positive"
    if x < 0:
        return "increased from a negative value to zero" if y == 0 else "increased from negative to positive"
    if x == 0:
        return "increased from zero to a positive value" if y > 0 else "decreased from zero to a negative value"
    if y <= 0:
        return "decreased from a positive value to zero" if y == 0 else "decreased from positive to negative"
    return "increased and remained positive" if y > x else "decreased and remained positive"


def display(value, unit):
    with localcontext() as context:
        context.prec = max(40, len(value.as_tuple().digits)+abs(value.adjusted())+10)
        return f"{value*100:.2f}%" if unit == "ratio" else f"{value:,.2f} USD"


def delta_display(value, unit, exact=False):
    with localcontext() as context:
        context.prec = max(40, len(value.as_tuple().digits)+abs(value.adjusted())+10)
        if unit == "ratio":
            return (str(value*100) if exact else f"{value*100:.2f}") + " percentage points"
        return (exact_decimal(value) if exact else f"{value:,.2f}") + " USD"


def precision_hidden(comp):
    return comp.absolute_change != 0 and (
        display(comp.earlier.value, comp.earlier.unit) == display(comp.later.value, comp.later.unit)
        or delta_display(abs(comp.absolute_change), comp.earlier.unit) == delta_display(Decimal(0), comp.earlier.unit)
        or comp.percentage_status == "available" and comp.percentage_change is not None
        and display(abs(comp.percentage_change), "ratio") == display(Decimal(0), "ratio"))


def percentage_display(value):
    if value != 0 and display(abs(value), "ratio") == display(Decimal(0), "ratio"):
        with localcontext() as context:
            context.prec = max(40, len(value.as_tuple().digits)+abs(value.adjusted())+10)
            return exact_decimal(value*100) + "%"
    return display(value, "ratio")


def statement(rule, key, text, financial=(), diagnostic=(), **kwargs):
    return InsightStatement(rule=rule, key=key, text=checked_text(text, 2048),
                            financial=ordered(financial), diagnostic=ordered(diagnostic), **kwargs)


def validate_statement_limits(actual, budget):
    budget.check("statements", len(actual))
    require(len({s.key for s in actual}) == len(actual))
    total = 0
    for item in budget.walk(actual):
        ordered(item.financial)
        ordered(item.diagnostic)
        count = len(item.financial)+len(item.diagnostic)
        budget.check("statement_refs", count)
        total += count
        budget.check("references", total)


def validate_statements(actual, expected, budget):
    validate_statement_limits(actual, budget)
    # Equality includes types, scope, all roles, exact set/order, predicates/text.
    require(actual == expected)


def bounded_json(payload, budget):
    """Never allocate a response string larger than the byte ceiling."""
    validate_fields(payload, budget)
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    chunks, size = [], 0
    for token in encoder.iterencode(payload):
        budget.visit()
        encoded = token.encode("utf-8")
        size += len(encoded)
        budget.check("output_bytes", size)
        chunks.append(encoded)
    budget.deadline()
    return b"".join(chunks)


def validate_fields(payload, budget):
    stack = [(payload, "", 0)]
    while stack:
        budget.visit()
        value, field, depth = stack.pop()
        require(depth <= 32)
        if isinstance(value, dict):
            for key, child in budget.walk(value.items()):
                require(type(key) is str)
                checked_text(key, 192)
                stack.append((child, key, depth+1))
        elif isinstance(value, (list, tuple)):
            for child in budget.walk(value):
                stack.append((child, field, depth+1))
        elif isinstance(value, str):
            limit = 2048 if field == "text" else 1024 if field in {"reason", "parent_reason", "selection_policy", "percentage_reason"} else (
                800 if field == "company_name" else 400 if field in {"metric", "stored_metric", "source", "original_concept"}
                else 192 if field in {"scope", "key", "sec_url"} else 128)
            checked_text(value, limit)
        else:
            require(value is None or type(value) in {int, bool})
