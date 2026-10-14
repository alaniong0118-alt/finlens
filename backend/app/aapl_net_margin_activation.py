"""Disabled internal operator entry point; never called by startup or requests.

Changing the source gate requires separate activation approval and Astra review.
No environment variable enables it. No permission is registered on import. Even
with the gate enabled, a trusted operator must explicitly acknowledge the exact
reviewed reference. That acknowledgement is not authentication or SEC provenance.
"""

from app.release_policy import development_only
from threading import Lock


# Preparation only. Keep false until separately approved/reviewed activation.
_ACTIVATION_ENABLED = False
_activation_lock = Lock()


def _require_launcher():
    from app.activation_lifecycle import require_validation_owner
    return require_validation_owner()


@development_only
def activate_aapl_net_margin(*, operator_authorized=False, reviewed_ref=None):
    """Install the reviewed pair in this process only after fresh verification.

    Disabled calls return False before imports/configuration/database/evidence I/O.
    Enabled failures raise and leave registries untouched. There is no caller-
    supplied store, session, fact subset, permission, policy or synthetic proof.
    This internal function has no API/CLI/startup wiring and no persistent effects.
    """
    if _ACTIVATION_ENABLED is not True:
        return False

    controller = _require_launcher()  # The bool/reference alone grant no authority.

    import os
    from pathlib import Path
    from xml.etree import ElementTree as ET
    from xml.parsers import expat
    from sqlalchemy import select, text
    from sqlalchemy.exc import SQLAlchemyError
    from app import aapl_net_margin_proposal as proposal
    from app import revenue_scope_authorizations as auth, sec_evidence_adapter as evidence
    from app.database import SessionLocal
    from app import financial_metric_registry as registry
    from app.financial_metrics_service import load_financial_metrics
    from app.freshness_service import read_session, request_scope
    from app.models import CompanyRefreshState, FilingPublication

    require = evidence._require
    require(operator_authorized is True, "operator_authorization_required")
    require(type(reviewed_ref) is auth.ApprovalRef and type(reviewed_ref.version) is int
            and reviewed_ref == proposal.REF, "reviewed_approval_required")
    require(request_scope.get() is None, "request_context_not_permitted")
    record, policy = proposal.PROPOSED_DENOMINATOR_AUTHORIZATION, proposal.PROPOSED_EVIDENCE_POLICY
    require(record.ref == policy.ref == proposal.REF and record.metric == "net_margin"
            and record.ref.permission == "denominator:net_margin", "proposal_permission_changed")

    def registration_boundary():
        # Initial single-pair installation only; never merge/clear existing records.
        require(auth.REVENUE_SELECTION_AUTHORIZATIONS == () and auth.DENOMINATOR_AUTHORIZATIONS == ()
                and evidence.PRODUCTION_EVIDENCE_POLICIES == (), "production_registry_not_empty")
        require(registry.REVENUE_EQUIVALENCES == frozenset(), "revenue_equivalences_changed")
        active, error = auth._approval((record,), record.ref.permission, (record,))
        require(active == record and error is None, error or "invalid_approval_lineage")

    with _activation_lock:
        registration_boundary()
        try:
            configured_root = os.environ.get("FINLENS_SEC_ORIGINAL_STORE", "")
            require(configured_root and Path(configured_root).is_absolute(), "unconfigured_original_store")
            root = Path(configured_root)
            require(not root.is_symlink() and root.absolute() == root.resolve(strict=True), "redirected_store_path")
            # Create our own new session: callers cannot reuse an old snapshot or
            # pre-filter candidates. read_session sets PostgreSQL READ ONLY.
            with read_session(SessionLocal) as session:
                require(session.get_bind().dialect.name == "postgresql", "unsupported_snapshot")
                require(session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
                        and session.scalar(text("SHOW transaction_read_only")) == "on", "unsafe_database_snapshot")
                metrics = load_financial_metrics(session, proposal.REVIEWED_TICKER)
                require(metrics.company.cik == proposal.REVENUE.cik
                        and metrics.company.ticker == proposal.REVIEWED_TICKER, "issuer_identity_changed")
                raw = metrics.authorization_sources(("revenue", "net_income"),
                    proposal.REVENUE.kind, proposal.REVENUE.end)
                state = session.get(CompanyRefreshState, proposal.REVENUE.cik)
                require(state is not None and (state.data_version, state.facts_version, state.evidence_version)
                        == proposal.EXPECTED_DATA_VERSIONS, "data_versions_changed")
                publications = list(session.scalars(select(FilingPublication).where(
                    FilingPublication.company_cik == proposal.REVENUE.cik)))
                snapshot = evidence.snapshot_digest(state, publications)
                evidence._verify_policy(policy, record, raw, root, snapshot, publications)
                # Do not retain/cache SourceEvidence. Ordinary financial requests
                # must still verify their own current facts, snapshot and bytes.
        except evidence.EvidenceRejected:
            raise
        except (OSError, ValueError, KeyError, TypeError, IndexError, RuntimeError,
                SQLAlchemyError, ET.ParseError, expat.ExpatError) as error:
            raise evidence.EvidenceRejected(f"activation_verification_failed:{type(error).__name__}") from None

        registration_boundary()  # Recheck lifecycle/conflicts after I/O.
        require(_ACTIVATION_ENABLED is True, "activation_disabled_during_verification")
        require(os.environ.get("FINLENS_SEC_ORIGINAL_STORE", "") == configured_root, "store_configuration_changed")
        # Bootstrap reader admission closes before either registry store. There
        # are still two assignments, not an atomic in-memory registry snapshot.
        previous_policies = evidence.PRODUCTION_EVIDENCE_POLICIES
        previous_permissions = auth.DENOMINATOR_AUTHORIZATIONS
        published_policies, published_permissions = (policy,), (record,)
        controller.require_authority()  # Detect lost maintenance ownership after I/O.
        controller.publishing()
        try:
            # Policy first: readers in the policy-only interval abstain.
            evidence.PRODUCTION_EVIDENCE_POLICIES = published_policies
            auth.DENOMINATOR_AUTHORIZATIONS = published_permissions
        except BaseException:
            # Quarantine before cleanup; a second cleanup fault cannot admit
            # readers or permit the operator launcher to start its server.
            controller.fail()
            # Revoke our permission first, then restore our policy. Identity checks
            # prevent replacing another owner's tuples after unexpected mutation.
            # Legitimate writers must use this same lock for publication/recovery.
            try:
                if auth.DENOMINATOR_AUTHORIZATIONS is published_permissions:
                    auth.DENOMINATOR_AUTHORIZATIONS = previous_permissions
            finally:
                if evidence.PRODUCTION_EVIDENCE_POLICIES is published_policies:
                    evidence.PRODUCTION_EVIDENCE_POLICIES = previous_policies
            raise
    return True
