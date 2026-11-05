"""Closed Chinese comparisons: pure records/loader, no database or network.

Standalone unittest; the scratch runner redirects only the service module.
FinancialMetrics, typed operation dispatch and provenance remain real code.
"""
import importlib.abc
import os
from pathlib import Path
import platform
import socket
import sys
import unittest

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND / ".venv/Lib/site-packages"), str(BACKEND)]
sys.dont_write_bytecode = True
platform.machine = lambda: "AMD64"
socket.gethostname = lambda: "synthetic-offline"
effects = dict(network=0, process=0, database=0, environment=0, write=0, import_guard=0)


class ForbiddenEffect(AssertionError):
    pass


class OfflineImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        allowed = {"app.research_answer_service", "app.financial_metric_registry", "app.financial_metric_schemas",
                   "app.financial_metrics_service", "app.models", "app.orm_base", "app.activation_lifecycle",
                   "app.sec_urls", "app.sec_parser", "app.revenue_scope_authorizations", "app.financial_metric_engine"}
        if (fullname.startswith("app.") and fullname not in allowed or fullname == "urllib.request"
                or fullname.split(".")[0] in {"dotenv", "psycopg", "psycopg2", "sqlite3", "requests", "httpx",
                                               "openai", "uvicorn", "fastapi", "torch", "sentence_transformers"}):
            effects["import_guard"] += 1
            raise ForbiddenEffect("offline_import_forbidden")


def audit(event, args):
    kind = None
    if event.startswith("socket."): kind = "network"
    elif event.startswith("subprocess.") or event in {"os.system", "os.posix_spawn"}: kind = "process"
    elif event in {"sqlite3.connect", "sqlite3.connect/handle"}: kind = "database"
    elif event == "open":
        name = os.fsdecode(args[0]).replace("\\", "/").rsplit("/", 1)[-1] if isinstance(args[0], (str, bytes, os.PathLike)) else ""
        if name == ".env" or name.startswith(".env."): kind = "environment"
        elif (args[1] and any(c in args[1] for c in "wax+")) or args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC): kind = "write"
    if kind:
        effects[kind] += 1
        raise ForbiddenEffect("offline_" + kind + "_forbidden")


sys.meta_path.insert(0, OfflineImports())
sys.addaudithook(audit)

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from unittest.mock import patch
from pydantic import ValidationError
from app import research_answer_service as answers
from app.models import Company, FinancialFact


def company(ticker="TEST", identifier=1):
    return Company(id=identifier, ticker=ticker, name="Synthetic Test Company", cik=f"{identifier:010d}", exchange="TEST")


def fact(year, value, identifier, *, concept="Revenues", unit="USD"):
    return FinancialFact(id=identifier, company_cik="0000000001", metric=concept, value=Decimal(value), unit=unit,
        period_start=date(year, 1, 1), period_end=date(year, 12, 31), period_type="annual",
        fiscal_year=year, fiscal_period="FY", form="10-K", filed=date(year + 1, 2, 1),
        accession_number=f"0000000001-{(year+1)%100:02d}-{identifier:06d}", source="SEC Company Facts API: " + concept,
        created_at=datetime(year+1,2,1,tzinfo=timezone.utc))


class RecordLoader:
    """Only a query-shape witness; never constructs an engine or executes SQL."""
    def __init__(self, companies, facts=(), *, forbid_facts=False):
        self.companies, self.facts, self.forbid_facts = companies, facts, forbid_facts
        self.company_reads, self.fact_reads = 0, 0

    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is Company:
            self.company_reads += 1
            return iter(self.companies)
        if entity is FinancialFact:
            self.fact_reads += 1
            if self.forbid_facts: raise AssertionError("rejected_request_loaded_facts")
            return iter(self.facts)
        raise AssertionError("unexpected_query")


