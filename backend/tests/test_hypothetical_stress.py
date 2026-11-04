"""Bounded user-asserted linear stress; run through the maintained offline guard."""
from copy import deepcopy
from decimal import localcontext, Inexact, Rounded
from fractions import Fraction
import json
import os
from pathlib import Path

import pytest

from app import hypothetical_stress as stress
from app.portfolio_risk import PortfolioRiskError
from app.release_policy import READONLY_ROUTES, FINANCIAL_ONLY_ROUTES, READER_ROUTES
from test_hypothetical_risk import client, fixture as risk_fixture, _dispatch_setup, _eventually, _cancel


def fixture():
    return {"reporting_currency":"USD", "exposure_date":"2026-11-04",
        "exposures":[{"asset_id":asset,"amount":amount,"currency":"USD","exposure_type":"linear_price_notional"}
                     for asset,amount in [("long","100"),("short","-50"),("zero","0")]],
        "scenarios":[{"scenario_id":"decline","shocks":{"long":"-10","short":"5","zero":"0"}},
                     {"scenario_id":"unchanged","shocks":{"long":"0","short":"0","zero":"0"}}],
        "common_shocks":["10","-100","0"]}


def fraction(value):
    return Fraction(int(value["numerator"]),int(value["denominator"]))


def assert_oracle(receipt):
    inputs,r=receipt["inputs"],receipt["result"]
    exposures={e["asset_id"]:Fraction(e["amount"]) for e in inputs["exposures"]}
    assert fraction(r["net_exposure"])==sum(exposures.values())
    assert fraction(r["gross_exposure"])==sum(abs(v) for v in exposures.values())
    assert fraction(r["common_shock_pnl_per_percentage_point"])==sum(exposures.values())/100
    pairs=[(row,inputs["scenarios"][i]["shocks"]) for i,row in enumerate(r["scenarios"])]
    pairs += [(row,dict.fromkeys(exposures, str(fraction(row["shock_percent"])))) for row in r["common_shock_sensitivity"]]
    for row,shocks in pairs:
        expected={asset:amount*Fraction(shocks[asset])/100 for asset,amount in exposures.items()}
        assert fraction(row["total_pnl"])==sum(expected.values())
        assert fraction(row["total_loss"])==-sum(expected.values())
        assert [c["asset_id"] for c in row["contributions"]]==sorted(exposures)
        for c in row["contributions"]:
            assert fraction(c["pnl"])==expected[c["asset_id"]]
            assert fraction(c["loss"])==-expected[c["asset_id"]]
            assert fraction(c["exposure"])==exposures[c["asset_id"]]
            assert fraction(c["shock_percent"])==Fraction(shocks[c["asset_id"]])


def test_signed_exact_contributions_and_common_sensitivity():
    value=fixture();original=deepcopy(value);receipt=stress.calculate_request(value);r=receipt["result"]
    assert value==original and receipt["inputs"]==original
    assert r["method_id"]=="hypothetical-linear-price-stress-v1"
    assert r["data_authority"]=="unverified_user_assumptions"
    assert fraction(r["scenarios"][0]["total_pnl"])==Fraction(-25,2)
    assert fraction(r["scenarios"][0]["total_loss"])==Fraction(25,2)
    assert fraction(r["scenarios"][1]["total_pnl"])==0
    assert [fraction(s["shock_percent"]) for s in r["common_shock_sensitivity"]]==[-100,0,10]
    assert [fraction(s["total_pnl"]) for s in r["common_shock_sensitivity"]]==[-50,0,5]
    assert_oracle(receipt)


def test_zero_net_common_offset_is_not_zero_named_stress():
    value=fixture();value["exposures"][1]["amount"]="-100"
    receipt=stress.calculate_request(value)
    assert all(fraction(s["total_pnl"])==0 for s in receipt["result"]["common_shock_sensitivity"])
    assert fraction(receipt["result"]["scenarios"][0]["total_pnl"])==-15
    assert_oracle(receipt)


def test_exact_decimals_context_scaling_and_signed_zero():
    value=fixture();value["exposures"][0]["amount"]="0.123456789012"
    value["exposures"][1]["amount"]="-0.000000000001"
    value["exposures"][2]["amount"]="-0"
    value["scenarios"][0]["shocks"]={"long":"0.000000000001","short":"0.000000000001","zero":"0"}
    with localcontext() as ctx:
        ctx.prec=2;ctx.traps[Inexact]=ctx.traps[Rounded]=True
        receipt=stress.calculate_request(value)
    assert_oracle(receipt)
    assert fraction(receipt["result"]["scenarios"][0]["total_pnl"])!=0
    doubled=deepcopy(value)
    # Exact textual doubling through Fraction, avoiding Decimal context arithmetic.
    doubled["exposures"][0]["amount"]="0.246913578024"
    doubled["exposures"][1]["amount"]="-0.000000000002"
    other=stress.calculate_request(doubled)
    assert fraction(other["result"]["scenarios"][0]["total_pnl"])==2*fraction(receipt["result"]["scenarios"][0]["total_pnl"])


