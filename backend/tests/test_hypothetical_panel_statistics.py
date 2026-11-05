"""Separate receipt/route with frozen v1 byte parity; use the offline runner."""
import asyncio
from copy import deepcopy
from datetime import date, timedelta
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
from threading import Event, get_ident

import httpx
import pytest
from fastapi.testclient import TestClient

from app import hypothetical_panel_statistics as statistics, hypothetical_risk as risk_adapter
from app import hypothetical_risk_route as route
from app.portfolio_risk import PortfolioRiskError
from app.release_policy import READONLY_ROUTES, FINANCIAL_ONLY_ROUTES, READER_ROUTES
from test_hypothetical_risk import fixture, client, _dispatch_setup, _eventually, _cancel
from test_hypothetical_stress import fixture as stress_fixture

PATH = '/hypothetical-panel-statistics'
GOLDEN = Path(__file__).resolve().parent / 'fixtures/hypothetical-risk-v1-golden.json'
GOLDEN_SHA256 = 'fd8826d87fa31dafedbe75526552a9902c126a5e9f0c9aaae4167f0456195cba'


def frozen_v1_cases():
    # Generated once from this exact Git baseline, never from the tested adapter.
    raw = GOLDEN.read_bytes().replace(b'\r\n', b'\n')
    assert len(raw) <= 262144
    assert hashlib.sha256(raw).hexdigest() == GOLDEN_SHA256, 'frozen_v1_fixture_changed'
    reference = json.loads(raw)
    assert reference['schema'] == 'frozen-hypothetical-risk-v1-golden-v1'
    assert reference['baseline_commit'] == 'b05f59d706b4e840ebcbebf34c796628000fe0eb'
    assert reference['source_sha256'] == {
        'backend/app/portfolio_risk.py': '0295126fe62d0538eb8dc37c84ce79a73eba23e6c2aea2b53b13e126d9c60c0e',
        'backend/app/hypothetical_risk.py': 'efd58894e8bb808e7cb3c3b271d69e7f5fc84b661431315d6717136e88811993',
    }
    assert reference['case_count'] == len(reference['cases']) == 56
    assert reference['groups'] == {'varied': 45, 'replay_export': 11}
    return reference['cases']


def assert_frozen_v1_response(case):
    actual = risk_adapter.response_bytes(deepcopy(case['inputs']))
    assert len(actual) == case['response_bytes'], 'v1_response_length_changed'
    assert hashlib.sha256(actual).hexdigest() == case['response_sha256'], 'v1_response_digest_changed'


def panel_fixture():
    value=fixture('0.5')
    value['exposures']=[{'asset_id':'b','amount':'-50'},{'asset_id':'a','amount':'100'}]
    value['sessions']=[{'session_id':'first','start':'2026-01-01','end':'2026-01-02','factors':{'b':'1.2','a':'1.1'}},
                       {'session_id':'second','start':'2026-01-02','end':'2026-01-08','factors':{'b':'0.8','a':'0.9'}}]
    return value


def test_separate_receipt_complete_inputs_and_root_contract():
    value=panel_fixture();original=deepcopy(value);receipt=statistics.calculate_request(value);r=receipt['result']
    assert value==original and receipt['inputs']==original
    assert set(receipt)=={'schema_id','inputs','result'} and receipt['schema_id']=='hypothetical-panel-statistics-v1'
    assert r['method_id']=='supplied-factor-panel-statistics-v1'
    assert r['precision_id']=='exact-rational-symbolic-root-display18-half-even-v1'
    assert r['data_authority']=='unverified_synthetic_inputs'
    assert r['asset_ids']==['a','b'] and r['interval_days']==[1,6] and not r['equal_interval_lengths']
    a=r['assets'][0]
    assert a['cumulative_return']['exact']['display']=='-0.010000000000000000'
    assert a['maximum_drawdown']['exact']['display']=='0.100000000000000000'
    assert (a['peak_boundary'],a['trough_boundary'])==(1,2)
    assert a['sample_volatility']=={'radicand':{'numerator':'1','denominator':'50','display':'0.020000000000000000'},
                                   'display':'0.141421356237309505','reason':None}
    assert r['covariance'][0][1]['exact']['display']=='0.040000000000000000'
    assert r['covariance'][0][1]==r['covariance'][1][0]
    assert 'portfolio_value' not in r and 'portfolio_wealth' not in r
    assert json.loads(statistics.response_bytes(value))==receipt


