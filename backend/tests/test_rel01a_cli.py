"""Early CLI admission and explicit selection, using no live services or DB."""
import builtins
from contextlib import nullcontext
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app import config
from app.refresh_contracts import RefreshRequest
from app.release_policy import ReleaseModeBlocked


@pytest.mark.parametrize("module,args", [
    ("refresh_data", ["--all"]),
    ("refresh_data", ["--all", "--allow-network"]),
    ("refresh_data", ["--all", "--dry-run", "--allow-network"]),
    ("refresh_data", ["--all", "--bootstrap"]),
    ("refresh_data", ["--ticker", "AAPL", "--bootstrap"]),
    ("refresh_data", ["--show-run", "fixture", "--ticker", ""]),
    ("refresh_data", ["--show-run", "fixture", "--all"]),
    ("refresh_data", ["--show-run", "fixture", "--bootstrap"]),
    ("index_catalog", []),
    ("index_catalog", ["--dry-run"]),
    ("index_catalog", ["--ticker", " "]),
    ("sync_financial_facts", []),
    ("sync_financial_facts", ["--dry-run"]),
    ("sync_financial_facts", ["--ticker", ""]),
] + [
    pytest.param("refresh_data", selection + flags,
                 id=f"refresh-invalid-{selection_name}-{mode}")
    for selection_name, selection in [
        ("missing", []),
        ("missing-value", ["--ticker"]),
        ("empty", ["--ticker", ""]),
        ("spaces", ["--ticker", "   "]),
        ("whitespace", ["--ticker", "\t\r\n"]),
        ("mixed-last", ["--ticker", "AAPL", "--ticker", ""]),
        ("mixed-first", ["--ticker", " ", "--ticker", "AAPL"]),
        ("mixed-many", ["--ticker", "AAPL", "--ticker", "COST", "--ticker", "\t"]),
    ]
    for mode, flags in [
        ("normal", []), ("network", ["--allow-network"]),
        ("dry", ["--dry-run"]), ("dry-network", ["--dry-run", "--allow-network"]),
    ]
])
def test_prohibited_cli_rejects_before_operational_imports(monkeypatch, module, args):
    cli = importlib.import_module(f"scripts.{module}")
    real_import = builtins.__import__
    forbidden = ("sqlalchemy", "app.database", "app.models", "app.sec_client", "app.refresh_service",
                 "app.catalog_indexing_service", "app.financial_sync_service", "scripts.setup_demo",
                 "scripts.sync_financial_facts")
    attempted = []

    def guarded_import(name, *a, **kw):
        if name in forbidden:
            attempted.append(name)
            raise AssertionError(f"Operational import before denial: {name}")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(SystemExit) as failure:
        cli.main(args)
    assert failure.value.code == 2
    assert attempted == []  # Includes DB/schema, catalog/coordinator and report modules.


@pytest.mark.parametrize("module,args", [
    ("refresh_data", ["--all", "--allow-network"]),
    ("refresh_data", ["--ticker", "AAPL", "--allow-network"]),
    ("index_catalog", ["--ticker", "AAPL"]),
    ("sync_financial_facts", ["--ticker", "AAPL"]),
])
def test_release_profile_guard_still_precedes_cli_admission(monkeypatch, module, args):
    cli = importlib.import_module(f"scripts.{module}")
    monkeypatch.setattr(config, "_SERVER_PROFILE", config.ServerProfile("sec_readonly"))
    with pytest.raises(ReleaseModeBlocked):
        cli.main(args)


def test_request_limit_and_publication_scope_unchanged():
    assert len(RefreshRequest(tickers=[f"T{i}" for i in range(35)]).tickers) == 35
    with pytest.raises(ValidationError):
        RefreshRequest(tickers=[f"T{i}" for i in range(36)])
    with pytest.raises(ValidationError):
        RefreshRequest(tickers=["AMD"], publication_scope="aapl-10k-2025", max_filings=1)