class ChineseRevenueComparisons(unittest.TestCase):
    def setUp(self):
        self.company = company()
        self.companies = [self.company, company("MSFT", 2)]
        self.facts = [fact(2022, "40", 1), fact(2024, "100", 2), fact(2025, "110", 3)]

    def answer(self, question, facts=None):
        loader = RecordLoader(self.companies, self.facts if facts is None else facts)
        result = answers.answer_research_question(loader, "TEST", question)
        self.assertEqual(loader.company_reads, 1)
        self.assertEqual(loader.fact_reads, 1)
        return result.model_dump(mode="json")

    def rejects(self, question, status="not_matched"):
        loader = RecordLoader(self.companies, forbid_facts=True)
        with patch.object(answers, "FinancialMetrics", side_effect=AssertionError("rejection_constructed_metrics")):
            result = answers.answer_research_question(loader, "TEST", question)
        self.assertEqual(loader.company_reads, 1); self.assertEqual(loader.fact_reads, 0)
        self.assertFalse(result.matched); self.assertEqual(result.status, status)
        self.assertIsNone(result.comparison); self.assertIsNone(result.observation); self.assertIsNone(result.answer_text)

    def parity(self, chinese, english, facts=None):
        zh, rejection = answers.recognize_operation(chinese, self.company, self.companies)
        en, en_rejection = answers.recognize_operation(english, self.company, self.companies)
        self.assertIsNone(rejection); self.assertIsNone(en_rejection)
        self.assertEqual(zh, en); self.assertTrue(answers.operation_agrees(zh))
        actual, expected = self.answer(chinese, facts), self.answer(english, facts)
        self.assertEqual(actual.pop("question"), chinese); self.assertEqual(expected.pop("question"), english)
        self.assertEqual(actual, expected)  # every value, label, formula, period, source and explanation
        return actual

    def test_complete_alias_connector_script_and_spacing_forms(self):
        for verb in ("比較", "比较"):
            for alias in ("營收", "营收", "營業收入", "营业收入"):
                for connector in ("與", "与", "和"):
                    with self.subTest(verb=verb, alias=alias, connector=connector):
                        result = self.parity(f"{verb}2024財年{connector}2025财年的{alias}？", "compare FY2024 and FY2025 revenue")
                        self.assertEqual(result["status"], "available")
                        self.assertTrue(result["comparison"]["earlier"]["provenance"])
                        self.assertTrue(result["comparison"]["later"]["provenance"])
        for question in ("請比較 2024 財年 與 2025 財年 的 營收 ?", "请比较2024财年和2025财年营收",
                         "　請　比較　2024　財年　與　2025　財年　的　營收　？　"):
            with self.subTest(question=question): self.parity(question, "compare FY2024 and FY2025 revenue")

    def test_reversed_and_nonadjacent_labels_keep_english_semantics(self):
        for a, b in ((2025, 2024), (2022, 2025), (2025, 2022)):
            with self.subTest(years=(a,b)):
                result = self.parity(f"比較{a}財年與{b}財年的營收", f"compare FY{a} and FY{b} revenue")
                self.assertEqual(result["comparison"]["earlier_period"]["fiscal_year"], min(a,b))
        self.assertIn("Cumulative period-to-period", result["answer_text"])
        self.assertNotIn("Year-over-year", result["answer_text"])

    def test_explicit_ticker_is_catalog_bound_without_name_translation(self):
        for prefix in ("股票代號TEST的", "股票代碼test的", "股票代码 test 的 "):
            with self.subTest(prefix=prefix): self.parity("請比較"+prefix+"2024財年與2025財年的營收", "compare TEST FY2024 and FY2025 revenue")
        self.rejects("比較股票代號MSFT的2024財年與2025財年的營收", "company_mismatch")
        self.rejects("比較股票代码UNKNOWN的2024财年和2025财年营收")
        for ticker in ("NOT", "OR", "BRK.B", "BF-B"):
            self.company.ticker = ticker
            op, rejection = answers.recognize_operation(f"比較股票代號{ticker}的2024財年與2025財年營收", self.company, [self.company])
            self.assertIsNone(rejection); self.assertTrue(answers.operation_agrees(op))

    def test_unavailable_inputs_zero_baseline_and_other_currency_keep_exact_parity(self):
        scenarios = [[], [fact(2024,"100",1)], [fact(2024,"0",1),fact(2025,"110",2)],
                     [fact(2024,"100",1),fact(2025,"90",2)], [fact(2024,"100",1),fact(2025,"100",2)],
                     [fact(2024,"100",1),fact(2025,"110",2,unit="EUR")],
                     [fact(2024,"100",1),fact(2025,"110",2,concept="RevenuesNetOfInterestExpense")]]
        for facts in scenarios:
            with self.subTest(fact_ids=[f.id for f in facts]): self.parity("比較2024財年與2025財年的營收？", "compare FY2024 and FY2025 revenue", facts)

    def test_chinese_selected_company_name_is_not_a_normalization_exception(self):
        self.company.name="測試公司"
        result=self.answer("比較股票代號TEST的2024財年與2025財年營收")
        self.assertEqual(result["status"],"available"); self.assertEqual(result["company_name"],"測試公司")
        self.rejects("比較測試公司的2024財年與2025財年營收")

    def test_provenance_remains_selected_and_period_bound(self):
        foreign=fact(2025,"999999",99);foreign.company_cik="0000000002"
        result=self.parity("比較2024財年與2025財年營收", "compare FY2024 and FY2025 revenue", self.facts+[foreign])
        for side,year in (("earlier",2024),("later",2025)):
            point=result["comparison"][side]
            self.assertEqual(point["period"]["fiscal_year"],year)
            self.assertTrue(point["provenance"])
            self.assertTrue(all(p["company_cik"]=="0000000001" and p["fact_id"]!=99 for p in point["provenance"]))

    def test_explicit_year_bounds_are_recognized_without_date_inference(self):
        for a,b in ((1900,1901),(2098,2099)):
            op,rejection=answers.recognize_operation(f"比較{a}財年與{b}財年營收",self.company,self.companies)
            self.assertIsNone(rejection);self.assertEqual([p.fiscal_year for p in op.periods],[a,b])
            self.assertTrue(all(p.quarter is None for p in op.periods))

    def test_negations_qualifiers_growth_and_calendar_ambiguity_never_load_facts(self):
        questions = ["不要比較2024財年與2025財年的營收", "不比较2024财年和2025财年营收", "不是比較2024財年與2025財年的營收",
            "請解釋2024財年與2025財年的營收定義", "比較2024年與2025年營收", "比較2024與2025財年營收",
            "比較2024財年與2025營收", "比較2024日曆年與2025日曆年的營收", "比較去年財年與今年財年營收",
            "比較2024財年與2024財年的營收", "比較2024財年與2025財年的調整後營收", "比较2024财年和2025财年扣除利息营业收入",
            "比較2024財年與2025財年的營收成長率", "比较2024财年和2025财年营收增长", "比較2024財年與2025財年的營收年化增長",
            "比較2024財年與2025財年的營收增加多少", "比較2024財年與2025財年的營收百分比", "比較2024財年與2025財年的營收差異",
            "比較2024財年與2025財年的營收以人民幣計", "比较2024财年和2025财年营收换算美元", "比較2024財年與2025財年淨利",
            "比較2024財年與2025財年營收和淨利", "比較2023財年、2024財年與2025財年營收", "比較2024財年第二季與2025財年第二季營收",
            "比較2024財年與2025財年營收，並解釋原因", "比較2024財年與2025財年營收但不要給數字", "比較2024財年與2025財年營收或銷售額",
            "比較股票代號TEST和MSFT的2024財年與2025財年營收", "比較蘋果2024財年與2025財年營收", "比較TEST的2024財年與2025財年營收",
            "從2025財年到2024財年營收", "2024財年與2025財年的營收是多少？", "比較２０２４財年與２０２５財年營收",
            "比較1899財年與2025財年營收", "比較2024財年與2100財年營收"]
        for question in questions:
            with self.subTest(question=question): self.rejects(question)

    def test_adversarial_prefixes_suffixes_and_controls_are_not_discarded(self):
        question = "比較2024財年與2025財年的營收"
        for text in ("不要", "not ", "英文 ", "\u200b", "\u202e", "\n", "\r", "\t", "\x00", "\u2028", "\u2029",
                     "\u0301", " not revenue", " excluding interest", " AND net income", "; DROP TABLE facts", "<script>", "。", "??", "？不含某部門"):
            for value in (text+question, question+text):
                with self.subTest(question=value): self.rejects(value)
        for control in ("\n", "\u200b", "\u202e", "\u2028"):
            with self.assertRaises(ValidationError): answers.ResearchAnswerRequest(question=control+question)

    def test_original_unicode_gate_and_precomputed_intents_still_refuse_chinese(self):
        for question in ("比較2024財年與2025財年的營收", "不是 FY2024 的 revenue。", "請解釋 revenue 的定義，不要給我數字。"):
            self.assertFalse(answers.supported_question_text(question))
            for intent in (answers.MathematicalIntent("value"), answers.MathematicalIntent("level_change")):
                self.assertEqual(answers.recognize(question,self.company,self.companies,math_intent=intent)[2],"not_matched")
                self.assertIsNone(answers.recognize_historical(question,self.company,self.companies,math_intent=intent))
        with patch.object(answers,"words",side_effect=AssertionError("lossy_normalization")):
            op, rejection = answers.recognize_operation("比較2024財年與2025財年的營收",self.company,self.companies)
            self.assertIsNone(rejection); self.assertTrue(answers.operation_agrees(op))
            self.rejects("比較2024財年與2025財年的營收，不要給數字")

    def test_forged_handoff_cannot_load_facts(self):
        original=answers.recognize_operation("比較2024財年與2025財年的營收",self.company,self.companies)[0]
        for changes in (dict(operation="unsupported_relative_change"),dict(metric="operating_margin"),
                        dict(operands="growth_observations"),dict(math=answers.MathematicalIntent("value")),
                        dict(periods=tuple(reversed(original.periods))),dict(status="unsupported")):
            with self.subTest(changes=changes),patch.object(answers,"recognize_operation",return_value=(replace(original,**changes),None)):
                self.rejects("比較2024財年與2025財年的營收")

    def test_existing_single_value_and_english_questions_still_work(self):
        for question in ("2024財年的營收是多少？", "请问2025财年营收为多少?", "最新財年的營收是多少？",
                         "2024 revenue", "latest annual revenue", "Compare FY2024 and FY2025 revenue"):
            with self.subTest(question=question): self.assertEqual(self.answer(question)["status"],"available")
        for question in ("不是 FY2024 的 revenue。", "請解釋 revenue 的定義，不要給我數字。", "not FY2024 revenue", "2024 revenue / year"):
            with self.subTest(question=question): self.rejects(question)

    def test_effect_guards_are_positive_controls(self):
        for event,args in (("socket.connect",(None,("example.invalid",443))), ("subprocess.Popen",("synthetic",[],None,None)),
                           ("sqlite3.connect",("synthetic",)), ("open",(".env","r",0)), ("open",("synthetic","w",os.O_WRONLY))):
            with self.assertRaises(ForbiddenEffect): sys.audit(event,*args)
        with self.assertRaises(ForbiddenEffect): __import__("app.database")


if __name__ == "__main__":
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ChineseRevenueComparisons))
    print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
                         guarded_effect_positive_controls=effects,database="NOT_USED",network="NOT_USED",facts="synthetic records only")))
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)