@pytest.mark.parametrize("shock", ["-100","1000","0","-0","0.000000000001","999.999999999999"])
def test_shock_bounds_and_zero(shock):
    value=fixture();value["common_shocks"]=[shock]
    value["scenarios"][0]["shocks"]=dict.fromkeys(["long","short","zero"],shock)
    assert_oracle(stress.calculate_request(value))


@pytest.mark.parametrize("bad", ["-100.000000000001","1000.000000000001",True,0,0.1,None,"NaN","Infinity","1e2"," 1","+1","01","0.1234567890123","1"*25])
@pytest.mark.parametrize("location", ["scenario","common"])
def test_invalid_shock_rejected_even_for_zero_position(bad,location):
    value=fixture()
    if location=="scenario":value["scenarios"][-1]["shocks"]["zero"]=bad
    else:value["common_shocks"][-1]=bad
    with pytest.raises(PortfolioRiskError):stress.calculate_request(value)


@pytest.mark.parametrize("case", ["missing","unknown","duplicate_asset","duplicate_scenario","duplicate_common","currency","type","top_currency","date","field","empty_assets","empty_scenarios","empty_common","assets_bound","scenarios_bound","common_bound"])
def test_contract_rejections(case):
    value=fixture()
    if case=="missing":del value["scenarios"][0]["shocks"]["zero"]
    if case=="unknown":value["scenarios"][0]["shocks"]["other"]="0"
    if case=="duplicate_asset":value["exposures"].append(value["exposures"][0])
    if case=="duplicate_scenario":value["scenarios"]*=2
    if case=="duplicate_common":value["common_shocks"]=["0","-0.0"]
    if case=="currency":value["exposures"][1]["currency"]="EUR"
    if case=="type":value["exposures"][0]["exposure_type"]="option_delta"
    if case=="top_currency":value["reporting_currency"]="$"
    if case=="date":value["exposure_date"]="2026-02-30"
    if case=="field":value["probability"]="0.5"
    if case=="empty_assets":value["exposures"]=[]
    if case=="empty_scenarios":value["scenarios"]=[]
    if case=="empty_common":value["common_shocks"]=[]
    if case=="assets_bound":value["exposures"]*=3
    if case=="scenarios_bound":value["scenarios"]*=7
    if case=="common_bound":value["common_shocks"]=[str(i) for i in range(22)]
    with pytest.raises(PortfolioRiskError):stress.calculate_request(value)


def test_all_cells_validated_before_calculation(monkeypatch):
    value=fixture();value["common_shocks"][-1]="-101"
    monkeypatch.setattr(stress,"outcome",lambda *a:pytest.fail("arithmetic before complete validation"))
    with pytest.raises(PortfolioRiskError):stress.calculate_request(value)


def test_inclusive_resource_caps_and_response_limit(monkeypatch):
    value=fixture();value["exposures"]=[{"asset_id":f"a{i}","amount":"999999999999.123456789012","currency":"USD","exposure_type":"linear_price_notional"} for i in range(8)]
    value["scenarios"]=[{"scenario_id":f"s{i}","shocks":{e["asset_id"]:"1000" for e in value["exposures"]}} for i in range(12)]
    value["common_shocks"]=[str(i) for i in range(-100,-79)]
    assert len(stress.response_bytes(value))<1048576
    assert_oracle(stress.calculate_request(value))
    monkeypatch.setattr(stress,"MAX_RESPONSE_BYTES",1)
    with pytest.raises(PortfolioRiskError,match="response_resource_limit"):stress.response_bytes(value)


@pytest.mark.parametrize("profile,flag,status", [("development","0",404),("development","",404),("sec_readonly","1",403),("sec_reader","1",403)])
def test_stress_default_off_and_restricted(monkeypatch,profile,flag,status):
    with client(monkeypatch,profile,flag,True) as c:
        assert c.post("/hypothetical-stress",json=fixture()).status_code==status
    assert all(("POST","/hypothetical-stress") not in routes for routes in [READONLY_ROUTES,FINANCIAL_ONLY_ROUTES,READER_ROUTES])


