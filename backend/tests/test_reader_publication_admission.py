"""Strict entry offline acceptance; no database, services or application wiring.

Invoke: .venv/Scripts/python.exe -I -S -B tests/test_reader_publication_admission.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_publication_admission as legacy
import unittest


STRICT = legacy.FIXTURES + r'''
import asyncio, inspect, json
from contextlib import nullcontext
from app import reader_resource_policy as policy

class ReaderStore(Store):
    # Synthetic row stores have no ORM unit of work. The real Session probe
    # below exercises SQLAlchemy's actual implicit-autoflush machinery.
    @property
    def no_autoflush(self):
        return nullcontext()

    def __init__(self, chunks=None, raw='{}'):
        super().__init__(chunks)
        self.raw = raw
        self.transferred = []
        self.size_override = None
    scalar = get = scalars = forbidden
    def execute(self, stmt):
        self.record(stmt)
        sql = self.statements[-1][0]
        keys = tuple(c.key for c in stmt.selected_columns)
        assert 'facts' not in sql and 'cleaned_text' not in sql
        assert all(d.get('expr') is not d.get('entity') for d in stmt.column_descriptions)
        if keys == ('ticker', 'cik', 'name'):
            self.events.append('company')
            return [] if self.company is None else [NS(ticker=self.company.ticker,
                cik=self.company.cik, name=self.company.name)]
        if 'evidence_json' in keys:
            self.events.append('state')
            if self.state is None: return []
            # Model CASE evaluation against the actual compiled statement.
            # A removed guard really materializes the oversized original here;
            # mutation checks assert this transfer independently of rejection.
            guarded = 'CASE WHEN' in sql
            assert sql.count('convert_to(CAST(company_refresh_state.evidence AS TEXT)') == 2
            assert list(self.statements[-1][1].values()).count('UTF8') == 1
            size = len(self.raw.encode('utf-8'))
            payload = self.raw if not guarded or size <= 131072 else None
            if payload is not None: self.transferred.append(payload)
            return [NS(company_cik=self.state.company_cik,
                data_version=self.state.data_version, evidence_version=self.state.evidence_version,
                evidence_bytes=size if self.size_override is None else self.size_override,
                evidence_json=payload)]
        if keys == core.PUBLICATION_FIELDS:
            self.events.append('manifest')
            return self.publications[:2]
        assert keys[:len(fresh.CHUNK_IDENTITY_FIELDS)] == fresh.CHUNK_IDENTITY_FIELDS
        assert self.statements[-1][1]['param_1'] == 4001
        if keys[-1] == 'text_length':
            self.events.append('inventory')
            assert 'filing_chunks.text AS' not in sql and 'embedding' not in sql
            return self.inventory[:4001]
        self.events.append('bodies')
        assert keys[-2:] == ('text', 'embedding')
        assert 'length(filing_chunks.text) <=' in sql
        rows = self.chunks if self.body_override is None else self.body_override
        return [NS(**{k: getattr(row, k) for k in keys}) for row in rows[:4001]]

def admit(store):
    return core.admit_reader_publication(store, 'aapl', ACC, 0)

def error(store, code='EVIDENCE_PENDING'):
    constructed = []
    original = core.PublicationChunk
    def record(*args):
        constructed.append(args)
        return original(*args)
    core.PublicationChunk = record
    try:
        try: admit(store)
        except HTTPException as exc:
            assert exc.status_code == 409 and exc.headers['X-FinLens-Error-Code'] == code, (exc.detail, exc.headers)
        else: raise AssertionError('strict corruption accepted')
        assert not constructed, 'partial detachment'
    finally:
        core.PublicationChunk = original
'''


REAL_SESSION = STRICT + r'''
from sqlalchemy.orm import Session

class AutoflushAttempt(AssertionError):
    pass

class ProjectedRead(Exception):
    def __init__(self, statement):
        self.statement = statement

def unbound_reader(autoflush):
    session, store = Session(autoflush=autoflush), ReaderStore()
    pending = Company(ticker='TEST', cik='0000000001', name='Pending caller state')
    session.add(pending)
    assert session.bind is None and tuple(session.new) == (pending,)
    flushes, reads = [], []
    def flush(*args, **kwargs):
        flushes.append(True)
        raise AutoflushAttempt('implicit Reader autoflush reached flush sentinel')
    session.flush = flush
    # SQLAlchemy's real Session.execute/_execute_internal runs its real ORM
    # pre-session/autoflush gate BEFORE get_bind. Stop at that boundary and
    # replay projected rows; do not short-circuit with do_orm_execute events.
    def bind(*args, **kwargs):
        raise ProjectedRead(kwargs['clause'])
    session.get_bind = bind
    execute = session.execute
    def projected_execute(statement, *args, **kwargs):
        try:
            return execute(statement, *args, **kwargs)
        except ProjectedRead as read:
            reads.append(session.autoflush)
            return store.execute(read.statement)
    session.execute = projected_execute
    session.connection = store.connection  # synthetic schema-capability probe
    session._connection_for_bind = forbidden
    session.commit = session.rollback = session.close = session.invalidate = forbidden
    return session, store, pending, flushes, reads

def preserved(session, pending, initial, flushes):
    assert session.autoflush is initial, 'autoflush configuration not restored'
    assert session.bind is None and tuple(session.new) == (pending,)
    assert not flushes, 'unexpected implicit or explicit flush'
'''


class ReaderPublicationAdmissionTests(unittest.TestCase):
    probe = legacy.PublicationAdmissionTests.probe

    def test_real_unbound_session_no_autoflush_and_restoration(self):
        self.probe(REAL_SESSION + r'''
for initial in (True, False):
    session,store,pending,flushes,reads = unbound_reader(initial)
    result = admit(session)
    assert result.publication.content_digest == fresh.chunk_digest(store.chunks)
    assert store.events == ['company','connection','state','manifest','inventory','bodies']
    assert reads == [False]*5, 'Reader context did not cover every SELECT'
    preserved(session,pending,initial,flushes)
    for step in ('company','state','manifest','inventory','bodies'):
        for failure in (RuntimeError('ordinary failure'), asyncio.CancelledError(), KeyboardInterrupt()):
            session,store,pending,flushes,reads = unbound_reader(initial)
            execute = store.execute
            def fail(statement):
                result = execute(statement)
                if store.events[-1] == step:
                    raise failure
                return result
            store.execute = fail
            try: admit(session)
            except type(failure) as actual: assert actual is failure
            else: raise AssertionError('Reader failure swallowed')
            assert reads and all(value is False for value in reads)
            preserved(session,pending,initial,flushes)
    for raw,code in (('{"unknown":true}','EVIDENCE_PENDING'),
                     ('{"last_error":"'+'x'*131073+'"}','SEARCH_SCOPE_TOO_LARGE')):
        session,store,pending,flushes,reads = unbound_reader(initial)
        store.raw = raw
        error(session,code)
        preserved(session,pending,initial,flushes)
# An enclosing caller-owned no_autoflush context must stay disabled until its
# own exit, then restore the caller's original True configuration.
session,store,pending,flushes,reads = unbound_reader(True)
with session.no_autoflush:
    admit(session)
    preserved(session,pending,False,flushes)
preserved(session,pending,True,flushes)
# Tone's entry must still reach its established implicit autoflush gate.
session,store,pending,flushes,reads = unbound_reader(True)
try: core.admit_complete_publication(session,'AAPL',ACC,0)
except AutoflushAttempt: pass
else: raise AssertionError('Tone autoflush behavior changed')
assert flushes == [True] and not reads and session.autoflush is True
''')

    def test_no_autoflush_removal_hits_real_flush_sentinel(self):
        source = (Path(__file__).resolve().parents[1] / 'app/publication_admission.py').read_text(encoding='utf-8')
        guarded = ('        with session.no_autoflush:\n'
                   '            return _admit_publication(session, ticker, accession, expected, reader=True)')
        self.assertEqual(source.count(guarded), 1)
        mutant = source.replace(guarded,
            '        return _admit_publication(session, ticker, accession, expected, reader=True)')
        self.probe(REAL_SESSION
                   + f'\nexec(compile({mutant!r}, "<no-autoflush-mutant>", "exec"), core.__dict__)\n'
                   + 'session,store,pending,flushes,reads = unbound_reader(True)\n'
                   + 'try: admit(session)\nexcept AutoflushAttempt:\n'
                   + '    assert flushes == [True] and not reads and session.autoflush is True\n'
                   + '    assert session.bind is None and tuple(session.new) == (pending,)\n    raise\n',
                   failure='AutoflushAttempt: implicit Reader autoflush reached flush sentinel')

    def test_fixed_entry_and_detached_output(self):
        self.probe(STRICT + r'''
assert tuple(inspect.signature(core.admit_reader_publication).parameters) == ('session','ticker','accession','expected')
for kw in ('reader', 'strict', 'policy', 'trusted_result', 'digest', 'fallback'):
    store = ReaderStore()
    try: core.admit_reader_publication(store, 'AAPL', ACC, 0, **{kw: False})
    except TypeError: pass
    else: raise AssertionError('public bypass accepted')
    assert not store.events
store = ReaderStore()
result = admit(store)
assert result.publication.content_digest == fresh.chunk_digest(store.chunks)
assert store.events == ['company','connection','state','manifest','inventory','bodies']
def detached(value):
    if is_dataclass(value):
        assert value.__dataclass_params__.frozen
        for f in fields(value): detached(getattr(value, f.name))
    elif type(value) is tuple:
        for member in value: detached(member)
    else: assert type(value) in (str, int, date), type(value)
detached(result)
store.chunks[-1].text = 'changed'; store.company.name = 'changed'
assert result.company_name == 'Apple' and result.chunks[-1].text == 'other passage'
for ticker, acc, pin in [('AAPL',ACC,v) for v in (True,-1,'0',2**53)] + [('bad ticker',ACC,0),('AAPL','bad',0)]:
    store = ReaderStore()
    try: core.admit_reader_publication(store,ticker,acc,pin)
    except HTTPException as exc: assert exc.status_code == 422
    else: raise AssertionError('invalid selector accepted')
    assert not store.events
store = ReaderStore(); store.state.data_version = 8; store.state.evidence_version = 2
assert core.admit_reader_publication(store,'AAPL',ACC,8).publication.data_version == 0
import numpy as np
store=ReaderStore(); store.chunks[-1].embedding=np.array(VECTOR,dtype=np.float32)
assert admit(store).chunks
store=ReaderStore(); store.company.name='é'*200
store.publications[0].filename='f'*251+'.htm'
for row in store.chunks: row.filename=store.publications[0].filename
store.inventory=inventory(store.chunks)
assert admit(store).company_name == 'é'*200
''')

    def test_actual_entry_byte_guard_depth_sentinel_and_precedence(self):
        self.probe(STRICT + r'''
original = policy.json.loads
def no_parse(*args, **kw): raise AssertionError('parser invoked')
for raw in ('{"last_error":"'+'x'*131072+'"}', '{"pending_targets":[[]]}',
            '{"unknown":[{}]}', '{"bad":false, "x":[[', '{"last_error":"'+'é'*65536+'"}'):
    store = ReaderStore(raw=raw)
    policy.json.loads = no_parse
    error(store, 'SEARCH_SCOPE_TOO_LARGE')
    if len(raw.encode()) > 131072: assert not store.transferred
    assert 'manifest' not in store.events
policy.json.loads = original
for raw in ('{"x":[[[', '{"last_error":"'+'x'*131072+'"}'):
    store = ReaderStore(raw=raw); store.state.data_version = 1
    policy.json.loads = no_parse
    error(store, 'DATA_VERSION_CHANGED')
policy.json.loads = original
raw = '{ "last_error" : "' + 'x'*(131072-len('{ "last_error" : "" }')) + '" }'
assert len(raw.encode()) == 131072
assert admit(ReaderStore(raw=raw)).chunks
store = ReaderStore(raw=raw+' '); error(store, 'SEARCH_SCOPE_TOO_LARGE'); assert not store.transferred
store = ReaderStore(raw='{"last_error":"é"}'); store.size_override = len(store.raw)
error(store)
''')

    def test_lifecycle_structure_mixed_limits_and_parser_validation(self):
        self.probe(STRICT + r'''
for raw in ('[]', 'null', '"root"', '{', '{"status":"invented"}',
    '{"pending_targets":"x"}', '{"pending_targets":[1]}', '{"inventory_complete":1}',
    '{"last_error":{}}', '{"unknown":1}', '{"status":"current","status":"failed"}',
    '{"status":"current","sta\\u0074us":"failed"}', '{"last_error":'+'9'*10000+'}',
    '{"inventory_complete":NaN}', '{"pending_targets":["'+ACC+'"]}'):
    error(ReaderStore(raw=raw))
assert admit(ReaderStore(raw=json.dumps({'last_error':'escaped " {} [] \\ delimiters',
    'pending_targets':['other']*4096}, separators=(',',':')))).chunks
for value in ({'pending_targets':['']*4097}, {'unknown':False,'pending_targets':['']*4097},
              {'last_error':123,'pending_targets':['']*4097}):
    raw = json.dumps(value,separators=(',',':')); assert len(raw.encode()) < 131072
    error(ReaderStore(raw=raw), 'SEARCH_SCOPE_TOO_LARGE')
raw='{"pending_targets":[],"pending_targets":['+','.join('""' for _ in range(4097))+']}'
error(ReaderStore(raw=raw), 'SEARCH_SCOPE_TOO_LARGE')
# Unknown fields never construct Pydantic's potentially large validation errors.
original = core.StreamState
core.StreamState = NS(model_validate=forbidden)
error(ReaderStore(raw='{"unknown":false}'))
core.StreamState = original
''')

    def test_complete_integrity_and_no_fallback(self):
        self.probe(STRICT + r'''
mutations = [
 lambda s: setattr(s.chunks[-1],'text','alter passage'),
 lambda s: setattr(s.chunks[-1],'embedding',[1.0]*383),
 lambda s: setattr(s.chunks[-1],'embedding',[1.0]*385),
 lambda s: setattr(s.chunks[-1],'embedding',[float('nan')]*384),
 lambda s: setattr(s.chunks[-1],'embedding',[0.0]*384),
 lambda s: setattr(s.chunks[-1],'embedding',[1e100]*384),
 lambda s: setattr(s.chunks[-1],'sec_url','https://evil.invalid'),
 lambda s: setattr(s.publications[0],'content_digest','0'*64),
 lambda s: setattr(s.publications[0],'company_cik','0000000001'),
 lambda s: setattr(s,'inventory',s.inventory[:1]),
 lambda s: setattr(s,'inventory',list(reversed(s.inventory))),
 lambda s: setattr(s,'inventory',[s.inventory[0]]*2),
 lambda s: setattr(s,'body_override',s.chunks[:1]),
 lambda s: setattr(s,'body_override',list(reversed(s.chunks))),
 lambda s: setattr(s.chunks[-1],'id',True),
 lambda s: setattr(s.state,'company_cik','0000000001'),
 lambda s: setattr(s.state,'evidence_version',1),
]
for mutate in mutations:
    store=ReaderStore(); mutate(store); error(store)
for field,value in (('sec_url','https://evil.invalid/'), ('chunk_id','chunk_0099'),
                    ('company_cik','0000000001'),('chunk_index',3)):
    store=ReaderStore(); setattr(store.chunks[-1],field,value)
    store.inventory=inventory(store.chunks)  # reach canonical/ordered checks
    error(store)
import numpy as np
store=ReaderStore(); store.chunks[-1].embedding=np.array(1.0); error(store)
for field, value in [('text',None), ('start_char',True), ('filed','2026-07-31'),
                     ('embedding',['1']*384), ('embedding',[[1]]*384)]:
    store=ReaderStore(); setattr(store.chunks[-1],field,value); error(store)
for field, value in [('name','x'*201),('ticker','x'*11)]:
    store=ReaderStore(); setattr(store.company,field,value); error(store,'SEARCH_SCOPE_TOO_LARGE')
store=ReaderStore(); store.publications=[]; error(store)
core.admit_complete_publication = forbidden
store=ReaderStore(raw='{"last_error":"'+'x'*131073+'"}')
assert len(store.raw.encode()) > 131072
error(store,'SEARCH_SCOPE_TOO_LARGE')
''')

    def test_actual_entry_combined_maximum_and_over_limits(self):
        self.probe(STRICT + r'''
# Simultaneously attain 4000 chunks, 3000 code points/chunk, 12M code
# points, 48M UTF-8 bytes and 1,536,000 vector components.
rows=[chunk(i,'\U0001f4c8'*3000) for i in range(4000)]
result=admit(ReaderStore(rows))
assert len(result.chunks)==4000 and sum(len(c.text) for c in result.chunks)==12000000
assert sum(len(c.text.encode()) for c in result.chunks)==48000000
for damage in ('manifest','sentinel','text'):
    store=ReaderStore()
    if damage=='manifest': store.publications[0].chunk_count=4001
    elif damage=='sentinel': store.inventory=inventory([chunk(i) for i in range(4001)])
    else: store.inventory[-1].text_length=3001
    error(store,'SEARCH_SCOPE_TOO_LARGE'); assert 'bodies' not in store.events
store=ReaderStore(); store.chunks[-1].text='x'*3001
error(store,'SEARCH_SCOPE_TOO_LARGE')
# Aggregate bounds are partly implied by count*per-row bounds. Test independent
# arithmetic endpoints too; no production policy is lowered to manufacture cases.
for args in ((2000000,12000000,48000000,1536000),): policy.detached_budget(*args)
for args in ((2000001,0,0,0),(0,12000001,0,0),(0,0,48000001,0),
             (0,0,0,1536001),(2000000,0,48000001,0)):
    try: policy.detached_budget(*args)
    except policy.ResourceExcess: pass
    else: raise AssertionError('aggregate excess accepted')
# Repeated metadata occurrences must be counted, even identical objects.
seen=[]; original=policy.detached_budget
policy.detached_budget=lambda *args: seen.append(args)
admit(ReaderStore())
store=ReaderStore()
expected=sum(policy.logical_bytes(v) for v in (store.company.ticker,store.company.cik,
 store.company.name,0,0,*(getattr(store.publications[0],f) for f in core.PUBLICATION_FIELDS)))
expected+=sum(policy.logical_bytes(getattr(c,f)) for c in store.chunks for f in fresh.CHUNK_IDENTITY_FIELDS)
assert seen[-1][0] == expected and seen[-1][0] > seen[0][0] and seen[-1][3] == 768
policy.detached_budget=original
''')

    def test_driver_programming_and_cancellation_propagate(self):
        self.probe(STRICT + r'''
from sqlalchemy.exc import ProgrammingError, OperationalError
for step in ('company','state','manifest','inventory','bodies'):
    for exc in (RuntimeError('programming'), asyncio.CancelledError(), KeyboardInterrupt(),
                ProgrammingError('synthetic',{},Exception('driver')),
                OperationalError('synthetic',{},Exception('driver'))):
        store=ReaderStore(); original=store.execute
        def execute(stmt):
            result=original(stmt)
            if store.events[-1]==step: raise exc
            return result
        store.execute=execute
        try: admit(store)
        except type(exc) as actual: assert actual is exc
        else: raise AssertionError('query failure swallowed')
for target in ('validate_chunks','chunk_digest'):
    original=getattr(core,target)
    for exc in (RuntimeError('programming'), asyncio.CancelledError(), KeyboardInterrupt()):
        def fail(*args): raise exc
        setattr(core,target,fail)
        try: admit(ReaderStore())
        except type(exc) as actual: assert actual is exc
        else: raise AssertionError('integrity failure swallowed')
    setattr(core,target,original)
''')

    def test_actual_entry_non_text_budget_boundary(self):
        self.probe(STRICT + r'''
# Use scalar-width-valid metadata to reach the independent non-text boundary.
# Deliberately noncanonical URLs must still reach the integrity gate at exact
# budget; this is a resource-gate test, not a successful-publication fixture.
store=ReaderStore([chunk(i) for i in range(1200)])
for c in store.chunks: c.sec_url=''
base=sum(policy.logical_bytes(v) for v in (store.company.ticker,store.company.cik,
 store.company.name,0,0,*(getattr(store.publications[0],f) for f in core.PUBLICATION_FIELDS)))
base+=sum(policy.logical_bytes(getattr(c,f)) for c in store.chunks for f in fresh.CHUNK_IDENTITY_FIELDS)
remaining=2000000-base
assert 0<remaining<1200*2000
for c in store.chunks:
    size=min(remaining,2000); units,remainder=divmod(size,4)
    c.sec_url='\U0001f4c8'*units+('', 'x','é','€')[remainder]
    remaining-=size
assert remaining==0
store.inventory=inventory(store.chunks)
called=[]
def integrity_gate(chunks):
    called.append(True)
    raise RuntimeError('exact metadata budget reached integrity')
core.validate_chunks=integrity_gate
try: admit(store)
except RuntimeError as exc: assert str(exc)=='exact metadata budget reached integrity'
else: raise AssertionError('noncanonical fixture returned publication')
assert called==[True]
called.clear()
next(c for c in store.chunks if len(c.sec_url)<500).sec_url+='x'
store.inventory=inventory(store.chunks)
error(store,'SEARCH_SCOPE_TOO_LARGE')
assert not called, 'over-budget reached integrity'
''')

    def test_mutation_controls_fail_for_intended_reasons(self):
        source=(Path(__file__).resolve().parents[1]/'app/publication_admission.py').read_text(encoding='utf-8')
        cases = [
            (source.replace('if digest != publication.content_digest:', 'if False:'),
             "store=ReaderStore(); store.chunks[-1].text='alter passage'; error(store)",
             'strict corruption accepted'),
            (source.replace('reader=True)', 'reader=False)'),
             "ReaderStore.scalar=Store.scalar; ReaderStore.get=Store.get; ReaderStore.scalars=Store.scalars; "
             "store=ReaderStore(raw=json.dumps({'last_error':'x'*131073})); "
             "store.state.evidence=json.loads(store.raw); "
             "assert len(store.raw.encode())>131072; error(store,'SEARCH_SCOPE_TOO_LARGE')",
             'strict corruption accepted'),
            (source.replace("case((size <= _reader.LIFECYCLE_BYTES, raw), else_=None)",
                            "case((size <= _reader.LIFECYCLE_BYTES, raw), else_=raw)"),
             "store=ReaderStore(raw=json.dumps({'last_error':'x'*131073})); "
             "error(store,'SEARCH_SCOPE_TOO_LARGE'); assert not store.transferred, 'oversized payload transferred'",
             'oversized payload transferred'),
        ]
        # Guard mutation models ELSE raw as unguarded materialization.
        fixture=STRICT.replace("guarded = 'CASE WHEN' in sql", "guarded = 'CASE WHEN' in sql and 'ELSE CAST' not in sql")
        for mutant, control, reason in cases:
            self.assertNotEqual(source,mutant)
            self.probe(fixture+f'\nexec(compile({mutant!r},"<strict-mutant>","exec"),core.__dict__)\n'
                       +'core.schema_ready=lambda _:True\n'+control, failure=reason)

    def test_policy_and_canonical_mutants_are_detected(self):
        policy_source=(Path(__file__).resolve().parents[1]/'app/reader_resource_policy.py').read_text(encoding='utf-8')
        mutant=policy_source.replace('if depth > JSON_DEPTH:', 'if False:')
        self.assertNotEqual(policy_source,mutant)
        self.probe(STRICT+f'\nexec(compile({mutant!r},"<depth-mutant>","exec"),policy.__dict__)\n'+r'''
def no_parse(*args,**kw): raise AssertionError('deep JSON reached parser')
policy.json.loads=no_parse
error(ReaderStore(raw='{"pending_targets":[[]]}'),'SEARCH_SCOPE_TOO_LARGE')
''', failure='deep JSON reached parser')
        self.probe(STRICT+r'''
original=core.validate_chunks
def bypass_canonical(chunks):
    saved=[c.sec_url for c in chunks]
    try:
        for c in chunks: c.sec_url=build_filing_url(c.company_cik,c.accession_number)
        original(chunks)
    finally:
        for c,value in zip(chunks,saved): c.sec_url=value
core.validate_chunks=bypass_canonical
store=ReaderStore(); store.chunks[-1].sec_url='https://evil.invalid/'
store.inventory=inventory(store.chunks)
error(store)
''', failure='strict corruption accepted')


if __name__ == '__main__':
    unittest.main()
