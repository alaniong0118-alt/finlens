"""Dormant session cash-flow orchestration; no production composition is installed.

Only trusted server code may compose custody, ownership and admission. The
public entry accepts selectors, never paths, providers or caller-made decisions.
Tests replace the private composition boundary; those replacements confer no
production source, identity, rights or custody authority.
"""
from dataclasses import dataclass
import hashlib

from app import financial_metric_engine as engine
from app import session_sec_inline as parser
from app.research_contracts import KeyRef, SessionArtifactRef
from app.session_financial_contracts import SessionFinancialResult, SessionInput, SessionObservationRef

METRICS = frozenset({"operating_cash_flow", "capital_expenditures", "free_cash_flow"})
SELECTION_VERSION = "session-sec-cashflow-selection-v1"


class SessionResearchFailure(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _ResolvedAccess:
    """Private trusted-composition output, not a caller-supplied capability."""
    artifact: SessionArtifactRef
    session_revision: int
    artifact_revision: int
    identity: parser.DocumentIdentity
    source_revision: KeyRef
    rights_revision: KeyRef
    mapping_revision: str
    operations: frozenset[str]


def _server_composition():
    # No source, rights, identity, custody or ownership provider is installed.
    return None


def _require(condition, reason):
    if not condition:
        raise SessionResearchFailure(reason)


def _check_access(access, session_key, session_revision, artifact_key, artifact_revision):
    _require(type(access) is _ResolvedAccess and type(access.artifact) is SessionArtifactRef, "access_unavailable")
    ref = access.artifact
    _require(ref.origin == "official_sec" and ref.session_key == session_key and ref.artifact_key == artifact_key
             and access.session_revision == session_revision and access.artifact_revision == artifact_revision
             and ref.source_revision_key is not None and ref.rights_policy_key is not None
             and ref.admission_record_key is not None and ref.source_revision_key == access.source_revision
             and access.mapping_revision == parser.PROFILE
             and type(access.rights_revision) is KeyRef and access.rights_revision.namespace == "rights_policy"
             and access.rights_revision == ref.rights_policy_key
             and type(access.operations) is frozenset and {"parse", "calculate", "display"} <= access.operations
             and type(access.identity) is parser.DocumentIdentity
             and ref.entity_key.namespace == "sec_cik" and ref.entity_key.id == access.identity.cik,
             "admission_unavailable")


class _CashPermissions:
    """This fixed subset never requests revenue or margin authority."""
    def select_revenue(self, _candidates):
        raise SessionResearchFailure("unsupported_metric")

    def denominator(self, _revenue, _numerator, _period):
        raise SessionResearchFailure("unsupported_metric")

    def gross_margin(self, _gross, _revenue):
        raise SessionResearchFailure("unsupported_metric")

    def inventory(self, _names, _kind, _end):
        raise SessionResearchFailure("unsupported_metric")


class SessionFinancialResearch:
    def calculate(self, token, session_key, session_revision, artifact_key, artifact_revision,
                  metric, fiscal_year, *, cancellation=None):
        _require(type(session_key) is KeyRef and session_key.namespace == "session"
                 and type(artifact_key) is KeyRef and artifact_key.namespace == "artifact"
                 and type(session_revision) is int and 0 < session_revision < 2**63
                 and type(artifact_revision) is int and 0 < artifact_revision < 2**63
                 and type(metric) is str and metric in METRICS
                 and type(fiscal_year) is int and 1900 <= fiscal_year <= 9999, "invalid_selector")
        composition = _server_composition()
        _require(composition is not None, "admission_unavailable")
        # The composition owns actual token verification, custody, source/rights
        # checks and cancellation. It returns detached metadata before any parse.
        access = composition.resolve_access(token, session_key, session_revision, artifact_key,
                                            artifact_revision, cancellation=cancellation)
        _check_access(access, session_key, session_revision, artifact_key, artifact_revision)
        composition.checkpoint(cancellation)
        original = composition.read_original(access)
        _require(type(original) is bytes and hashlib.sha256(original).hexdigest() == access.artifact.artifact_sha256,
                 "artifact_changed")
        inventory = parser.inventory_original(original, access.identity,
                                              _checkpoint=lambda: composition.checkpoint(cancellation))
        composition.checkpoint(cancellation)
        _require(inventory.sha256 == access.artifact.artifact_sha256, "artifact_changed")
        eligible = [fact for fact in inventory.facts if fact.kind == "annual" and not fact.dimensions
                    and fact.end.year == fiscal_year]
        intervals = {(fact.start, fact.end) for fact in eligible}
        _require(len(intervals) == 1, "annual_period_unavailable_or_ambiguous")
        start, end = next(iter(intervals))
        rows, facts = [], {}
        for fact in eligible:
            _require((fact.start, fact.end) == (start, end), "annual_period_mismatch")
            name = "operating_cash_flow" if fact.concept in parser.METRICS["operating_cash_flow"].concepts else "capital_expenditures"
            key = engine.SessionObservationKey(inventory.sha256, fact.fact_id)
            _require(key not in facts, "duplicate_observation_identity")
            facts[key] = fact
            rows.append(engine.Observation(key, fact.concept, fact.value, "USD", fact.start, fact.end,
                                           "annual", access.identity.filed, access.identity.form,
                                           access.identity.accession, (name,)))
        calculator = engine.FinancialMetricEngine(tuple(rows), _CashPermissions(),
            missing_source_reason="No compatible admitted session observation for this period, concept and unit.")
        result = calculator.observation(metric, engine.Period("annual", start, end, fiscal_year, "FY", "annual_period_end_year"))

        def project(ref):
            fact = facts[ref.observation.reference]
            return SessionObservationRef(access.artifact, fact.fact_id, fact.context_id, ref.metric,
                                         fact.value, "USD", fact.start, fact.end)

        receipt = SessionFinancialResult(access.artifact, metric, fiscal_year, result.status, result.value,
            result.reason, start, end, result.formula, SELECTION_VERSION, access.mapping_revision,
            inventory.profile, tuple(project(ref) for ref in result.provenance),
            tuple(project(ref) for ref in result.alternatives),
            tuple(SessionInput(item.role, item.metric, item.value, item.unit,
                               tuple(project(ref) for ref in item.references)) for item in result.inputs))
        receipt.encode()  # Enforce complete detached result size before reauthorization.
        composition.checkpoint(cancellation)
        final = composition.resolve_access(token, session_key, session_revision, artifact_key,
                                           artifact_revision, cancellation=cancellation)
        _check_access(final, session_key, session_revision, artifact_key, artifact_revision)
        _require(final == access, "admission_changed")
        composition.checkpoint(cancellation)
        return receipt
