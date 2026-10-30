"""02B.2 offline probes: python -I -S -B tests/test_pure_helper_isolation.py.

Stdlib parent, fresh guarded children, immutable reference implementations.
No SQL, real engines, services, acquisition or model loading.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = '560dc30c00e56cd3a8978feb87140f42a97359f8'
GUARDS = r'''
import builtins, importlib, importlib.abc, io, os, socket, sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

attempts = []
def forbidden(*args, **kwargs):
    attempts.append('initialization')
    raise AssertionError('forbidden initialization')
def protect(original):
    def guarded(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(path)).replace('\\', '/').rsplit('/', 1)[-1]
            if name == '.env' or name.startswith('.env.'):
                forbidden()
        return original(path, *args, **kwargs)
    return guarded
builtins.open = protect(builtins.open)
io.open = protect(io.open)
os.open = protect(os.open)
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden

allowed_app = {'app.sec_urls', 'app.embedding_validation'}
blocked = {'dotenv', 'sqlalchemy', 'psycopg', 'sqlite3', 'httpx', 'requests',
           'openai', 'torch', 'transformers', 'sentence_transformers',
           'huggingface_hub', 'tensorflow'}
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if ((fullname.startswith('app.') and fullname not in allowed_app)
                or fullname.split('.')[0] in blocked):
            attempts.append(fullname)
            raise AssertionError('forbidden import: ' + fullname)
sys.meta_path.insert(0, Guard())
original_getitem = type(os.environ).__getitem__
def getitem(environ, key):
    if key == 'DATABASE_URL':
        forbidden()
    return original_getitem(environ, key)
type(os.environ).__getitem__ = getitem

def outcome(function, *args):
    try:
        return ('return', function(*args))
    except Exception as exc:
        cause = exc.__cause__
        return ('raise', type(exc), str(exc),
                None if cause is None else (type(cause), str(cause)))
'''

READ_SETUP = r'''
allowed_app.update({'app.models', 'app.orm_base', 'app.freshness_service',
                   'app.refresh_contracts', 'app.evidence_latency'})
blocked.remove('sqlalchemy')
import sqlalchemy
import sqlalchemy.engine.create
sqlalchemy.create_engine = forbidden
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = forbidden
sqlalchemy.engine_from_config = forbidden
'''

LEGACY_SETUP = READ_SETUP + r'''
allowed_app.update({'app.config', 'app.release_policy', 'app.sec_client', 'app.embedding_service'})
blocked.remove('httpx')
import httpx
httpx.Client = forbidden
httpx.AsyncClient = forbidden
dotenv_calls = []
dotenv = ModuleType('dotenv')
def synthetic_dotenv(path, *, override=False):
    dotenv_calls.append((path, override))
    return False
dotenv.load_dotenv = synthetic_dotenv
sys.modules['dotenv'] = dotenv
'''

CHUNKS = r'''
from datetime import date
from copy import deepcopy
from app import freshness_service as fresh
from app.sec_urls import build_filing_url
CIK, ACC = '0000320193', '0000320193-26-000020'
def chunks():
    return [SimpleNamespace(company_cik=CIK, accession_number=ACC,
        chunk_index=i, chunk_id=f'chunk_{i:04d}', text=text,
        form='10-Q', filed=date(2026, 7, 31), filename='report.htm',
        start_char=i*10, end_char=i*10+len(text)+2,
        sec_url=build_filing_url(CIK, ACC), embedding=[1.0]+[0.0]*383)
        for i, text in enumerate((' Revenue 😀\r\n', 'e\u0301 retained text'))]
'''


class PureHelperIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {}
        for name in ('sec_client', 'embedding_service', 'freshness_service',
                     'financial_metrics_service', 'financial_insights_service'):
            cls.sources[name] = subprocess.run(
                ['git', 'show', f'{BASELINE}:backend/app/{name}.py'], cwd=ROOT.parent,
                capture_output=True, text=True, check=True).stdout

    def reference(self):
        code = ['import math, hashlib', 'from array import array', 'EMBEDDING_DIMENSION = 384']
        for module, names in (
            ('sec_client', {'build_filing_url', 'build_filing_raw_url'}),
            ('embedding_service', {'validate_embedding'}),
            ('freshness_service', {'validate_chunks', 'chunk_digest'}),
        ):
            for node in ast.parse(self.sources[module]).body:
                if isinstance(node, ast.FunctionDef) and node.name in names:
                    # Reference only: supply the original pure functions as globals
                    # instead of importing operational modules inside validate_chunks.
                    node.body = [n for n in node.body if not isinstance(n, ast.ImportFrom)]
                    code.append(ast.unparse(node))
        return 'reference = {}\nexec(' + repr('\n'.join(code)) + ', reference)\n'

    def probe(self, code, *, profile=None, failure=None):
        env = {k: v for k, v in os.environ.items()
               if k != 'DATABASE_URL' and not k.startswith(('FINLENS_', 'OPENAI_', 'PG'))}
        if profile is not None:
            env['FINLENS_SERVER_PROFILE'] = profile
        setup = f"import sys\nsys.path[:0] = {[str(ROOT / '.venv' / 'Lib' / 'site-packages'), str(ROOT)]!r}\n"
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c',
                                 setup + GUARDS + '\n' + textwrap.dedent(code)
                                 + '\nassert not attempts, attempts\n'],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        if failure is None:
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, 'negative control succeeded')
            self.assertIn(failure, result.stderr)

    def test_pure_imports_require_no_application_or_third_party_stack(self):
        for profile in (None, 'development', 'sec_readonly', 'sec_reader', 'unknown'):
            for target in ('app.sec_urls', 'app.embedding_validation'):
                with self.subTest(profile=profile, target=target):
                    self.probe(f"""
                        importlib.import_module({target!r})
                        assert not (set(sys.modules) & blocked)
                        assert {{n for n in sys.modules if n.startswith('app.')}} <= allowed_app
                    """, profile=profile)

    def test_raising_import_and_initialization_controls(self):
        cases = [(f'import {name}', 'forbidden import: ' + name) for name in
                 ('app.config', 'app.database', 'app.sec_client', 'app.embedding_service',
                  'app.refresh_service', 'dotenv', 'sqlalchemy', 'psycopg', 'httpx',
                  'openai', 'sentence_transformers', 'huggingface_hub')]
        cases += [("Path('/synthetic/.env').read_text()", 'forbidden initialization'),
                  ("os.getenv('DATABASE_URL')", 'forbidden initialization'),
                  ("socket.create_connection(('127.0.0.1', 1))", 'forbidden initialization')]
        for code, failure in cases:
            with self.subTest(code=code):
                self.probe(code, failure=failure)

    def test_url_outputs_and_exception_causes_match_immutable_baseline(self):
        self.probe(self.reference() + r'''
from app import sec_urls
ciks = ['0000320193', '  +0000320193 ', '0', '-1', '٣٢٠١٩٣', b'0000320193',
        320193, 1.9, True, None, '', 'not-a-cik', float('nan'), float('inf'), 10**40]
accessions = ['0000320193-26-000020', '', '--', '../odd?x#fragment', 'é\r\n',
              None, 12, b'0000320193-26-000020']
for name in ('build_filing_url', 'build_filing_raw_url'):
    for cik in ciks:
        for accession in accessions:
            assert outcome(getattr(sec_urls, name), cik, accession) == outcome(
                reference[name], cik, accession), (name, type(cik), type(accession))
assert sec_urls.build_filing_url('0000320193', '0000320193-26-000020') == (
    'https://www.sec.gov/Archives/edgar/data/320193/000032019326000020/0000320193-26-000020-index.html')
''')

    def test_float32_vector_results_errors_and_input_preservation(self):
        self.probe(self.reference() + r'''
from array import array
from decimal import Decimal
from app.embedding_validation import EMBEDDING_DIMENSION, validate_embedding
assert EMBEDDING_DIMENSION == 384
cases = [lambda: None, lambda: 384, lambda: [], lambda: [1.0]*383,
         lambda: [1.0]*385, lambda: [0.0]*384, lambda: [-0.0]*384,
         lambda: [1.0]+[0.0]*383, lambda: tuple([-1.0]*384),
         lambda: [True]*384, lambda: array('d', [0.25]*384),
         lambda: [Decimal('0.1')]*384, lambda: iter([1.0]*384),
         lambda: b'\x01'*384, lambda: 'a'*384, lambda: dict.fromkeys(range(384))]
for value in (float('nan'), float('inf'), -float('inf'), 1e100, 1e-50,
              1e-45, 3.4028234663852886e38, 3.4028236e38, 'bad', None, 1+2j):
    cases.append(lambda value=value: [value]*384)
    cases.append(lambda value=value: [1.0]+[value]*383)
for case in cases:
    candidate, prior = case(), case()
    before = repr(candidate)
    assert outcome(validate_embedding, candidate) == outcome(reference['validate_embedding'], prior)
    assert repr(candidate) == before
''')

    def test_legacy_exports_and_profile_guards_are_preserved(self):
        for profile in ('development', 'sec_readonly'):
            with self.subTest(profile=profile):
                self.probe(LEGACY_SETUP + '''
from app import sec_urls, embedding_validation, sec_client, embedding_service, config
assert sec_client.build_filing_url is sec_urls.build_filing_url
assert sec_client.build_filing_raw_url is sec_urls.build_filing_raw_url
assert embedding_service.validate_embedding is embedding_validation.validate_embedding
assert embedding_service.EMBEDDING_DIMENSION == embedding_validation.EMBEDDING_DIMENSION == 384
assert config.server_profile().generation_allowed == (config.server_profile().name == 'development')
assert len(dotenv_calls) == 2 and all(override is False for _, override in dotenv_calls)
from app.release_policy import require_development, ReleaseModeBlocked
if config.server_profile().name == 'sec_readonly':
    try:
        sec_client._sec_get(object())
    except ReleaseModeBlocked:
        pass
    else:
        raise AssertionError('acquisition guard bypassed')
else:
    require_development()
assert 'app.database' not in sys.modules
assert not (set(sys.modules) & {'openai', 'sentence_transformers', 'huggingface_hub'})
''', profile=profile)

    def test_chunk_validation_and_digest_parity_without_operational_imports(self):
        self.probe(READ_SETUP + self.reference() + CHUNKS + r'''
pristine = chunks()
identity = repr(pristine)
assert outcome(fresh.validate_chunks, pristine) == ('return', None)
assert repr(pristine) == identity
assert fresh.chunk_digest(pristine) == reference['chunk_digest'](pristine)
damages = [('chunk_index', 0), ('chunk_id', 'wrong'), ('text', '  '),
    ('form', '8-K'), ('filed', None), ('filename', ''), ('start_char', -1),
    ('end_char', 0), ('end_char', 1), ('company_cik', '0000000001'),
    ('accession_number', '0000000001-26-000001'), ('filename', 'other.htm'),
    ('sec_url', 'https://example.invalid/'), ('embedding', None),
    ('embedding', [0.0]*384), ('embedding', [float('nan')]*384),
    ('embedding', [float('inf')]*384), ('embedding', [1e-50]*384),
    ('embedding', [1.0]), ('embedding', ['bad']*384)]
for field, value in damages:
    candidate = chunks()
    setattr(candidate[1], field, value)
    before = repr(candidate)
    actual = outcome(fresh.validate_chunks, candidate)
    assert actual == outcome(reference['validate_chunks'], candidate), field
    assert actual[0] == 'raise', field
    assert repr(candidate) == before
assert outcome(fresh.validate_chunks, []) == outcome(reference['validate_chunks'], [])
for bodies in ([], chunks(), list(reversed(chunks()))):
    assert fresh.chunk_digest(bodies) == reference['chunk_digest'](bodies)
changed = chunks()
changed[1].text = 'changed passage'
assert fresh.chunk_digest(changed) != fresh.chunk_digest(pristine)
assert 'app.sec_client' not in sys.modules and 'app.embedding_service' not in sys.modules
assert 'app.config' not in sys.modules and 'app.database' not in sys.modules
''')

    def test_financial_consumers_import_without_sec_acquisition(self):
        self.probe(READ_SETUP + '''
allowed_app.update({'app.financial_metrics_service', 'app.financial_insights_service',
    'app.financial_metric_engine',
    'app.financial_metric_registry', 'app.financial_metric_schemas',
    'app.financial_insights_contract', 'app.financial_insights_schemas',
    'app.revenue_scope_authorizations', 'app.sec_evidence_adapter',
    'app.sec_parser', 'app.activation_lifecycle'})
from app import financial_metrics_service, financial_insights_service, sec_urls
assert financial_metrics_service.build_filing_url is sec_urls.build_filing_url
financial_insights_service.registry_guard()
assert 'app.sec_client' not in sys.modules and 'app.database' not in sys.modules
assert 'app.config' not in sys.modules and 'app.embedding_service' not in sys.modules
''')

    def test_reader_still_has_only_disabled_diagnostics(self):
        self.probe('''
allowed_app.update({'app.config', 'app.release_policy', 'app.sec_reader'})
dotenv = ModuleType('dotenv')
dotenv.load_dotenv = forbidden
sys.modules['dotenv'] = dotenv
from app import sec_reader
import json
assert {(method, route.path) for route in sec_reader.app.routes for method in route.methods} == {
    ('GET', '/healthz'), ('GET', '/capabilities')}
assert json.loads(sec_reader.capabilities().body) == {
    'research_mode': False, 'ai_analysis_configured': False,
    'ai_analysis_enabled': False, 'server_profile': 'sec_reader'}
assert not (set(sys.modules) & {'app.database', 'app.models', 'app.sec_client', 'app.embedding_service'})
''', profile='sec_reader')

    def test_source_ast_changes_are_only_moves_and_import_substitutions(self):
        moves = {'sec_client': {'build_filing_url', 'build_filing_raw_url'},
                 'embedding_service': {'validate_embedding'}}
        for name, source in self.sources.items():
            if name == 'financial_metrics_service':
                # C5 intentionally extracts this module. Its fixed 6838af1
                # serialization oracle and actual delegation tests live in
                # test_financial_metrics.py, rather than a whole-module AST lock.
                continue
            original = ast.parse(source)
            if name in moves:
                original.body = [n for n in original.body
                                 if not (isinstance(n, ast.FunctionDef) and n.name in moves[name])]
            if name == 'sec_client':
                original.body.insert(1, ast.parse(
                    'from app.sec_urls import build_filing_url, build_filing_raw_url').body[0])
            if name == 'embedding_service':
                original.body = [n for n in original.body if not (
                    isinstance(n, ast.Import) and any(a.name == 'math' for a in n.names)) and not (
                    isinstance(n, ast.ImportFrom) and n.module == 'array') and not (
                    isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                        and t.id == 'EMBEDDING_DIMENSION' for t in n.targets))]
                original.body.insert(1, ast.parse(
                    'from app.embedding_validation import EMBEDDING_DIMENSION, validate_embedding').body[0])
            for node in ast.walk(original):
                if isinstance(node, ast.ImportFrom):
                    if name in {'freshness_service', 'financial_metrics_service', 'financial_insights_service'}:
                        node.module = {'app.sec_client': 'app.sec_urls',
                                       'app.embedding_service': 'app.embedding_validation'}.get(node.module, node.module)
            current = ast.parse((ROOT / 'app' / f'{name}.py').read_text())
            with self.subTest(module=name):
                self.assertEqual(ast.dump(original), ast.dump(current))
        for old, new in (('sec_client', 'sec_urls'), ('embedding_service', 'embedding_validation')):
            baseline = {n.name: n for n in ast.parse(self.sources[old]).body if isinstance(n, ast.FunctionDef)}
            extracted = [n for n in ast.parse((ROOT / 'app' / f'{new}.py').read_text()).body
                         if isinstance(n, ast.FunctionDef)]
            self.assertEqual({n.name for n in extracted}, moves[old])
            for node in extracted:
                self.assertEqual(ast.dump(node), ast.dump(baseline[node.name]))

    def test_financial_engine_import_and_execution_need_no_operational_modules(self):
        self.probe('''
allowed_app.update({'app.financial_metric_engine', 'app.financial_metric_registry'})
from app.financial_metric_engine import FinancialMetricEngine, Observation, Metric
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
class Denied:
    def __getattr__(self, name):
        raise AssertionError('No permission operation needed for approved total revenue')
row = Observation(7, 'Revenues', Decimal('100'), 'USD', date(2025,1,1),
    date(2025,12,31), 'annual', date(2026,2,1), '10-K', '0000000001-26-000001', ('revenue',))
engine = FinancialMetricEngine((row,), Denied())
point = engine.observation('revenue', engine.period('annual', row.start, row.end))
assert point.value == Decimal('100') and point.provenance[0].observation is row
for obj, field in ((row, 'value'), (point, 'value'), (point.period, 'end'),
                   (point.provenance[0], 'metric')):
    try:
        setattr(obj, field, None)
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError('Mutable internal observation/result')
assert not attempts
assert not (set(sys.modules) & {'app.models', 'app.database', 'app.config',
    'app.sec_client', 'app.sec_evidence_adapter', 'app.revenue_scope_authorizations',
    'app.activation_lifecycle', 'sqlalchemy', 'dotenv', 'bs4', 'pydantic'})
''')


if __name__ == '__main__':
    unittest.main(verbosity=2)