def test_contract_example_export():
    target=os.environ.get('FINLENS_PANEL_STATISTICS_CONTRACT_OUTPUT')
    if target:
        Path(target).write_bytes(statistics.response_bytes(panel_fixture()))


def test_original_v1_risk_response_bytes_match_frozen_baseline_for_45_variants():
    cases = [case for case in frozen_v1_cases() if case['group'] == 'varied']
    assert len(cases) == 45
    for case in cases:
        assert_frozen_v1_response(case)


def test_original_eleven_receipt_export_variants_keep_full_v1_parity():
    cases = [case for case in frozen_v1_cases() if case['group'] == 'replay_export']
    assert len(cases) == 11
    for case in cases:
        assert_frozen_v1_response(case)


def test_frozen_v1_reference_detects_changed_candidate_calculation(monkeypatch):
    case = next(case for case in frozen_v1_cases() if case['name'] == 'replay-00')
    assert_frozen_v1_response(case)
    original = risk_adapter.calculate_historical_risk

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        return replace(result, var=replace(result.var, exact=result.var.exact + 1))

    monkeypatch.setattr(risk_adapter, 'calculate_historical_risk', changed)
    with pytest.raises(AssertionError, match='v1_response_digest_changed'):
        assert_frozen_v1_response(case)
    assert case == next(item for item in frozen_v1_cases() if item['name'] == 'replay-00')


def test_frozen_v1_fixture_accepts_crlf_and_rejects_drift(monkeypatch):
    original = frozen_v1_cases()
    class FixtureBytes:
        raw = GOLDEN.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        def read_bytes(self):
            return self.raw
    reference = FixtureBytes()
    monkeypatch.setitem(frozen_v1_cases.__globals__, 'GOLDEN', reference)
    assert frozen_v1_cases() == original
    reference.raw = reference.raw.replace(b'"USD"', b'"EUR"', 1)
    with pytest.raises(AssertionError, match='frozen_v1_fixture_changed'):
        frozen_v1_cases()


@pytest.mark.parametrize('count',[0,1])
def test_insufficiency_is_explicit_in_json(count):
    value=panel_fixture();value['sessions']=value['sessions'][:count];r=statistics.calculate_request(value)['result']
    assert r['sample_count']==count and r['sample_denominator'] is None and not r['covariance_complete']
    for asset in r['assets']:
        assert asset['sample_variance']=={'exact':None,'reason':'insufficient_observations'}
        assert asset['sample_volatility']=={'radicand':None,'display':None,'reason':'insufficient_observations'}
        if count==0:assert asset['cumulative_return']['reason']=='insufficient_observations'
        else:assert asset['cumulative_return']['exact'] is not None


@pytest.mark.parametrize('case',['missing','unknown','nonpositive','gap','duplicate','currency','float','confidence','horizon','field'])
def test_shared_input_rejection_is_not_relaxed(case):
    value=panel_fixture()
    if case=='missing':del value['sessions'][0]['factors']['a']
    if case=='unknown':value['sessions'][0]['factors']['c']='1'
    if case=='nonpositive':value['sessions'][0]['factors']['a']='0'
    if case=='gap':value['sessions'][1]['start']='2026-01-03'
    if case=='duplicate':value['exposures']*=2
    if case=='currency':value['reporting_currency']='usd'
    if case=='float':value['sessions'][0]['factors']['a']=1.1
    if case=='confidence':value['confidence']='1'
    if case=='horizon':value['horizon']=True
    if case=='field':value['growth_forecast']='1'
    with pytest.raises(PortfolioRiskError):statistics.calculate_request(value)