def test_http_contract_and_transport(monkeypatch):
    with client(monkeypatch) as c:
        response=c.post("/hypothetical-stress",json=fixture())
        assert response.status_code==200 and response.headers["cache-control"]=="no-store"
        assert response.json()==stress.calculate_request(fixture())
        assert c.post("/hypothetical-stress",json={}).status_code==422
        for bad in ["-100.000000000001","1000.000000000001"]:
            value=fixture();value["scenarios"][0]["shocks"]["zero"]=bad
            rejected=c.post("/hypothetical-stress",json=value)
            assert rejected.status_code==422 and rejected.json()=={"detail":"unsupported_shock_percent"}
        assert c.post("/hypothetical-stress",content="{}",headers={"Content-Type":"text/plain"}).status_code==415
        assert c.post("/hypothetical-stress",content=b' '*131073,headers={"Content-Type":"application/json"}).status_code==413
        assert c.post("/hypothetical-stress",content=b'{"x":0,"x":1}',headers={"Content-Type":"application/json"}).status_code==422
        assert c.post("/hypothetical-stress",json=fixture(),headers={"Content-Encoding":"gzip"}).status_code==415
        monkeypatch.delenv("FINLENS_HYPOTHETICAL_RISK",raising=False)
        assert c.post("/hypothetical-stress",content=b'{',headers={"Content-Type":"application/json"}).status_code==404


def test_actual_queued_stress_cancel_frees_shared_slot(monkeypatch):
    import asyncio,httpx
    from anyio.to_thread import current_default_thread_limiter
    route,slot,app=_dispatch_setup(monkeypatch)
    async def scenario():
        limiter=current_default_thread_limiter();previous=limiter.total_tokens;limiter.total_tokens=1
        borrower=object();await limiter.acquire_on_behalf_of(borrower);borrowed=True
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url="http://fixture") as c:
                request=asyncio.create_task(c.post("/hypothetical-stress",json=fixture()))
                await _eventually(lambda:limiter.statistics().tasks_waiting==1)
                assert (await c.post("/hypothetical-risk",json=risk_fixture())).status_code==429
                await _cancel(request,3);assert slot.counts==(1,1)
                limiter.release_on_behalf_of(borrower);borrowed=False
                stress_response=await c.post("/hypothetical-stress",json=fixture())
                risk_response=await c.post("/hypothetical-risk",json=risk_fixture())
                assert stress_response.status_code==risk_response.status_code==200
                assert stress_response.json()["result"]["method_id"]==stress.METHOD_ID
                assert risk_response.json()["result"]["method_id"]=="historical-loss-es-v1"
                assert slot.counts==(3,3)
        finally:
            if borrowed:limiter.release_on_behalf_of(borrower)
            limiter.total_tokens=previous
    asyncio.run(scenario())


def test_actual_running_stress_cancel_retains_shared_slot(monkeypatch):
    import asyncio,httpx
    from threading import Event
    route,slot,app=_dispatch_setup(monkeypatch);entered,finish=Event(),Event();original=stress.response_bytes
    def blocked(value):
        entered.set();assert finish.wait(5);return original(value)
    monkeypatch.setattr(stress,"response_bytes",blocked)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url="http://fixture") as c:
            request=asyncio.create_task(c.post("/hypothetical-stress",json=fixture()))
            try:
                await _eventually(entered.is_set);await _cancel(request,3);assert slot.counts==(1,0)
                assert (await c.post("/hypothetical-risk",json=risk_fixture())).status_code==429
                assert (await c.post("/hypothetical-stress",json=fixture())).status_code==429
            finally:finish.set()
            await _eventually(slot.released.is_set);assert slot.counts==(1,1)
            assert (await c.post("/hypothetical-stress",json=fixture())).status_code==200
            assert (await c.post("/hypothetical-risk",json=risk_fixture())).status_code==200
            assert slot.counts==(3,3)
    asyncio.run(scenario())


def test_actual_historical_slot_blocks_stress(monkeypatch):
    from app import hypothetical_risk_route as route
    with client(monkeypatch) as c:
        assert route._slot.acquire(False)
        try:assert c.post("/hypothetical-stress",json=fixture()).status_code==429
        finally:route._slot.release()
        assert c.post("/hypothetical-stress",json=fixture()).status_code==200


def test_contract_export():
    target=os.environ.get("FINLENS_STRESS_CONTRACT_OUTPUT")
    if target:
        variants=[fixture()]
        for amount in ["-100","0","0.123456789012","999999999999.123456789012"]:
            value=fixture();value["exposures"][0]["amount"]=amount;variants.append(value)
        for shock_value in ["-100","1000","0.000000000001"]:
            value=fixture();value["scenarios"][0]["shocks"]=dict.fromkeys(["long","short","zero"],shock_value);variants.append(value)
        permuted=fixture();permuted["exposures"].reverse();variants.append(permuted)
        receipts=[stress.calculate_request(v) for v in variants]
        for receipt in receipts:assert_oracle(receipt)
        Path(target).write_text(json.dumps(receipts),encoding="utf-8")


def test_exposure_and_mapping_order_cannot_reassign_named_shocks():
    baseline=stress.calculate_request(fixture())
    value=fixture();value["exposures"].reverse()
    for scenario in value["scenarios"]:scenario["shocks"]=dict(reversed(list(scenario["shocks"].items())))
    receipt=stress.calculate_request(value)
    assert receipt["result"]==baseline["result"]
    assert receipt["inputs"]==value
    assert_oracle(receipt)
