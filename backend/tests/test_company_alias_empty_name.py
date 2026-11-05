"""Pure recognizer regressions: no engine, session, data source or network."""
import importlib.abc
import os
from pathlib import Path
import platform
import socket
import sys
import unittest

BACKEND=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(BACKEND/".venv/Lib/site-packages"),str(BACKEND)]
sys.dont_write_bytecode=True
platform.machine=lambda:"AMD64"
socket.gethostname=lambda:"synthetic-offline"


class ForbiddenEffect(AssertionError): pass


def audit(event,args):
    forbidden=(event.startswith(("socket.","subprocess.")) or event in {"os.system","sqlite3.connect","sqlite3.connect/handle"})
    if event=="open":
        name=os.fsdecode(args[0]).replace("\\","/").rsplit("/",1)[-1] if isinstance(args[0],(str,bytes,os.PathLike)) else ""
        forbidden=(name==".env" or name.startswith(".env.") or bool(args[1] and any(c in args[1] for c in "wax+"))
                   or bool(args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)))
    if forbidden:raise ForbiddenEffect("offline_effect_forbidden")


class Imports(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        allowed={"app.research_answer_service","app.financial_metric_registry","app.financial_metric_schemas",
                 "app.financial_metrics_service","app.models","app.orm_base","app.activation_lifecycle",
                 "app.sec_urls","app.sec_parser","app.revenue_scope_authorizations","app.financial_metric_engine"}
        if (fullname.startswith("app.") and fullname not in allowed or fullname=="urllib.request"
                or fullname.split(".")[0] in {"dotenv","sqlite3","psycopg","psycopg2","requests","httpx","openai","fastapi","uvicorn"}):
            raise ForbiddenEffect("offline_import_forbidden")


sys.addaudithook(audit);sys.meta_path.insert(0,Imports())
from types import SimpleNamespace
from unittest.mock import patch
from app import research_answer_service as answers


def company(name,ticker="TEST"):
    return SimpleNamespace(name=name,ticker=ticker,cik="0000000001")


class EmptyCompanyAliases(unittest.TestCase):
    def test_empty_normalized_names_keep_only_existing_multi_character_ticker(self):
        for name in ("台積電","測試公司","東京電力","ΔΕΗ","😀","!!!","","  ","é\u0301","１２３"):
            with self.subTest(name=name):self.assertEqual(answers.company_aliases(company(name,"TSM")),{"tsm"})

    def test_empty_aliases_and_single_character_tickers_stay_excluded(self):
        for ticker in ("A","X",""):
            with self.subTest(ticker=ticker):self.assertEqual(answers.company_aliases(company("測試公司",ticker)),set())
        selected=company("測試公司","TSM")
        text,rejection=answers.company_question("latest annual revenue",selected,[selected])
        self.assertIsNone(rejection);self.assertEqual(text,"latest annual revenue")

    def test_existing_english_alias_sets_and_generic_first_word_exclusions(self):
        cases=[("Apple Inc.","AAPL",{"apple inc","apple","aapl"}),
               ("Microsoft Corporation","MSFT",{"microsoft corporation","microsoft","msft"}),
               ("General Electric Co.","GE",{"general electric co","general electric","ge"}),
               ("Bank of America Corp","BAC",{"bank of america corp","bank of america","bac"}),
               ("Home Depot Inc","HD",{"home depot inc","home depot","hd"}),
               ("測試 Apple Inc","AAPL",{"apple inc","apple","aapl"})]
        for name,ticker,expected in cases:
            with self.subTest(name=name):self.assertEqual(answers.company_aliases(company(name,ticker)),expected)

    def test_selected_non_latin_name_supports_unchanged_english_operations(self):
        selected=company("測試公司","TSM")
        for question in ("FY2024 revenue","TSM FY2024 revenue","latest annual revenue","compare FY2024 and FY2025 revenue"):
            with self.subTest(question=question):
                op,rejection=answers.recognize_operation(question,selected,[selected])
                self.assertIsNone(rejection);self.assertEqual(op.metric,"revenue");self.assertTrue(answers.operation_agrees(op))

    def test_unselected_non_latin_catalog_name_cannot_crash_other_company(self):
        selected,other=company("Apple Inc.","AAPL"),company("台積電","TSM")
        for question in ("AAPL FY2024 revenue","latest annual revenue","compare FY2024 and FY2025 revenue"):
            self.assertEqual(answers.recognize_operation(question,selected,[selected,other]),
                             answers.recognize_operation(question,selected,[selected]))

    def test_named_other_ticker_still_reports_mismatch(self):
        selected,other=company("Apple Inc.","AAPL"),company("台積電","TSM")
        op,rejection=answers.recognize_operation("TSM FY2024 revenue",selected,[selected,other])
        self.assertIsNone(op);self.assertEqual(rejection,"company_mismatch")

    def test_no_fact_or_metric_access_is_needed_for_recognition(self):
        selected=company("台積電","TSM")
        with patch.object(answers,"FinancialMetrics",side_effect=AssertionError("metric_access")), \
                patch.object(answers,"FinancialFact",None):
            op,rejection=answers.recognize_operation("compare FY2024 and FY2025 revenue",selected,[selected])
        self.assertIsNone(rejection);self.assertTrue(answers.operation_agrees(op))

    def test_unicode_guard_and_unlabelled_chinese_names_are_not_widened(self):
        selected=company("台積電","TSM")
        for question in ("台積電 FY2024 revenue","不是 FY2024 revenue","FY2024 revenue\u200b"):
            self.assertEqual(answers.recognize(question,selected,[selected],math_intent=answers.MathematicalIntent("value"))[2],"not_matched")
            self.assertEqual(answers.recognize_operation(question,selected,[selected])[1],"not_matched")

    def test_positive_no_io_controls(self):
        for event,args in (("socket.connect",()),("subprocess.Popen",()),("sqlite3.connect",()),("open",(".env","r",0)),("open",("synthetic","w",os.O_WRONLY))):
            with self.assertRaises(ForbiddenEffect):sys.audit(event,*args)
        with self.assertRaises(ForbiddenEffect):__import__("app.database")


if __name__=="__main__":unittest.main(verbosity=2)
