"""Candidate route body/decorator and response validation, synthetic ASGI only."""
import ast
import asyncio
from contextlib import contextmanager
from pathlib import Path
import runpy
import sys
import unittest
# Preload framework before the shared fixture's strict import/effect guard.
import fastapi
import httpx
import sniffio
from fastapi import FastAPI, HTTPException

support = runpy.run_path(str(Path(__file__).with_name("test_multi_metric_fiscal.py")), run_name="synthetic_contract_support")
a = support["a"]
Loader, company, fact = support["Loader"], support["company"], support["fact"]
source = Path(__file__).resolve().parents[1] / "app/main.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
route = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "deterministic_research_answer")
assert len(route.decorator_list) == 1
assert ast.unparse(route.decorator_list[0]) == "app.post('/companies/{ticker}/research-answer', response_model=MultiResearchAnswer | ResearchAnswer)"
app = FastAPI()
loaders=[]
@contextmanager
def read_session(_):
    loader=Loader([company(), company("MSFT",2)], [fact(2024,"100",1)])
    loaders.append(loader)
    yield loader
namespace={"app":app,"ResearchAnswer":a.ResearchAnswer,"MultiResearchAnswer":a.MultiResearchAnswer,
           "ResearchAnswerRequest":a.ResearchAnswerRequest,"answer_research_question":a.answer_research_question,
           "UnknownCompany":a.UnknownCompany,"HTTPException":HTTPException,"read_session":read_session,
           "HttpSessionLocal":None,"validate_research_input":lambda question: None}
exec(compile(ast.fix_missing_locations(ast.Module(body=[route],type_ignores=[])),str(source),"exec"),namespace)

async def direct_worker(fn, *args, **kwargs):
    return fn(*args, **kwargs)
fastapi.routing.run_in_threadpool = direct_worker

def without_event_loop(coro):
    sniffio.current_async_library_cvar.set("asyncio")
    try:
        yielded = coro.send(None)
    except StopIteration as done:
        return done.value
    coro.close()
    raise AssertionError(f"unexpected async scheduling: {yielded!r}")

class RouteTests(unittest.TestCase):
    async def request(self,q):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://synthetic.invalid") as client:
            return await client.post("/companies/TEST/research-answer",json={"question":q})
    def test_mixed_observations_and_real_response_model(self):
        response=without_event_loop(self.request("revenue and net income for FY2024"))
        self.assertEqual(response.status_code,200)
        body=response.json();self.assertEqual(body["answer_kind"],"multi_metric");self.assertEqual(body["company_cik"],"0000000001")
        self.assertEqual([x["status"] for x in body["metrics"]],["available","unavailable"])
        self.assertTrue(body["metrics"][0]["observation"]["provenance"])
        self.assertTrue(body["metrics"][1]["explanation"])
        self.assertEqual(loaders[-1].fact_reads,1)
    def test_single_json_exactly_matches_service_and_rejected_loads_no_facts(self):
        response=without_event_loop(self.request("FY2024 revenue"))
        expected=a.answer_research_question(Loader([company()],[fact(2024,"100",1)]),"TEST","FY2024 revenue")
        self.assertEqual(response.status_code,200);self.assertEqual(response.json(),expected.model_dump(mode="json"))
        self.assertNotIn("metrics",response.json())
        response=without_event_loop(self.request("not revenue and net income for FY2024"))
        self.assertEqual(response.status_code,200);self.assertFalse(response.json()["matched"])
        self.assertEqual(loaders[-1].fact_reads,0)
    def test_unknown_company(self):
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://synthetic.invalid") as client:
                return await client.post("/companies/UNKNOWN/research-answer",json={"question":"FY2024 revenue"})
        response=without_event_loop(request())
        self.assertEqual(response.status_code,404)
        self.assertEqual(loaders[-1].fact_reads,0)
    def test_input_validation(self):
        response=without_event_loop(self.request("revenue and net income for FY2024\u200b"))
        self.assertEqual(response.status_code,422)

if __name__ == "__main__": unittest.main()