@pytest.mark.parametrize("module", ["index_catalog", "sync_financial_facts"])
def test_explicit_selection_reaches_same_service_without_fallback(monkeypatch, tmp_path, module):
    # Fake sessions/services only; report writes go to a disposable pytest directory.
    from app import database, catalog_indexing_service, financial_sync_service
    from scripts import setup_demo
    cli = importlib.import_module(f"scripts.{module}")
    session = SimpleNamespace()
    factory = Mock(side_effect=lambda: nullcontext(session))
    monkeypatch.setattr(database, "SessionLocal", factory)
    schema = Mock()
    monkeypatch.setattr(setup_demo, "check_schema", schema)
    if module == "index_catalog":
        service = Mock(return_value={"catalog_total": 36, "skipped": 2, "newly_indexed": 0,
                                     "resumed": 0, "failed": 0, "final_ready": 35})
        monkeypatch.setattr(catalog_indexing_service, "index_catalog", service)
    else:
        service = Mock(return_value={"companies_requested": ["AAPL", "COST"], "updated": 0,
                                     "already_current": 2, "failed": 0, "no_usable_source": 0,
                                     "facts_inserted": 0, "catalog_error": None})
        monkeypatch.setattr(financial_sync_service, "sync_catalog", service)
        monkeypatch.setattr(cli, "report_path", lambda p: tmp_path / "report.json")
    assert cli.main(["--ticker", "AAPL", "--ticker", "COST", "--dry-run",
                     "--report", str(tmp_path / "report.json")]) == 0
    assert service.call_args.args[1] == ["AAPL", "COST"]
    assert service.call_args.kwargs["dry_run"] is True
    schema.assert_called_once_with(session)


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("tickers,scope", [(["AAPL"], "aapl-10k-2025"), (["AAPL", "COST"], None)])
def test_explicit_refresh_keeps_request_options_without_catalog_selection(monkeypatch, tmp_path, dry_run, tickers, scope):
    from app import database, refresh_service, sec_client
    from scripts import refresh_data, setup_demo, sync_financial_facts
    # Any catalog SELECT would fail: the fake session has no scalars/execute.
    factory = Mock(side_effect=lambda: nullcontext(SimpleNamespace()))
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(setup_demo, "check_schema", Mock())
    monkeypatch.setattr(sec_client, "get_sec_headers", Mock(return_value={}))
    monkeypatch.setattr(sync_financial_facts, "report_path", lambda p: tmp_path / "report.json")
    write = Mock()
    monkeypatch.setattr(sync_financial_facts, "write_report", write)
    service = Mock(return_value={"run_id": "fixture", "error": None, "companies": []})
    monkeypatch.setattr(refresh_service, "refresh", service)
    selection = [arg for ticker in tickers for arg in ("--ticker", ticker)]
    options = (["--dry-run"] if dry_run else []) + (["--publication-scope", scope] if scope else [])
    assert refresh_data.main([*selection, *options, "--allow-network",
                              "--max-filings", "1", "--max-seconds", "300",
                              "--max-run-seconds", "600", "--report", str(tmp_path / "report.json")]) == 0
    request = service.call_args.args[1]
    assert request.tickers == tickers and request.dry_run is dry_run
    assert request.publication_scope == scope
    assert (request.max_filings, request.max_seconds, request.max_run_seconds) == (1, 300, 600)
    write.assert_not_called()  # Progress callback belongs to the fake service.


@pytest.mark.parametrize("found", [False, True])
@pytest.mark.parametrize("flags", [[], ["--dry-run"], ["--allow-network"], ["--dry-run", "--allow-network"]])
def test_show_run_preserves_ledger_precedence_without_tickers(monkeypatch, capsys, found, flags):
    from app import database, refresh_service, sec_client
    from scripts import refresh_data, setup_demo, sync_financial_facts
    attempt = SimpleNamespace(id=1, company_cik="0000320193", stream="facts", status="no_change",
                              published_version=0, details={})
    session = SimpleNamespace(scalars=Mock(return_value=[attempt] if found else []))
    factory = Mock(side_effect=lambda: nullcontext(session))
    schema = Mock()
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(setup_demo, "check_schema", schema)
    forbidden = []
    for owner, name in [(refresh_data, "RefreshRequest"), (refresh_service, "refresh"),
                        (refresh_service, "coordinator"), (refresh_service, "bootstrap_publications"),
                        (sec_client, "get_sec_headers"), (sync_financial_facts, "report_path"),
                        (sync_financial_facts, "write_report")]:
        sentinel = Mock(side_effect=AssertionError("Ledger inspection must not perform refresh/report work"))
        monkeypatch.setattr(owner, name, sentinel)
        forbidden.append(sentinel)
    assert refresh_data.main(["--show-run", "fixture", *flags, "--report", "reports/unused.json"]) == (0 if found else 1)
    factory.assert_called_once_with()
    schema.assert_called_once_with(session)
    session.scalars.assert_called_once()
    statement = str(session.scalars.call_args.args[0])
    assert "refresh_attempts" in statement and "companies" not in statement
    assert '"run_id": "fixture"' in capsys.readouterr().out
    for sentinel in forbidden:
        sentinel.assert_not_called()
