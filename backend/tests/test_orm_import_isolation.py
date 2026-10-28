"""02B.1 offline probes: python -I -S -B tests/test_orm_import_isolation.py.

Only stdlib runs in the parent. Each child installs guards before app imports;
legacy compatibility substitutes a recording object for engine construction.
"""
import ast
from itertools import permutations
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASELINE = '0287e7687a9cdb87eefb1cbfe27afdf9e4475b65'
GUARDS = r'''
import builtins, importlib, importlib.abc, io, os, socket, sys
from pathlib import Path
from types import SimpleNamespace

attempts = []
def forbidden(*args, **kwargs):
    attempts.append('bootstrap')
    raise AssertionError('forbidden bootstrap operation')

def protected_open(original):
    def guarded(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)):
            name = os.fsdecode(os.fspath(path)).replace('\\', '/').rsplit('/', 1)[-1]
            if name == '.env' or name.startswith('.env.'):
                forbidden()
        return original(path, *args, **kwargs)
    return guarded
builtins.open = protected_open(builtins.open)
io.open = protected_open(io.open)
os.open = protected_open(os.open)
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden

allowed_app = {'app.models', 'app.orm_base'}
class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if ((fullname.startswith('app.') and fullname not in allowed_app)
                or fullname.split('.')[0] in {'openai', 'torch', 'transformers',
                    'sentence_transformers', 'huggingface_hub', 'tensorflow'}):
            attempts.append(fullname)
            raise AssertionError('forbidden import: ' + fullname)
sys.meta_path.insert(0, ImportGuard())

import sqlalchemy
import sqlalchemy.engine.create
import sqlalchemy.orm
import psycopg
import sqlite3
import sqlite3.dbapi2
import dotenv
sqlalchemy.create_engine = forbidden
sqlalchemy.engine.create_engine = forbidden
sqlalchemy.engine.create.create_engine = forbidden
sqlalchemy.engine_from_config = forbidden
psycopg.connect = forbidden
psycopg.Connection.connect = classmethod(forbidden)
psycopg.AsyncConnection.connect = classmethod(forbidden)
sqlite3.connect = forbidden
sqlite3.dbapi2.connect = forbidden
dotenv.load_dotenv = forbidden
dotenv.find_dotenv = forbidden

url_allowed = False
original_getitem = type(os.environ).__getitem__
def guarded_getitem(environ, key):
    if not url_allowed and key == 'DATABASE_URL':
        attempts.append('DATABASE_URL')
        raise AssertionError('forbidden DATABASE_URL resolution')
    return original_getitem(environ, key)
type(os.environ).__getitem__ = guarded_getitem
'''

LEGACY = r'''
allowed_app.update({'app.database', 'app.config', 'app.release_policy'})
url_allowed = True
os.environ['DATABASE_URL'] = 'postgresql+psycopg://fixture:private@127.0.0.1/fixture'
dotenv_calls, engine_calls = [], []
def synthetic_dotenv(path, *, override=False):
    dotenv_calls.append((path, override))
    return False
dotenv.load_dotenv = synthetic_dotenv
fake_engine = SimpleNamespace(connect=forbidden)
def recording_engine(*args, **kwargs):
    engine_calls.append((args, kwargs))
    return fake_engine
sqlalchemy.create_engine = recording_engine
'''

IDENTITY = r'''
from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers
from app import models, orm_base, database
from app.database import Base as compatibility_base
classes = {models.Company, models.FinancialFact, models.FilingChunk,
           models.CompanyRefreshState, models.RefreshAttempt, models.FilingPublication}
assert compatibility_base is database.Base is models.Base is orm_base.Base
assert database.Base.metadata is orm_base.Base.metadata
assert set(orm_base.Base.metadata.tables) == {'companies', 'financial_facts',
    'filing_chunks', 'company_refresh_state', 'refresh_attempts', 'filing_publications'}
configure_mappers()
assert {m.class_ for m in orm_base.Base.registry.mappers} == classes
for cls in classes:
    assert cls.metadata is orm_base.Base.metadata
    assert cls.registry is orm_base.Base.registry
    assert inspect(cls) is cls.__mapper__
    assert inspect(cls).local_table is orm_base.Base.metadata.tables[cls.__tablename__]
assert importlib.import_module('app.models') is models
assert importlib.import_module('app.database').Base is compatibility_base
assert database.engine is fake_engine
assert engine_calls == [((os.environ['DATABASE_URL'],), {'pool_pre_ping': True})]
assert database.SessionLocal.kw['bind'] is fake_engine
assert database.SessionLocal.kw['autoflush'] is False
assert database.SessionLocal.kw['autocommit'] is False
assert database._http_factory is database._insights_factory is None
assert len(dotenv_calls) == 2 and all(override is False for _, override in dotenv_calls)
assert all(path == Path(database.__file__).resolve().parents[1] / '.env'
           for path, _ in dotenv_calls)
'''


