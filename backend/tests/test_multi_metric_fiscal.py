"""Synthetic offline contract checks, reusing the existing closed-fixture guard."""
import importlib.abc
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
import os

PRIMARY = Path(os.environ.get("FINLENS_TEST_BACKEND", Path(__file__).resolve().parents[1]))
CANDIDATE = Path(__file__).resolve().parents[1] / "app" / "research_answer_service.py"
sys.path[:0] = [str(PRIMARY / ".venv/Lib/site-packages"), str(PRIMARY)]
class Candidate(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "app.research_answer_service":
            return importlib.util.spec_from_file_location(fullname, CANDIDATE)
sys.meta_path.insert(0, Candidate())
support = runpy.run_path(str(PRIMARY / "tests/test_chinese_revenue_comparison.py"), run_name="synthetic_support")
a = support["answers"]
company, fact, Loader = support["company"], support["fact"], support["RecordLoader"]
from pydantic import TypeAdapter

class MultiTests(unittest.TestCase):
    def setUp(self):
        self.companies = [company(), company("MSFT", 2)]
        self.facts = [fact(2024, "100", 1), fact(2024, "25", 2, concept="NetIncomeLoss")]
    def query(self, q, facts=None):
        loader=Loader(self.companies, self.facts if facts is None else facts)
        result=a.answer_research_question(loader, "TEST", q)
        self.assertEqual((loader.company_reads, loader.fact_reads), (1,1))
        return result
    def test_two_and_three_and_provenance_parity(self):
        for q in ("What were revenue and net income for FY2024?", "revenue, gross profit, and net income for fiscal year 2024"):
            result=self.query(q)
            self.assertEqual(result.answer_kind, "multi_metric")
            for item in result.metrics:
                single=self.query(f"FY2024 {item.metric_label}")
                self.assertEqual(item.observation.model_dump(mode="json"), single.observation.model_dump(mode="json"))
                self.assertEqual(item.status, single.status)
            self.assertTrue(result.metrics[0].observation.provenance)
        self.assertEqual(result.metrics[1].status, "unavailable")
        self.assertTrue(result.metrics[1].explanation)
    def test_all_missing_and_three_item_order(self):
        result=self.query("revenue, gross profit, and net income for FY2024", facts=[])
        self.assertEqual(result.status, "unavailable")
        self.assertEqual([i.metric for i in result.metrics], ["revenue", "gross_profit", "net_income"])
        for item in result.metrics:
            self.assertEqual(item.status, "unavailable")
            self.assertTrue(item.explanation)
            self.assertEqual(item.observation.provenance, [])
    def test_single_compatibility_with_original_service(self):
        # Canonical JSON SHA-256 frozen from Git be3be0c research_answer_service.py,
        # blob b9009befe3c1e128422295bf511d6abfd7b9924e. See ExecPlan.
        import hashlib
        import json
        expected = {
            "FY2024 revenue": ("896043385e79da2b5a777eadf540e1cce1a0269d03f08ba3132e2ade6c99ec0f", 1),
            "latest revenue": ("1edfc4afb27c4595fbe0574aca73ecb956c8237f642d6718f454617db64f1a37", 1),
            "FY2024 gross margin": ("c25518e0958f892bc2fac7cffa4ce3579e4a1961c6cf0d419ea1929ae726061d", 1),
            "revenue and EBITDA for FY2024": ("34fab189596f140c325b1ecd81ca584dfbccfcd2e59611a666a2efc5d02488d7", 0),
        }
        for question, (digest, fact_reads) in expected.items():
            with self.subTest(question=question):
                loader = Loader(self.companies, self.facts)
                result = a.answer_research_question(loader, "TEST", question).model_dump(mode="json")
                canonical = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
                self.assertEqual(hashlib.sha256(canonical).hexdigest(), digest)
                self.assertEqual((loader.company_reads, loader.fact_reads), (1, fact_reads))
    def test_different_fiscal_windows_are_explicit(self):
        from datetime import date
        other = fact(2024, "25", 2, concept="NetIncomeLoss")
        other.period_start = date(2024, 2, 1)
        result = self.query("revenue and net income for FY2024", [fact(2024,"100",1), other])
        self.assertEqual([x.status for x in result.metrics], ["available", "available"])
        self.assertEqual(result.window_status, "incompatible")
        self.assertTrue(all(x.observation.provenance for x in result.metrics))
        self.assertEqual(self.query("revenue and net income for FY2024").window_status, "unverified")
    def test_single_and_union_wire(self):
        single=self.query("FY2024 revenue")
        self.assertNotIn("metrics", single.model_dump())
        adapter=TypeAdapter(a.MultiResearchAnswer | a.ResearchAnswer)
        self.assertEqual(adapter.dump_python(single, mode="json"), single.model_dump(mode="json"))
        multi=self.query("revenue and net income for FY2024")
        wire=adapter.dump_python(multi, mode="json")
        self.assertEqual(len(wire["metrics"]),2)
        self.assertEqual(wire["metrics"][0]["observation"],multi.metrics[0].observation.model_dump(mode="json"))
    def test_rejections_no_fact_reads(self):
        cases=("revenue and revenue for FY2024", "revenue and EBITDA for FY2024", "revenue and net income for 2024", "revenue and net income for FY2024 and FY2023", "revenue and net income for FY2024 why?", "not revenue and net income for FY2024", "revenue and net income for FY2024 adjusted", "revenue and net income for FY2024 for MSFT", "revenue and net income for FY2024 in euros", "revenue and net income for FY2024 except losses", "revenue and net income for FY2024\u200b", "revenue and gross profit and net income and total assets for FY2024")
        for q in cases:
            with self.subTest(q=q):
                loader=Loader(self.companies,forbid_facts=True)
                result=a.answer_research_question(loader,"TEST",q)
                self.assertFalse(result.matched)
                self.assertEqual(loader.fact_reads,0)
    def test_typed_handoff_failure_before_reads(self):
        from unittest.mock import patch
        loader=Loader(self.companies,forbid_facts=True)
        with patch.object(a,"operation_agrees",return_value=False):
            result=a.answer_research_question(loader,"TEST","revenue and net income for FY2024")
        self.assertFalse(result.matched)
        self.assertEqual(loader.fact_reads,0)

if __name__ == "__main__": unittest.main()
