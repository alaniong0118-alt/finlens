"""Synthetic source/evidence fixtures only: no sessions, DB writes, network or models."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app import revenue_scope_authorizations as auth
from app.financial_metrics_service import FinancialMetrics
from app.models import FinancialFact

CUSTOMER = "RevenueFromContractWithCustomerExcludingAssessedTax"
CIK = "0000000001"
COMPANY = SimpleNamespace(cik=CIK, ticker="TEST", name="Synthetic issuer")
PRODUCTION_REGISTRIES = (
    "REVENUE_SELECTION_AUTHORIZATIONS", "DENOMINATOR_AUTHORIZATIONS", "AUTHORIZATION_WITHDRAWALS",
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    # Check actual production contents before synthetic isolation can mask them.
    for name in PRODUCTION_REGISTRIES:
        assert getattr(auth, name) == (), f"{name} must be empty before synthetic test isolation."
    for name in PRODUCTION_REGISTRIES:
        monkeypatch.setattr(auth, name, ())
    from app.database import engine
    monkeypatch.setattr(engine, "connect", lambda *a, **k: pytest.fail("Database access forbidden"))


@pytest.mark.parametrize("registry", PRODUCTION_REGISTRIES)
def test_isolation_rejects_populated_production_registry_before_any_patch(monkeypatch, registry):
    monkeypatch.setattr(auth, registry, (object(),))
    attempted_patches = []
    spy = SimpleNamespace(setattr=lambda *args: attempted_patches.append(args))
    with pytest.raises(AssertionError, match=registry):
        isolated.__wrapped__(spy)
    assert attempted_patches == []


def fact(number, concept=CUSTOMER, value="100", **changes):
    fields = dict(id=number, company_cik=CIK, metric=concept, value=Decimal(value), unit="USD",
                  period_start=date(2025, 1, 1), period_end=date(2025, 3, 31), period_type="quarter",
                  fiscal_year=2025, fiscal_period="Q1", frame=None, form="10-Q", filed=date(2025, 5, 1),
                  accession_number="0000000001-25-000001", source=f"SEC Company Facts API: {concept}",
                  created_at=datetime(2025, 5, 1))
    fields.update(changes)
    return FinancialFact(**fields)


def evidence(row, scope="consolidated_revenue"):
    text = f"Synthetic fixture only: consolidated statement {row.metric} {row.value} USD."
    return auth.SourceEvidence(auth.SourceIdentity.from_fact(row), "fixture.htm", text,
                               "Consolidated statement, current-quarter column", 0, len(text),
                               "verified-context-" + row.metric, (), scope)


def binding(item):
    return auth.EvidenceBinding(item.identity, item.fingerprint())


def selection_fixture(monkeypatch):
    rows = [fact(1), fact(2, "SalesRevenueNet")]
    proofs = tuple(evidence(row) for row in rows)
    approval = auth.SelectionAuthorization(auth.ApprovalRef("select:revenue", "fixture-selection", 1),
                                          binding(proofs[0]), tuple(binding(e) for e in proofs),
                                          "Both reviewed statement contexts cover consolidated revenue; select the pinned customer-contract observation.")
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (approval,))
    return rows, proofs, approval


def denominator_fixture(monkeypatch):
    rows = [fact(1), fact(2, "NetIncomeLoss", "20")]
    proofs = (evidence(rows[0]), evidence(rows[1], "consolidated_net_income"))
    approval = auth.DenominatorAuthorization(auth.ApprovalRef("denominator:net_margin", "fixture-denominator", 1),
                                            "net_margin", binding(proofs[0]), binding(proofs[1]),
                                            tuple(binding(e) for e in proofs), "Reviewed consolidated net income over consolidated revenue.")
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (approval,))
    return rows, proofs, approval


def summary(rows, proofs=()):
    return FinancialMetrics(COMPANY, rows, authorization_evidence=proofs).summary()


def selection_decision(rows, proofs):
    identities = tuple(auth.SourceIdentity.from_fact(row) for row in rows)
    return auth.authorize_selection(identities[0].period_scope(), identities, proofs)


def decision_for(path, rows, proofs):
    if path == "selection":
        return selection_decision(rows, proofs)
    identities = tuple(auth.SourceIdentity.from_fact(row) for row in rows)
    return auth.authorize_denominator("net_margin", identities[0], identities[1], identities, proofs)


def test_empty_permissions_preserve_component_ambiguity_and_no_metadata():
    rows = [fact(1), fact(2, "SalesRevenueNet"), fact(3, "NetIncomeLoss", "20")]
    snap = summary(rows)
    assert snap.metrics["revenue"].status == "unavailable"
    assert {s.fact_id for s in snap.metrics["revenue"].alternatives} == {1, 2}
    assert snap.metrics["net_margin"].status == "unavailable"
    assert "scope_authorization" not in snap.metrics["revenue"].model_dump(mode="json")
    assert auth.REVENUE_SELECTION_AUTHORIZATIONS == auth.DENOMINATOR_AUTHORIZATIONS == auth.AUTHORIZATION_WITHDRAWALS == ()


def test_selection_is_independent_and_preserves_original_concept_basis_and_alternatives(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    rows.append(fact(3, "NetIncomeLoss", "20"))
    snap = summary(rows, proofs)
    point = snap.metrics["revenue"]
    assert point.value == 100 and point.revenue_basis == "customer_contract"
    assert point.provenance[0].original_concept == CUSTOMER
    assert [s.fact_id for s in point.alternatives] == [2]
    assert point.scope_authorization.approval_id == approval.ref.approval_id
    assert snap.metrics["net_margin"].status == snap.metrics["operating_margin"].status == "unavailable"


def test_denominator_is_independent_and_exact_metric_only(monkeypatch):
    rows, proofs, approval = denominator_fixture(monkeypatch)
    snap = summary(rows, proofs)
    assert snap.metrics["net_margin"].value == Decimal(".2")
    assert snap.metrics["revenue"].revenue_basis == "customer_contract"
    assert snap.metrics["net_margin"].scope_authorization.permission == "denominator:net_margin"
    assert auth.authorize_denominator("gross_margin", proofs[0].identity, proofs[1].identity,
                                      tuple(e.identity for e in proofs), proofs).accepted is False
    rows.append(fact(3, "SalesRevenueNet"))
    assert summary(rows, proofs).metrics["revenue"].status == "unavailable"
    assert summary(rows, proofs).metrics["net_margin"].status == "unavailable"


@pytest.mark.parametrize("path", ["selection", "denominator"])
def test_permission_without_independent_evidence_is_disabled(monkeypatch, path):
    rows, proofs, _ = (selection_fixture if path == "selection" else denominator_fixture)(monkeypatch)
    metric = "revenue" if path == "selection" else "net_margin"
    assert summary(rows).metrics[metric].status == "unavailable"


@pytest.mark.parametrize("field,value", [
    ("document_identity", ""), ("document_text", ""), ("statement_location", ""),
    ("statement_end", 0), ("context_id", ""), ("dimensions", None),
    ("dimensions", (("ProductAxis", "HardwareMember"),)), ("economic_scope", "unknown"),
])
def test_missing_context_fails_even_if_its_hash_is_approved(monkeypatch, field, value):
    rows, proofs, approval = selection_fixture(monkeypatch)
    missing = replace(proofs[0], **{field: value})
    altered = replace(approval, selected=binding(missing), candidates=(binding(missing), binding(proofs[1])))
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (altered,))
    assert not selection_decision(rows, (missing, proofs[1])).accepted


@pytest.mark.parametrize("field", ["document_identity", "document_text", "statement_location", "context_id", "statement_start"])
def test_absent_evidence_fields_fail_closed_without_raising(monkeypatch, field):
    rows, proofs, _ = selection_fixture(monkeypatch)
    assert not selection_decision(rows, (replace(proofs[0], **{field: None}), proofs[1])).accepted


@pytest.mark.parametrize("field,value", [
    ("cik", "0000000002"), ("source_namespace", "Other API"), ("taxonomy_namespace", "issuer"),
    ("concept", "Revenues"), ("start", date(2025, 1, 2)), ("end", date(2025, 3, 30)),
    ("kind", "half_year"), ("unit", "EUR"), ("value", Decimal("101")),
    ("accession", "0000000001-25-000002"), ("form", "10-Q/A"), ("filed", date(2025, 5, 2)),
])
def test_denominator_rejects_wrong_source_identity(monkeypatch, field, value):
    rows, proofs, _ = denominator_fixture(monkeypatch)
    wrong = replace(proofs[0].identity, **{field: value})
    decision = auth.authorize_denominator("net_margin", wrong, proofs[1].identity,
                                         tuple(e.identity for e in proofs), proofs)
    assert not decision.accepted


def test_wrong_permission_is_rejected(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (replace(approval, ref=replace(approval.ref, permission="denominator:net_margin")),))
    assert selection_decision(rows, proofs).reason == "invalid_approval"


def test_genuine_annotation_duplicates_are_safe(monkeypatch):
    rows, proofs, _ = selection_fixture(monkeypatch)
    rows += [fact(88, fiscal_year=2026, fiscal_period="Q3", frame="CY2025Q1")]
    result = summary(rows, proofs).metrics["revenue"]
    assert result.value == 100
    assert selection_decision(rows, proofs + (proofs[0],)).accepted


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("path", ["selection", "denominator"])
def test_same_source_conflicts_fail_independent_of_row_order(monkeypatch, reverse, path):
    rows, proofs, _ = (selection_fixture if path == "selection" else denominator_fixture)(monkeypatch)
    rows.append(fact(0 if reverse else 99, value="101"))
    if reverse:
        rows.reverse()
    snap = summary(rows, proofs)
    metric = "revenue" if path == "selection" else "net_margin"
    assert snap.metrics[metric].status == "unavailable"
    assert {p.fact_id for p in snap.metrics[metric].alternatives} == {r.id for r in rows}
    if path == "denominator":
        assert "same_source_conflicting_values" in snap.metrics[metric].reason


@pytest.mark.parametrize("form,value", [("10-Q", "100"), ("10-Q/A", "100"), ("10-Q/A", "101")])
@pytest.mark.parametrize("path", ["selection", "denominator"])
def test_new_vintages_and_same_value_amendments_do_not_inherit_approval(monkeypatch, form, value, path):
    rows, proofs, _ = (selection_fixture if path == "selection" else denominator_fixture)(monkeypatch)
    rows.append(fact(3, value=value, accession_number="0000000001-25-000002", form=form, filed=date(2025, 5, 2)))
    decision = decision_for(path, rows, proofs)
    assert not decision.accepted
    assert decision.reason == ("candidate_manifest_changed" if value == "100" else "different_vintage_requires_restatement_review")


def test_complete_renewed_manifest_still_cannot_select_an_older_observation(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    later = fact(3, accession_number="0000000001-25-000002", filed=date(2025, 5, 2))
    rows.append(later)
    proofs += (evidence(later),)
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (replace(approval, candidates=tuple(binding(e) for e in proofs)),))
    assert selection_decision(rows, proofs).reason == "older_observation_not_permitted"


@pytest.mark.parametrize("path", ["selection", "denominator"])
@pytest.mark.parametrize("action", ["revoked", "superseded"])
def test_withdrawn_approvals_fail_closed(monkeypatch, path, action):
    rows, proofs, approval = (selection_fixture if path == "selection" else denominator_fixture)(monkeypatch)
    replacement = replace(approval.ref, version=2) if action == "superseded" else None
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(approval.ref, action, "Renewed review required", replacement),))
    assert summary(rows, proofs).metrics["revenue" if path == "selection" else "net_margin"].status == "unavailable"


@pytest.mark.parametrize("field,value", [("document_text", "Changed document"), ("context_id", "another-context"),
                                       ("statement_location", "different table"), ("economic_scope", "component_revenue")])
def test_changed_evidence_invalidates_permission(monkeypatch, field, value):
    rows, proofs, _ = selection_fixture(monkeypatch)
    altered = replace(proofs[0], **{field: value})
    assert not selection_decision(rows, (altered, proofs[1])).accepted


def test_overlapping_contradictory_selections_are_rejected(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    contrary = replace(approval, ref=replace(approval.ref, approval_id="contrary"), selected=binding(proofs[1]))
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (approval, contrary))
    assert selection_decision(rows, proofs).reason == "overlapping_approvals"


def test_version_lifecycle_does_not_fall_back_to_an_older_approval(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    newer = replace(approval, ref=replace(approval.ref, version=2))
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (approval, newer))
    assert selection_decision(rows, proofs).reason == "explicit_supersession_required"
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(approval.ref, "superseded", "Version two reviewed", newer.ref),))
    assert selection_decision(rows, proofs).ref.version == 2
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(newer.ref, "revoked", "Withdraw version two"),))
    assert not selection_decision(rows, proofs).accepted


def test_approval_records_are_immutable(monkeypatch):
    _, _, approval = selection_fixture(monkeypatch)
    with pytest.raises(FrozenInstanceError):
        approval.reviewed_scope = "Changed"
    with pytest.raises(TypeError):
        replace(approval, candidates=list(approval.candidates))


def test_denominator_cannot_authorize_cross_accession_pair_even_with_new_manifest(monkeypatch):
    rows, proofs, approval = denominator_fixture(monkeypatch)
    rows[1].accession_number = "0000000001-25-000002"
    proofs = (proofs[0], evidence(rows[1], "consolidated_net_income"))
    altered = replace(approval, numerator=binding(proofs[1]), candidates=tuple(binding(e) for e in proofs))
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (altered,))
    assert summary(rows, proofs).metrics["net_margin"].status == "unavailable"


@pytest.mark.parametrize("path", ["selection", "denominator"])
@pytest.mark.parametrize("change", ["new_scope", "withdrawn_successor", "changed_same_version"])
def test_lifecycle_checks_global_lineage_not_only_matching_period(monkeypatch, path, change):
    rows, proofs, approval = (selection_fixture if path == "selection" else denominator_fixture)(monkeypatch)
    registry = "REVENUE_SELECTION_AUTHORIZATIONS" if path == "selection" else "DENOMINATOR_AUTHORIZATIONS"
    field = "selected" if path == "selection" else "revenue"
    changed = replace(getattr(approval, field), identity=replace(proofs[0].identity, start=date(2025, 1, 2)))
    newer = replace(approval, ref=replace(approval.ref, version=2), **{field: changed})
    if change == "withdrawn_successor":
        monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(newer.ref, "revoked", "Successor withdrawn"),))
    else:
        if change == "changed_same_version":
            newer = replace(newer, ref=approval.ref)
        monkeypatch.setattr(auth, registry, (approval, newer))
    result = decision_for(path, rows, proofs)
    assert not result.accepted
    assert result.reason == ("conflicting_approval_version" if change == "changed_same_version" else "explicit_supersession_required")


def test_conflicting_reviewed_totals_are_rejected_despite_explicit_manifest(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    rows[1].value = Decimal("101")
    proofs = (proofs[0], evidence(rows[1]))
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (replace(approval, candidates=tuple(binding(e) for e in proofs)),))
    assert selection_decision(rows, proofs).reason == "conflicting_reviewed_economic_totals"


def test_nonselected_evidence_cannot_assign_a_wrong_economic_scope(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    proofs = (proofs[0], replace(proofs[1], economic_scope="consolidated_net_income"))
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (replace(approval, candidates=tuple(binding(e) for e in proofs)),))
    assert selection_decision(rows, proofs).reason == "economic_scope_mismatch"


def test_denominator_overlap_and_evidence_change_fail_closed(monkeypatch):
    rows, proofs, approval = denominator_fixture(monkeypatch)
    contrary = replace(approval, ref=replace(approval.ref, approval_id="contrary"), reviewed_scope="Conflicting review")
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (approval, contrary))
    assert decision_for("denominator", rows, proofs).reason == "overlapping_approvals"
    monkeypatch.setattr(auth, "DENOMINATOR_AUTHORIZATIONS", (approval,))
    assert not decision_for("denominator", rows, (replace(proofs[0], dimensions=None), proofs[1])).accepted
    assert not decision_for("denominator", rows, (replace(proofs[1], context_id="changed"), proofs[0])).accepted


def test_renewed_same_value_selection_requires_latest_evidence_and_explicit_supersession(monkeypatch):
    rows, proofs, approval = selection_fixture(monkeypatch)
    later = fact(3, form="10-Q/A", accession_number="0000000001-25-000002", filed=date(2025, 5, 2))
    rows.append(later)
    proofs += (evidence(later),)
    newer = replace(approval, ref=replace(approval.ref, version=2), selected=binding(proofs[-1]),
                    candidates=tuple(binding(e) for e in proofs))
    monkeypatch.setattr(auth, "REVENUE_SELECTION_AUTHORIZATIONS", (approval, newer))
    monkeypatch.setattr(auth, "AUTHORIZATION_WITHDRAWALS", (auth.AuthorizationWithdrawal(approval.ref, "superseded", "New amendment independently reviewed", newer.ref),))
    result = selection_decision(rows, proofs)
    assert result.accepted and result.selected == auth.SourceIdentity.from_fact(later)
    assert summary(rows, proofs).metrics["revenue"].provenance[0].fact_id == later.id


@pytest.mark.parametrize("path", ["selection", "denominator"])
def test_changed_fiscal_boundary_invalidates_manifest_and_retains_raw_alternative(monkeypatch, path):
    rows, proofs, _ = (selection_fixture if path == "selection" else denominator_fixture)(monkeypatch)
    rows.append(fact(3, period_start=date(2025, 1, 2), filed=date(2025, 5, 2), accession_number="0000000001-25-000002"))
    view = FinancialMetrics(COMPANY, rows, authorization_evidence=proofs)
    kind = "revenue" if path == "selection" else "net_margin"
    point = next(p for p in view.history(kind).history if p.period.start == date(2025, 1, 1))
    assert point.status == "unavailable" and "candidate_manifest_changed" in point.reason
    assert {p.fact_id for p in point.alternatives} == {r.id for r in rows}


def test_empty_registries_preserve_aapl_gross_margin_net_margin_and_historical_gaps():
    current = dict(company_cik="0000320193", period_start=date(2026, 3, 29), period_end=date(2026, 6, 27),
                   filed=date(2026, 7, 31), accession_number="0000320193-26-000020")
    rows = [fact(1, value="109417000000", **current), fact(2, "GrossProfit", "54770000000", **current),
            fact(3, "NetIncomeLoss", "29789000000", **current)]
    company = SimpleNamespace(cik=current["company_cik"], ticker="AAPL", name="Apple synthetic source identities")
    snap = FinancialMetrics(company, rows).summary()
    assert snap.metrics["gross_margin"].value == Decimal("0.5005620698794520047159033788")
    assert snap.metrics["net_margin"].status == "unavailable"
    rows.append(fact(4, value="109417000001", **current))
    assert FinancialMetrics(company, rows).summary().metrics["gross_margin"].status == "unavailable"
    historical = [
        fact(10, "SalesRevenueNet", "149430000000", company_cik=company.cik, period_start=date(2017, 10, 1), period_end=date(2018, 3, 31), filed=date(2018, 5, 2), accession_number="0000320193-18-000070"),
        fact(11, CUSTOMER, "149430000000", company_cik=company.cik, period_start=date(2017, 10, 1), period_end=date(2018, 3, 31), filed=date(2019, 5, 1), accession_number="0000320193-19-000066"),
        fact(12, CUSTOMER, "142325000000", company_cik=company.cik, period_start=date(2018, 9, 30), period_end=date(2019, 3, 30), filed=date(2020, 5, 1), accession_number="0000320193-20-000052"),
    ]
    view = FinancialMetrics(company, historical)
    assert view.history("revenue", "half_year").history[0].status == "unavailable"
    assert view.history("revenue_growth_yoy", "half_year").history[-1].status == "unavailable"


@pytest.mark.parametrize("concept", [CUSTOMER, "GrossProfit"])
@pytest.mark.parametrize("conflict", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_existing_gross_margin_raw_guard_with_duplicate_or_conflict_in_either_order(concept, conflict, reverse):
    context = dict(company_cik="0000320193", period_start=date(2026, 3, 29), period_end=date(2026, 6, 27),
                   filed=date(2026, 7, 31), accession_number="0000320193-26-000020")
    rows = [fact(1, value="109417000000", **context), fact(2, "GrossProfit", "54770000000", **context)]
    value = next(row.value for row in rows if row.metric == concept) + int(conflict)
    rows.append(fact(0 if reverse else 99, concept, str(value), fiscal_year=2030, frame="annotation-only", **context))
    if reverse:
        rows.reverse()
    company = SimpleNamespace(cik=context["company_cik"], ticker="AAPL", name="Synthetic guard fixture")
    result = FinancialMetrics(company, rows).summary().metrics["gross_margin"]
    assert result.status == ("unavailable" if conflict else "available")
    if not conflict:
        assert result.value == Decimal("0.5005620698794520047159033788")