def test_maximum_adapter_panel_and_resource_unavailable_are_bounded(monkeypatch):
    value=fixture('0.5',20);value['exposures']=[{'asset_id':f'a{j}','amount':'0'} for j in range(8)]
    start=date(2026,1,1)
    value['sessions']=[{'session_id':f's{i}','start':(start+timedelta(days=i)).isoformat(),
        'end':(start+timedelta(days=i+1)).isoformat(),'factors':{f'a{j}':'999999999999.123456789012' for j in range(8)}} for i in range(120)]
    payload=statistics.response_bytes(value);assert len(payload)<statistics.MAX_RESPONSE_BYTES
    r=json.loads(payload)['result'];assert r['sample_count']==120 and len(r['covariance'])==8
    assert all(a['cumulative_return']['reason']=='arithmetic_resource_limit' for a in r['assets'])
    assert all(a['maximum_drawdown']['exact']['numerator']=='0' for a in r['assets'])
    monkeypatch.setattr(statistics,'MAX_RESPONSE_BYTES',1)
    with pytest.raises(PortfolioRiskError,match='response_resource_limit'):statistics.response_bytes(panel_fixture())


@pytest.mark.parametrize('profile,enabled,status',[('development','0',404),('development','',404),('sec_readonly','1',403),('sec_reader','1',403)])
def test_disabled_and_restricted_route_never_broadens_admission(monkeypatch,profile,enabled,status):
    with client(monkeypatch,profile,enabled,True) as c:
        assert c.post(PATH,json=panel_fixture()).status_code==status
    assert all(('POST',PATH) not in routes for routes in (READONLY_ROUTES,FINANCIAL_ONLY_ROUTES,READER_ROUTES))


def test_http_exact_response_transport_rejection_and_no_schema_publication(monkeypatch):
    with client(monkeypatch) as c:
        reply=c.post(PATH,json=panel_fixture())
        assert reply.status_code==200 and reply.headers['cache-control']=='no-store'
        assert reply.content==statistics.response_bytes(panel_fixture())
        assert c.post(PATH,content='{}',headers={'content-type':'text/plain'}).status_code==415
        assert c.post(PATH,content=b' '*131073,headers={'content-type':'application/json'}).status_code==413
        assert c.post(PATH,content=b'{"a":1,"a":2}',headers={'content-type':'application/json'}).status_code==422
        assert c.post(PATH,json=panel_fixture(),headers={'content-encoding':'gzip'}).status_code==415
        assert PATH not in c.get('/openapi.json').json()['paths']
        assert c.post(PATH,json={}).status_code==422
        assert c.post(PATH,json=panel_fixture()).status_code==200


def test_actual_main_registration_preserves_disabled_and_restricted_states(monkeypatch):
    from app import config
    from app.main import app
    monkeypatch.setattr(config,'_SERVER_PROFILE',config.ServerProfile('development'))
    monkeypatch.delenv('FINLENS_HYPOTHETICAL_RISK',raising=False)
    with TestClient(app) as c:
        assert c.post(PATH,json=panel_fixture()).status_code==404
        monkeypatch.setenv('FINLENS_HYPOTHETICAL_RISK','1')
        assert c.post(PATH,json=panel_fixture()).status_code==200
        monkeypatch.setattr(config,'_SERVER_PROFILE',config.ServerProfile('sec_readonly'))
        assert c.post(PATH,json=panel_fixture()).status_code==403


def test_one_slot_is_shared_by_risk_stress_and_statistics(monkeypatch):
    with client(monkeypatch) as c:
        assert route._slot.acquire(False)
        try:
            for path,value in [(PATH,panel_fixture()),('/hypothetical-risk',fixture()),('/hypothetical-stress',stress_fixture())]:
                assert c.post(path,json=value).status_code==429
        finally:route._slot.release()
        assert c.post(PATH,json=panel_fixture()).status_code==200