def committed(path):
    return subprocess.run(['git', 'show', BASELINE + ':' + path], cwd=ROOT.parent,
                          capture_output=True, text=True, check=True).stdout


class OrmImportIsolationTests(unittest.TestCase):
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

    def test_inert_imports_without_configuration(self):
        for target in ('app.orm_base', 'app.models'):
            for profile in (None, 'development', 'sec_readonly', 'sec_reader', 'unknown'):
                with self.subTest(target=target, profile=profile):
                    self.probe(f"""
                        importlib.import_module({target!r})
                        assert 'app.database' not in sys.modules
                        assert 'app.config' not in sys.modules
                        assert not (set(sys.modules) & {{'app.main', 'app.sec_client',
                            'app.embedding_service', 'app.refresh_service', 'app.answer_service'}})
                    """, profile=profile)

    def test_forbidden_operations_are_raising_sentinels(self):
        cases = [
            ("import app.database", 'forbidden import: app.database'),
            ("import app.config", 'forbidden import: app.config'),
            ("import app.sec_client", 'forbidden import: app.sec_client'),
            ("import app.embedding_service", 'forbidden import: app.embedding_service'),
            ("import app.refresh_service", 'forbidden import: app.refresh_service'),
            ("import openai", 'forbidden import: openai'),
            ("sqlalchemy.create_engine('sqlite://')", 'forbidden bootstrap operation'),
            ("psycopg.connect('')", 'forbidden bootstrap operation'),
            ("dotenv.load_dotenv()", 'forbidden bootstrap operation'),
            ("Path('/synthetic/.env').read_text()", 'forbidden bootstrap operation'),
            ("os.getenv('DATABASE_URL')", 'forbidden DATABASE_URL resolution'),
        ]
        for code, failure in cases:
            with self.subTest(code=code):
                self.probe(code, failure=failure)

    def test_old_models_import_is_rejected_by_the_guard(self):
        old = committed('backend/app/models.py')
        self.probe(f"exec(compile({old!r}, '<old-models-import>', 'exec'))",
                   failure='forbidden import: app.database')

    def test_import_order_and_legacy_profile_compatibility(self):
        for profile in ('development', 'sec_readonly'):
            for order in permutations(('app.orm_base', 'app.models', 'app.database')):
                with self.subTest(profile=profile, order=order):
                    self.probe(LEGACY + f"\nfor name in {order!r}: importlib.import_module(name)\n"
                               + IDENTITY, profile=profile)

    def test_database_bounds_and_missing_url_behavior_are_preserved(self):
        for profile, bounds in (('development', (5, 5, 30000, 5000, 5)),
                                ('sec_readonly', (3, 2, 10000, 2000, 0))):
            with self.subTest(profile=profile):
                self.probe(LEGACY + f'''
from app import database, config
b = config.server_profile().http_database_bounds
assert (b.connect_timeout, b.pool_timeout, b.statement_timeout_ms,
        b.lock_timeout_ms, b.max_overflow) == {bounds!r}
_, options = database.http_engine_options(os.environ['DATABASE_URL'], config.server_profile(), {{}})
assert options['connect_args']['options'] == b.startup_options
assert options['pool_size'] == 5 and options['max_overflow'] == b.max_overflow
assert options['pool_timeout'] == b.pool_timeout and options['pool_pre_ping'] is False
os.environ.pop('DATABASE_URL')
del sys.modules['app.database']
try:
    importlib.import_module('app.database')
except RuntimeError as exc:
    assert str(exc).startswith('Set DATABASE_URL privately')
else:
    raise AssertionError('missing operational URL accepted')
assert len(engine_calls) == 1
''', profile=profile)

    def test_disabled_reader_remains_independent_and_diagnostic_only(self):
        self.probe('''
allowed_app.update({'app.config', 'app.release_policy', 'app.sec_reader'})
from app import sec_reader
from app.release_policy import READER_ROUTES
import json
assert {(method, route.path) for route in sec_reader.app.routes
        for method in route.methods} == READER_ROUTES == {
            ('GET', '/healthz'), ('GET', '/capabilities')}
assert json.loads(sec_reader.capabilities().body) == {
    'research_mode': False, 'ai_analysis_configured': False,
    'ai_analysis_enabled': False, 'server_profile': 'sec_reader'}
assert not (set(sys.modules) & {'app.models', 'app.orm_base', 'app.database'})
try:
    sec_reader.server_profile().http_database_bounds
except ValueError:
    pass
else:
    raise AssertionError('reader database bounds admitted')
''', profile='sec_reader')

    def test_source_changes_are_only_base_ownership_and_imports(self):
        original = ast.parse(committed('backend/app/models.py'))
        current = ast.parse((ROOT / 'app' / 'models.py').read_text())
        imports = [node for node in original.body if isinstance(node, ast.ImportFrom)
                   and node.module == 'app.database']
        self.assertEqual(len(imports), 1)
        imports[0].module = 'app.orm_base'
        self.assertEqual(ast.dump(original), ast.dump(current))

        original = ast.parse(committed('backend/app/database.py'))
        base = next(node for node in original.body
                    if isinstance(node, ast.ClassDef) and node.name == 'Base')
        original.body.remove(base)
        orm = next(node for node in original.body if isinstance(node, ast.ImportFrom)
                   and node.module == 'sqlalchemy.orm')
        orm.names = [name for name in orm.names if name.name != 'DeclarativeBase']
        original.body.insert(0, ast.ImportFrom(module='app.orm_base',
                                             names=[ast.alias(name='Base')], level=0))
        current = ast.parse((ROOT / 'app' / 'database.py').read_text())
        self.assertEqual(ast.dump(original), ast.dump(current))

    def test_committed_model_metadata_and_mapping_parity_in_memory(self):
        source = committed('backend/app/models.py')
        self.probe(LEGACY + IDENTITY + f'\nreference_source = {source!r}\n' + r'''
import ast, types
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.orm import DeclarativeBase

# Independent test-only reference registry; never installed in application modules.
class ReferenceBase(DeclarativeBase):
    pass
reference_base = types.ModuleType('orm_reference_base')
reference_base.Base = ReferenceBase
sys.modules[reference_base.__name__] = reference_base
reference = types.ModuleType('orm_reference_models')
sys.modules[reference.__name__] = reference
tree = ast.parse(reference_source)
for node in tree.body:
    if isinstance(node, ast.ImportFrom) and node.module == 'app.database':
        node.module = reference_base.__name__
exec(compile(tree, '<committed-model-reference>', 'exec'), reference.__dict__)
configure_mappers()

def signature(metadata):
    dialect = postgresql.dialect()
    return {name: (
        str(CreateTable(table).compile(dialect=dialect)),
        sorted(str(CreateIndex(index).compile(dialect=dialect)) for index in table.indexes),
        [(c.name, c.autoincrement, None if c.default is None else
          (c.default.is_callable, getattr(c.default.arg, '__name__', c.default.arg)))
         for c in table.columns],
    ) for name, table in metadata.tables.items()}
assert signature(ReferenceBase.metadata) == signature(orm_base.Base.metadata)
for cls in classes:
    prior = getattr(reference, cls.__name__)
    assert list(inspect(cls).attrs.keys()) == list(inspect(prior).attrs.keys())
    assert [c.name for c in inspect(cls).primary_key] == [c.name for c in inspect(prior).primary_key]
assert {m.class_ for m in orm_base.Base.registry.mappers} == classes
''', profile='development')


if __name__ == '__main__':
    unittest.main(verbosity=2)
