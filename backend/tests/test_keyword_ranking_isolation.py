"""02B.3A: python -I -S -B tests/test_keyword_ranking_isolation.py.

Independent guarded children; immutable legacy function is the behavior oracle.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = '002cb893ce312200416461f93cbbb22ab8458320'
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
builtins.open, io.open, os.open = map(protect, (builtins.open, io.open, os.open))
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden
allowed_app = {'app.keyword_ranking'}
blocked = {'dotenv', 'sqlalchemy', 'psycopg', 'sqlite3', 'httpx', 'requests',
           'openai', 'torch', 'transformers', 'sentence_transformers', 'huggingface_hub'}
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
'''

SERVICE_SETUP = r'''
allowed_app.update({'app.filing_search_service', 'app.models', 'app.orm_base',
    'app.embedding_service', 'app.embedding_validation', 'app.config', 'app.release_policy',
    'app.evidence_latency', 'app.freshness_service', 'app.refresh_contracts'})
blocked.remove('sqlalchemy')
import sqlalchemy
import sqlalchemy.engine.create
sqlalchemy.create_engine = forbidden
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = forbidden
sqlalchemy.engine_from_config = forbidden
dotenv = ModuleType('dotenv')
dotenv.load_dotenv = lambda *args, **kwargs: False  # Synthetic legacy config only.
sys.modules['dotenv'] = dotenv
from app import filing_search_service as service, freshness_service as fresh
from app.models import FilingChunk
'''


class KeywordRankingIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline_source = subprocess.run(
            ['git', 'show', f'{BASELINE}:backend/app/filing_search_service.py'],
            cwd=ROOT.parent, capture_output=True, text=True, check=True).stdout
        node = next(n for n in ast.parse(cls.baseline_source).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'search_filing_chunks')
        cls.oracle_source = 'from __future__ import annotations\n' + ast.unparse(node)

    def oracle(self):
        # Ranking-only probes bypass boundary validation; service probes replace
        # these globals with the real validator and tracked, synthetic reads.
        return f'''
oracle_globals = {{'FilingChunk': SimpleNamespace(company_cik='cik', accession_number='accession'),
                  'validate_research_input': lambda *args: None}}
exec(compile({self.oracle_source!r}, '<immutable-keyword-oracle>', 'exec'), oracle_globals)
oracle = oracle_globals['search_filing_chunks']
def expected_positions(rows, query, limit):
    oracle_globals['research_chunks'] = lambda *args: rows
    return [row.position for row in oracle(None, 'cik', 'accession', query, limit)]
'''

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
            self.assertNotEqual(result.returncode, 0, 'negative control unexpectedly succeeded')
            self.assertIn(failure, result.stderr)

    def test_fresh_import_is_stdlib_only_for_every_profile(self):
        for profile in (None, 'development', 'sec_readonly', 'sec_reader', 'unknown'):
            with self.subTest(profile=profile):
                self.probe('''
from app import keyword_ranking
assert not (set(sys.modules) & blocked)
assert {n for n in sys.modules if n.startswith('app.')} == {'app.keyword_ranking'}
''', profile=profile)

    def test_forbidden_import_and_bootstrap_controls_raise(self):
        for name in ('app.database', 'app.config', 'app.sec_client', 'app.embedding_service',
                     'dotenv', 'sqlalchemy', 'openai', 'sentence_transformers'):
            with self.subTest(name=name):
                self.probe('import ' + name, failure='forbidden import: ' + name)
        source = (ROOT / 'app' / 'keyword_ranking.py').read_text()
        self.probe(f"exec(compile('import app.database\\n' + {source!r}, '<import-mutant>', 'exec'))",
                   failure='forbidden import: app.database')
        for code in ("Path('/synthetic/.env').read_text()", "os.getenv('DATABASE_URL')",
                     "socket.create_connection(('127.0.0.1', 1))"):
            with self.subTest(code=code):
                self.probe(code, failure='forbidden initialization')

    def test_detached_ranking_matches_immutable_function(self):
        self.probe(self.oracle() + r'''
from dataclasses import FrozenInstanceError, fields
from itertools import permutations
from app.keyword_ranking import KeywordChunk, keyword_terms, rank_keyword_positions
assert [f.name for f in fields(KeywordChunk)] == ['position', 'chunk_index', 'text']
base = (KeywordChunk(9, 2, 'Revenue revenue, aaa'),
        KeywordChunk(1, 2, 'COST cost cost Straße'),
        KeywordChunk(7, 0, 'İ i\u0307 😀 revenue'))
queries = ['', ' \t\n', 'revenue', ' REVENUE ', 'revenue revenue cost', 'aa',
           'revenue,', 'cost\nrevenue', 'straße', 'STRASSE', 'İ', 'i\u0307',
           '😀', 'MISSING', 'revenue\u2003cost', 'rev enue']
datasets = [(), *permutations(base),
            tuple(KeywordChunk(i, i % 3, 'revenue') for i in range(52)),
            (KeywordChunk(0, 0, 'é'*3000),)]
for rows in datasets:
    before = repr(rows)
    for query in queries:
        for limit in (1, 5, 50):
            assert rank_keyword_positions(rows, keyword_terms(query), limit) == expected_positions(
                rows, query, limit), (query, limit)
    assert repr(rows) == before
try:
    base[0].text = 'changed'
except FrozenInstanceError:
    pass
else:
    raise AssertionError('ranking input is mutable')
''')

    def test_duplicate_and_tie_mutations_fail_the_oracle_comparison(self):
        source = (ROOT / 'app' / 'keyword_ranking.py').read_text()
        self.probe(self.oracle() + f'\nsource = {source!r}\n' + r'''
import ast
from app import keyword_ranking as kernel
def check(function, rows, query):
    assert function(rows, kernel.keyword_terms(query), 5) == expected_positions(rows, query, 5)
def mutant(damage):
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'rank_keyword_positions')
    if damage == 'duplicates':
        node.body.insert(1, ast.parse('search_terms = list(dict.fromkeys(search_terms))').body[0])
    else:
        sort = next(n for n in ast.walk(node) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == 'sort')
        sort.keywords[0].value.body.elts.append(ast.parse('item[1].position', mode='eval').body)
    namespace = dict(vars(kernel))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 '<ranking-mutant>', 'exec'), namespace)
    return namespace['rank_keyword_positions']
for damage, rows, query in (
    ('duplicates', (kernel.KeywordChunk(0, 0, 'revenue revenue'),
                    kernel.KeywordChunk(1, 1, 'cost cost cost')), 'revenue revenue cost'),
    ('ties', (kernel.KeywordChunk(9, 0, 'revenue'), kernel.KeywordChunk(1, 0, 'revenue')), 'revenue'),
):
    check(kernel.rank_keyword_positions, rows, query)
    try:
        check(mutant(damage), rows, query)
    except AssertionError:
        pass
    else:
        raise AssertionError('ranking mutation escaped parity comparison: ' + damage)
''')

    def test_legacy_identity_validation_read_order_and_exceptions(self):
        for profile in ('development', 'sec_readonly'):
            with self.subTest(profile=profile):
                self.probe(SERVICE_SETUP + self.oracle() + r'''
from app import keyword_ranking as kernel
oracle_globals['FilingChunk'] = FilingChunk
rows = [FilingChunk(id=1, chunk_index=2, text='revenue revenue'),
        FilingChunk(id=2, chunk_index=2, text='cost cost cost'),
        FilingChunk(id=3, chunk_index=0, text='nothing')]
def run(function, query, limit, read_error=False):
    events, captured = [], []
    def validate(q, n):
        events.append('validate')
        fresh.validate_research_input(q, n)
    def read(session, *predicates):
        events.append('read')
        assert session is owner
        captured.append([(str(p.compile()), p.compile().params) for p in predicates])
        if read_error:
            raise RuntimeError('synthetic read failure')
        return rows
    owner = object()
    function.__globals__.update(validate_research_input=validate, research_chunks=read)
    try:
        result = function(owner, '0000320193', '0000320193-26-000020', query, limit)
        assert type(result) is list
        assert all(type(row) is FilingChunk and any(row is original for original in rows) for row in result)
        value = ('return', [next(i for i, original in enumerate(rows) if row is original) for row in result])
    except Exception as exc:
        value = ('raise', type(exc), str(exc), getattr(exc, 'status_code', None),
                 getattr(exc, 'detail', None), getattr(exc, 'headers', None))
    return value, events, captured
for query, limit in [('', 5), (' \t\n', 5), (None, 5), ('x'*2001, 5),
                     ('revenue', 0), ('revenue', 51), ('revenue', True), ('revenue', '5'),
                     ('revenue', 1.5), ('revenue', 1), ('revenue revenue cost', 50),
                     ('MISSING', 5), ('é'*2000, 5)]:
    expected = run(oracle, query, limit)
    actual = run(service.search_filing_chunks, query, limit)
    assert actual == expected, (query, limit)
    assert len(actual[2]) <= 1
    assert actual[1] == (['validate', 'read'] if actual[0][0] == 'return' else ['validate'])
assert run(service.search_filing_chunks, 'revenue', 5, True) == run(oracle, 'revenue', 5, True)
rows[0].text = None
assert run(service.search_filing_chunks, 'revenue', 5) == run(oracle, 'revenue', 5)
assert 'app.database' not in sys.modules and 'app.sec_client' not in sys.modules
''', profile=profile)

    def test_normalization_and_detachment_happen_at_the_existing_boundary(self):
        self.probe(SERVICE_SETUP + self.oracle() + r'''
from app import keyword_ranking as kernel
oracle_globals['FilingChunk'] = FilingChunk
events = []
class TracedQuery(str):
    def strip(self, *args):
        events.append('strip')
        return super().strip(*args)
def validate(query, limit):
    events.append('validate')
    fresh.validate_research_input(query, limit)
rows = [FilingChunk(id=1, chunk_index=3, text='revenue revenue')]
def read(*args):
    events.append('read')
    return rows
for function in (oracle, service.search_filing_chunks):
    function.__globals__.update(validate_research_input=validate, research_chunks=read)
    events.clear()
    assert function(None, 'cik', 'accession', TracedQuery(' revenue revenue '), 5)[0] is rows[0]
    assert events == ['validate', 'strip', 'strip', 'read']
original = kernel.rank_keyword_positions
def rank(detached, terms, limit):
    assert events[-1] == 'read'
    assert type(detached) is tuple and type(detached[0]) is kernel.KeywordChunk
    assert detached[0] == kernel.KeywordChunk(0, 3, rows[0].text)
    assert terms == ['revenue', 'revenue'] and limit == 5
    return original(detached, terms, limit)
service.rank_keyword_positions = rank
assert service.search_filing_chunks(None, 'cik', 'accession', 'revenue revenue', 5)[0] is rows[0]
''', profile='development')

    def test_other_service_functions_and_signature_are_unchanged(self):
        original = ast.parse(self.baseline_source)
        current = ast.parse((ROOT / 'app' / 'filing_search_service.py').read_text())
        functions = []
        for tree in (original, current):
            function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                            and n.name == 'search_filing_chunks')
            functions.append(function)
            tree.body.remove(function)
        imports = [n for n in current.body if isinstance(n, ast.ImportFrom)
                   and n.module == 'app.keyword_ranking']
        self.assertEqual(len(imports), 1)
        self.assertEqual([n.name for n in imports[0].names],
                         ['KeywordChunk', 'keyword_terms', 'rank_keyword_positions'])
        current.body.remove(imports[0])
        self.assertEqual(ast.dump(original), ast.dump(current))
        self.assertEqual(ast.dump(functions[0].args), ast.dump(functions[1].args))
        self.assertEqual(ast.dump(functions[0].returns), ast.dump(functions[1].returns))

    def test_reader_import_and_capabilities_remain_diagnostic_only(self):
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
assert not (set(sys.modules) & {'app.database', 'app.filing_search_service', 'app.keyword_ranking'})
''', profile='sec_reader')


if __name__ == '__main__':
    unittest.main(verbosity=2)
