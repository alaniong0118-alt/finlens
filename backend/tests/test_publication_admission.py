"""02B.3B1 offline verification: python -I -S -B tests/test_publication_admission.py.

Fresh guarded children, synthetic sessions, immutable Tone oracle; no SQL execution.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'a488b7b28c7da2775f73f530fcc49f21015782b8'
GUARDS = r'''
import builtins, importlib.abc, io, os, socket, sys
from pathlib import Path
from types import SimpleNamespace as NS, ModuleType
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
socket.socket.connect = socket.socket.connect_ex = forbidden
socket.create_connection = socket.getaddrinfo = forbidden
allowed_app = {'app.publication_admission', 'app.freshness_service', 'app.models',
    'app.orm_base', 'app.refresh_contracts', 'app.evidence_latency',
    'app.sec_urls', 'app.embedding_validation', 'app.filing_tone_service', 'app.filing_tone',
    'app.reader_resource_policy'}
blocked = {'dotenv', 'psycopg', 'sqlite3', 'httpx', 'requests', 'openai', 'torch',
           'transformers', 'sentence_transformers', 'huggingface_hub', 'tensorflow'}
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
import sqlalchemy, sqlalchemy.engine.create
sqlalchemy.create_engine = sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = sqlalchemy.engine_from_config = forbidden
'''

FIXTURES = r'''
from datetime import date
from dataclasses import fields, is_dataclass, FrozenInstanceError
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from app import publication_admission as core, filing_tone_service as tone
from app import freshness_service as fresh
from app.models import Company, CompanyRefreshState, FilingChunk, FilingPublication
from app.sec_urls import build_filing_url
CIK, ACC = '0000320193', '0000320193-26-000020'
VECTOR = [1.0] + [0.0] * 383
def chunk(i=0, text='strong strong weak'):
    return FilingChunk(id=i+1, company_cik=CIK, accession_number=ACC, form='10-Q',
        filed=date(2026, 7, 31), filename='report.htm', chunk_index=i,
        chunk_id=f'chunk_{i:04d}', start_char=i*2250, end_char=i*2250+len(text),
        text=text, embedding=VECTOR, sec_url=build_filing_url(CIK, ACC))
def inventory(chunks):
    return [NS(**{f: getattr(c, f) for f in fresh.CHUNK_IDENTITY_FIELDS},
               text_length=len(c.text)) for c in chunks]
class Store:
    def __init__(self, chunks=None):
        self.chunks = [chunk(), chunk(1, 'other passage')] if chunks is None else chunks
        self.inventory = inventory(self.chunks)
        self.company = Company(id=1, ticker='AAPL', cik=CIK, name='Apple')
        self.state = CompanyRefreshState(company_cik=CIK, data_version=0,
            evidence_version=0, evidence={})
        self.publications = [NS(company_cik=CIK, accession_number=ACC, form='10-Q',
            filed=date(2026, 7, 31), filename='report.htm', chunk_count=len(self.chunks),
            content_digest=fresh.chunk_digest(self.chunks), data_version=0)]
        self.events, self.statements = [], []
        self.body_override = None
    def record(self, stmt):
        compiled = stmt.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        assert sql.startswith('SELECT') and 'cleaned_text' not in sql
        self.statements.append((sql, compiled.params, dict(stmt.get_execution_options())))
    def scalar(self, stmt):
        self.record(stmt)
        self.events.append('company')
        return self.company
    def connection(self):
        self.events.append('connection')
        return self
    def get(self, model, key):
        assert model is CompanyRefreshState and key == CIK
        self.events.append('state')
        return self.state
    def execute(self, stmt):
        self.record(stmt)
        entity = stmt.column_descriptions[0]['entity']
        if entity is FilingPublication:
            assert tuple(c.key for c in stmt.selected_columns) == core.PUBLICATION_FIELDS
            self.events.append('manifest')
            return self.publications[:2]
        assert entity is FilingChunk
        self.events.append('inventory')
        return self.inventory[:4001]
    def scalars(self, stmt):
        self.record(stmt)
        self.events.append('bodies')
        return self.chunks if self.body_override is None else self.body_override
    close = invalidate = commit = rollback = add = flush = forbidden
core.schema_ready = lambda _: True
def outcome(resolver, store, pin='0', selected='chunk_0000'):
    try:
        passage = resolver(store, 'aapl', ACC, selected, pin)
        scorer = sys.modules[resolver.__module__].score_published_passage
        return ('ok', scorer(passage).model_dump_json())
    except HTTPException as exc:
        return ('error', exc.status_code, exc.detail, exc.headers)
'''


class PublicationAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = subprocess.run(
            ['git', 'show', f'{BASELINE}:backend/app/filing_tone_service.py'],
            cwd=ROOT.parent, capture_output=True, text=True, check=True).stdout

    def probe(self, code, *, failure=None, profile=None):
        env = {k: v for k, v in os.environ.items()
               if k != 'DATABASE_URL' and not k.startswith(('FINLENS_', 'OPENAI_', 'PG'))}
        if profile is not None:
            env['FINLENS_SERVER_PROFILE'] = profile
        setup = f'import sys\nsys.path[:0] = {[str(ROOT / ".venv" / "Lib" / "site-packages"), str(ROOT)]!r}\n'
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c',
            setup + GUARDS + '\n' + textwrap.dedent(code) + '\nassert not attempts, attempts\n'],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        if failure is None:
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, 'negative control succeeded')
            self.assertIn(failure, result.stderr)

    def oracle(self):
        return f'''
oracle = ModuleType('immutable_tone')
sys.modules[oracle.__name__] = oracle
exec(compile({self.source!r}, '<immutable-tone-oracle>', 'exec'), oracle.__dict__)
oracle.schema_ready = core.schema_ready
'''

    def test_imports_are_inert_in_all_profiles(self):
        for profile in (None, 'development', 'sec_readonly', 'sec_reader', 'unknown'):
            with self.subTest(profile=profile):
                self.probe('from app import publication_admission\n'
                           'assert {n for n in sys.modules if n.startswith("app.")} <= allowed_app',
                           profile=profile)

    def test_guards_and_import_mutant_are_detected(self):
        for name in ('app.database', 'app.config', 'app.sec_client', 'app.embedding_service',
                     'app.main', 'app.sec_reader', 'dotenv', 'psycopg', 'openai', 'torch'):
            with self.subTest(name=name):
                self.probe('import ' + name, failure='forbidden import: ' + name)
        for code in ('sqlalchemy.create_engine("synthetic")', 'os.getenv("DATABASE_URL")',
                     'Path("/synthetic/.env").read_text()',
                     'socket.create_connection(("127.0.0.1", 1))'):
            self.probe(code, failure='forbidden initialization')
        source = (ROOT / 'app/publication_admission.py').read_text(encoding='utf-8')
        self.probe(f'exec(compile("import app.database\\n" + {source!r}, "<mutant>", "exec"))',
                   failure='forbidden import: app.database')

    def test_detached_complete_output_and_pin_validation(self):
        self.probe(FIXTURES + r'''
store = Store()
result = core.admit_complete_publication(store, 'aapl', ACC, 0)
assert result.publication.content_digest == fresh.chunk_digest(store.chunks)
assert len(result.chunks) == 2 and result.data_version == 0
def detached(value):
    if is_dataclass(value):
        assert value.__dataclass_params__.frozen
        for field in fields(value):
            detached(getattr(value, field.name))
        try:
            setattr(value, fields(value)[0].name, None)
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError('mutable evidence')
    elif type(value) is tuple:
        for member in value: detached(member)
    else:
        assert type(value) in (str, int, date), type(value)
detached(result)
store.chunks[0].text = 'modified after admission'
store.company.name = 'modified'
assert result.chunks[0].text == 'strong strong weak' and result.company_name == 'Apple'
assert store.events == ['company', 'connection', 'state', 'manifest', 'inventory', 'bodies']
for ticker, accession, pin in [('AAPL', ACC, p) for p in (None, True, -1, 0.0, '0', 2**53)] + [
    ('bad ticker', ACC, 0), ('AAPL', 'bad', 0)]:
    store = Store()
    try: core.admit_complete_publication(store, ticker, accession, pin)
    except HTTPException as exc: assert exc.status_code == 422
    else: raise AssertionError('invalid input accepted')
    assert not store.events
''')

    def test_tone_matches_immutable_oracle_for_integrity_matrix(self):
        self.probe(FIXTURES + self.oracle() + r'''
cases = [('valid', lambda s: None, '0', 'chunk_0000'),
         ('selected-second', lambda s: None, '0', 'chunk_0001'),
         ('missing-selected', lambda s: None, '0', 'chunk_0099')]
def add(name, mutate, pin='0', selected='chunk_0000'):
    cases.append((name, mutate, pin, selected))
for pin in (None, '', True, 0, '00', '-1', '1', '9007199254740992'):
    add('pin', lambda s: None, pin)
for value in (None, {}, [], '', 0, False, {'pending_targets': ACC},
              {'extra': 1}, {'status': 'invented'}, {'pending_targets': [ACC]}):
    add('lifecycle', lambda s, v=value: setattr(s.state, 'evidence', v))
for field, values in {
    'data_version': (None, True, 1, -1, 0.0, '0'), 'evidence_version': (-1, True, 1),
    'company_cik': ('0000000001',),
}.items():
    for value in values:
        add('state', lambda s, f=field, v=value: setattr(s.state, f, v))
add('no-company', lambda s: setattr(s, 'company', None))
add('no-state', lambda s: setattr(s, 'state', None))
add('no-manifest', lambda s: setattr(s, 'publications', []))
add('duplicate-manifest', lambda s: setattr(s, 'publications', s.publications*2))
for field, values in {
    'company_cik': ('0000000001',), 'accession_number': ('0000000001-26-000001',),
    'form': ('8-K',), 'filed': ('2026-07-31',), 'filename': ('../bad.htm', 'bad#x'),
    'chunk_count': (0, True, 3, 4001), 'data_version': (-1, True, 1),
    'content_digest': (None, 'g'*64, '0'*64),
}.items():
    for value in values:
        add('manifest', lambda s, f=field, v=value: setattr(s.publications[0], f, v))
for field, value in [('company_cik', '0000000001'), ('accession_number', 'foreign'),
    ('form', '10-K'), ('filed', date(2025, 1, 1)), ('filename', 'different.htm'),
    ('sec_url', 'https://evil.invalid/'), ('chunk_id', 'chunk_0099'), ('chunk_index', 3),
    ('start_char', -1), ('end_char', 1), ('text', 'alter passage'), ('text', ' '*13)]:
    def damage(s, f=field, v=value):
        setattr(s.chunks[1], f, v)
        s.inventory = inventory(s.chunks)
    add('unselected-'+field, damage)
for vector in (None, [], [1.0], [0.0]*384, [float('nan')]*384,
               [float('inf')]*384, [1e100]*384, ['bad']*384):
    add('unselected-vector', lambda s, v=vector: setattr(s.chunks[1], 'embedding', v))
add('missing-body', lambda s: setattr(s, 'body_override', s.chunks[:1]))
add('duplicate-body', lambda s: setattr(s, 'body_override', [s.chunks[0]]*2))
add('foreign-body', lambda s: setattr(s.chunks[1], 'id', 100))
add('identity-race', lambda s: setattr(s.chunks[1], 'filename', 'changed.htm'))
add('inventory-duplicate', lambda s: setattr(s, 'inventory', [s.inventory[0]]*2))
add('inventory-missing', lambda s: setattr(s, 'inventory', s.inventory[:1]))
for size in (None, 3001):
    add('inventory-bound', lambda s, v=size: setattr(s.inventory[1], 'text_length', v))
def older(s):
    s.state.data_version = 8
    s.state.evidence_version = 2
    s.state.evidence = {'status': 'failed', 'pending_targets': ['other']}
add('old-publication', older, '8')
for name, mutate, pin, selected in cases:
    left, right = Store(), Store()
    mutate(left); mutate(right)
    expected = outcome(oracle.resolve_published_passage, left, pin, selected)
    actual = outcome(tone.resolve_published_passage, right, pin, selected)
    assert actual == expected, (name, actual, expected)
    assert left.events == right.events and left.statements == right.statements, name
    # Missing selection must never conceal publication damage.
    if actual[0] == 'error' and actual[1] == 409:
        damaged = Store(); mutate(damaged)
        assert outcome(tone.resolve_published_passage, damaged, pin, 'chunk_0099') == actual
assert len(cases) >= 80, len(cases)
print('immutable direct parity cases:', len(cases))
''')

    def test_exact_resources_and_no_new_lifecycle_or_output_cap(self):
        self.probe(FIXTURES + self.oracle() + r'''
for rows in ([chunk(text='é'*3000)], [chunk(i, 'é'*3000) for i in range(4000)]):
    left, right = Store(rows), Store(rows)
    # Existing schema has no 64 KiB state cap. Existing per-publication bounds
    # allow 12 million code points, including over 4 MiB of detached UTF-8 text.
    left.state.evidence = right.state.evidence = {'last_error': 'x'*65537}
    result = core.admit_complete_publication(right, 'AAPL', ACC, 0)
    assert len(result.chunks) == len(rows)
    assert outcome(oracle.resolve_published_passage, left) == outcome(tone.resolve_published_passage, Store(rows))
    assert sum(len(c.text.encode()) for c in result.chunks) == len(rows)*6000
for damage in ('manifest', 'inventory', 'text'):
    store = Store()
    if damage == 'manifest': store.publications[0].chunk_count = 4001
    elif damage == 'inventory': store.inventory = inventory([chunk(i) for i in range(4001)])
    else: store.inventory[1].text_length = 3001
    try: core.admit_complete_publication(store, 'AAPL', ACC, 0)
    except HTTPException as exc: assert exc.headers['X-FinLens-Error-Code'] == 'SEARCH_SCOPE_TOO_LARGE'
    else: raise AssertionError('over-bound accepted')
    assert 'bodies' not in store.events
''')

    def test_cancellation_and_cleanup_errors_propagate(self):
        self.probe(FIXTURES + r'''
import asyncio
for method in ('scalar', 'connection', 'get', 'execute', 'scalars'):
    for error in (asyncio.CancelledError, KeyboardInterrupt, RuntimeError):
        store = Store()
        def fail(*args, **kwargs): raise error('synthetic cancellation/query failure')
        setattr(store, method, fail)
        try: core.admit_complete_publication(store, 'AAPL', ACC, 0)
        except error: pass
        else: raise AssertionError('failure swallowed')
for target in ('validate_chunks', 'chunk_digest'):
    original = getattr(core, target)
    for error in (asyncio.CancelledError, KeyboardInterrupt, RuntimeError):
        def fail(*args): raise error('synthetic validation cancellation')
        setattr(core, target, fail)
        try: core.admit_complete_publication(Store(), 'AAPL', ACC, 0)
        except error: pass
        else: raise AssertionError('validation failure swallowed')
    setattr(core, target, original)
class ClosingStore(Store):
    def get_bind(self): return NS(dialect=NS(name='synthetic'))
    def close(self): raise RuntimeError('cleanup failure')
    def invalidate(self): self.events.append('invalidated')
store = ClosingStore()
try:
    with fresh.read_session(lambda: store) as session:
        core.admit_complete_publication(session, 'AAPL', ACC, 0)
except RuntimeError as exc: assert str(exc) == 'cleanup failure'
else: raise AssertionError('cleanup failure swallowed')
assert store.events[-1] == 'invalidated'
''')

    def test_digest_bypass_mutant_fails_integrity_assertion(self):
        source = (ROOT / 'app/publication_admission.py').read_text(encoding='utf-8')
        mutant = source.replace('if digest != publication.content_digest:', 'if False:')
        self.assertNotEqual(source, mutant)
        self.probe(FIXTURES + f'\nexec(compile({mutant!r}, "<digest-mutant>", "exec"), core.__dict__)\n' + r'''
core.schema_ready = lambda _: True
store = Store(); store.chunks[1].text = 'alter passage'
try: core.admit_complete_publication(store, 'AAPL', ACC, 0)
except HTTPException: pass
else: raise AssertionError('digest corruption was accepted')
''', failure='digest corruption was accepted')

    def test_no_detachment_or_selection_before_entire_admission(self):
        self.probe(FIXTURES + r'''
original = core.PublicationChunk
constructed = []
def record(*args):
    constructed.append(args)
    return original(*args)
core.PublicationChunk = record
for damage in ('last-embedding', 'last-text', 'digest', 'reordered'):
    store = Store()
    if damage == 'last-embedding': store.chunks[-1].embedding = None
    elif damage == 'last-text': store.chunks[-1].text = 'alter passage'
    elif damage == 'digest': store.publications[0].content_digest = '0'*64
    else: store.body_override = list(reversed(store.chunks))
    result = outcome(tone.resolve_published_passage, store, selected='chunk_0099')
    assert result[0:2] == ('error', 409), result
    assert result[-1]['X-FinLens-Error-Code'] == 'EVIDENCE_PENDING'
    assert constructed == [], 'partially verified evidence escaped'
''')

    def test_source_gate_order_and_unmodified_public_schema(self):
        baseline = ast.parse(self.source)
        current = ast.parse((ROOT / 'app/filing_tone_service.py').read_text(encoding='utf-8'))
        core = ast.parse((ROOT / 'app/publication_admission.py').read_text(encoding='utf-8'))
        def node(tree, name): return next(n for n in tree.body if getattr(n, 'name', None) == name)
        for original in baseline.body:
            name = getattr(original, 'name', None)
            if name and name not in ('resolve_published_passage', '_version_changed'):
                self.assertEqual(ast.dump(original), ast.dump(node(current, name)), name)
        old = node(baseline, 'resolve_published_passage').body
        start = next(i for i, n in enumerate(old) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'company')
        end = next(i for i, n in enumerate(old) if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'selected')
        class TonePath(ast.NodeTransformer):
            # Only erase the fixed Reader branches; the immutable oracle and
            # every legacy gate remain unchanged. No generic AST relaxation.
            def visit_If(self, item):
                if isinstance(item.test, ast.Name) and item.test.id == 'reader':
                    return [self.visit(n) for n in item.orelse
                            if not (isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'evidence')]
                return self.generic_visit(item)
            def visit_IfExp(self, item):
                if isinstance(item.test, ast.Name) and item.test.id == 'reader':
                    return self.visit(item.orelse)
                return self.generic_visit(item)
            def visit_Name(self, item):
                if item.id == 'evidence':
                    return ast.Attribute(value=ast.Name(id='state', ctx=ast.Load()),
                                         attr='evidence', ctx=item.ctx)
                return item
        new = TonePath().visit(node(core, '_admit_publication')).body
        self.assertEqual([ast.dump(n) for n in old[start:end]], [ast.dump(n) for n in new[2:-1]])
        wrapper = node(core, 'admit_complete_publication')
        self.assertEqual(ast.unparse(wrapper.body[-1]),
                         'return _admit_publication(session, ticker, accession, expected, reader=False)')
        self.assertEqual(ast.dump(node(baseline, '_version_changed')), ast.dump(node(core, '_version_changed')))


if __name__ == '__main__':
    unittest.main()