@pytest.mark.parametrize('times',[1,3])
def test_actual_statistics_dispatch_queued_cancel_releases_and_valid_retry(monkeypatch,times):
    from anyio.to_thread import current_default_thread_limiter
    _,slot,app=_dispatch_setup(monkeypatch);calls=[];original=statistics.response_bytes
    def record(value):calls.append(value);return original(value)
    monkeypatch.setattr(statistics,'response_bytes',record)
    async def scenario():
        limiter=current_default_thread_limiter();previous=limiter.total_tokens;limiter.total_tokens=1
        borrower=object();await limiter.acquire_on_behalf_of(borrower);borrowed=True
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as c:
                request=asyncio.create_task(c.post(PATH,json=panel_fixture()))
                await _eventually(lambda:limiter.statistics().tasks_waiting==1)
                assert slot.counts==(1,0) and not calls
                await _cancel(request,times);assert slot.counts==(1,1) and not calls
                limiter.release_on_behalf_of(borrower);borrowed=False
                reply=await c.post(PATH,json=panel_fixture());assert reply.status_code==200
                assert reply.json()==statistics.calculate_request(panel_fixture())
                assert slot.counts==(2,2) and len(calls)==1
        finally:
            if borrowed:limiter.release_on_behalf_of(borrower)
            limiter.total_tokens=previous
    asyncio.run(scenario())


@pytest.mark.parametrize('times',[1,3])
def test_actual_statistics_running_cancel_retains_until_worker_completion(monkeypatch,times):
    _,slot,app=_dispatch_setup(monkeypatch);entered,finish=Event(),Event();original=statistics.response_bytes;main=get_ident()
    def block(value):
        assert get_ident()!=main;entered.set();assert finish.wait(5);return original(value)
    monkeypatch.setattr(statistics,'response_bytes',block)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as c:
            request=asyncio.create_task(c.post(PATH,json=panel_fixture()))
            try:
                await _eventually(entered.is_set);await _cancel(request,times)
                assert slot.counts==(1,0)
                assert (await c.post('/hypothetical-risk',json=fixture())).status_code==429
            finally:finish.set()
            await _eventually(slot.released.is_set);assert slot.counts==(1,1)
            assert (await c.post(PATH,json=panel_fixture())).status_code==200;assert slot.counts==(2,2)
    asyncio.run(scenario())


@pytest.mark.parametrize('error_type',[PortfolioRiskError,RuntimeError])
def test_statistics_worker_failure_releases_and_subsequent_valid_retry(monkeypatch,error_type):
    _,slot,app=_dispatch_setup(monkeypatch);original=statistics.response_bytes;first=True
    def fail_once(value):
        nonlocal first
        if first:first=False;raise error_type('Synthetic statistics worker failure')
        return original(value)
    monkeypatch.setattr(statistics,'response_bytes',fail_once)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as c:
            if error_type is PortfolioRiskError:assert (await c.post(PATH,json=panel_fixture())).status_code==422
            else:
                with pytest.raises(RuntimeError,match='Synthetic statistics worker failure'):await c.post(PATH,json=panel_fixture())
            assert slot.counts==(1,1)
            assert (await c.post(PATH,json=panel_fixture())).status_code==200 and slot.counts==(2,2)
    asyncio.run(scenario())


def test_statistics_dispatch_start_failure_releases_and_retries(monkeypatch):
    from anyio._backends._asyncio import WorkerThread
    _,slot,app=_dispatch_setup(monkeypatch);original=WorkerThread.start;first=True
    def fail_once(worker):
        nonlocal first
        if first:first=False;raise RuntimeError('Synthetic statistics dispatch failure')
        return original(worker)
    monkeypatch.setattr(WorkerThread,'start',fail_once)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://fixture') as c:
            with pytest.raises(RuntimeError,match='Synthetic statistics dispatch failure'):await c.post(PATH,json=panel_fixture())
            assert slot.counts==(1,1)
            assert (await c.post(PATH,json=panel_fixture())).status_code==200 and slot.counts==(2,2)
    asyncio.run(scenario())
