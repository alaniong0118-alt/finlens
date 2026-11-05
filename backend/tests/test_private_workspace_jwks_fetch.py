"""Synthetic HTTPX + existing RSA/verifier fixtures, never network or database."""
import asyncio
import base64
from dataclasses import FrozenInstanceError, replace
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import sys
import time
import traceback
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = Path('D:/Projects/finlens-foundation/backend')
if (ROOT / 'backend/tests/test_private_workspace_http.py').is_file():
    PRIMARY = ROOT / 'backend'
sys.path[:0] = [str(PRIMARY / '.venv/Lib/site-packages'), str(PRIMARY), str(PRIMARY / 'tests')]

# The maintained fixture creates only its local asyncio wakeup machinery before
# its strict DNS/socket/subprocess/.env/database guard. RSA keys remain in memory.
from test_private_workspace_http import LOOP, CryptoFixtures
from app import account_auth as auth


def no_writes(event, args):
    if event == 'open' and ((args[1] and any(c in args[1] for c in 'wax+'))
                           or args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
        raise AssertionError('offline_write_forbidden')


sys.addaudithook(no_writes)
spec = importlib.util.spec_from_file_location('jwks_fetch_candidate', ROOT / 'backend/app/private_workspace_jwks_fetch.py')
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)
import httpx

CANARY = 'SYNTHETIC-PRIVATE-CANARY-123'


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks=(b'{"keys":[]}',), *, delay=0, failure=None, close_error=False):
        self.chunks, self.delay, self.failure, self.close_error = chunks, delay, failure, close_error
        self.reads, self.closed, self.cancelled = 0, False, False

    async def __aiter__(self):
        try:
            for part in self.chunks:
                self.reads += 1
                if self.delay:
                    await asyncio.sleep(self.delay)
                if self.failure:
                    raise self.failure
                yield part
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def aclose(self):
        self.closed = True
        if self.close_error:
            raise RuntimeError(CANARY)


class FetchTests(CryptoFixtures):
    def run_async(self, awaitable):
        return LOOP.run_until_complete(awaitable)

    def target(self, transport, **changes):
        args = dict(policy=self.policy, _test_transport=transport,
                    clock=lambda: self.clock.wall, monotonic=lambda: self.clock.mono)
        return adapter.HttpsJwksSnapshotFetcher(**(args | changes))

    async def exchange(self, stream=None, *, headers=None, status=200, error=None, hook=None,
                       revision=2, lifetime=60):
        stream = Stream() if stream is None else stream
        calls, clients = [], []
        real_client = httpx.AsyncClient
        async def handler(request):
            calls.append(request)
            if hook:
                hook()
            if error:
                raise error
            return httpx.Response(status, headers={'content-type': 'application/jwk-set+json'} if headers is None else headers,
                                  stream=stream)
        def client(**kwargs):
            result = real_client(**kwargs)
            clients.append(result)
            return result
        try:
            with patch.object(adapter.httpx, 'AsyncClient', side_effect=client):
                result = await self.target(httpx.MockTransport(handler))(revision=revision, lifetime_seconds=lifetime)
            return result, calls, stream
        finally:
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(clients), 1)
            self.assertTrue(clients[0].is_closed)
            if error is None:
                self.assertTrue(stream.closed)

    def denied(self, awaitable, code='AUTH_UNAVAILABLE'):
        try:
            self.run_async(awaitable)
        except auth.AuthFailure as error:
            self.assertEqual((error.code, str(error)), (code, code))
            self.assertNotIn(CANARY, ''.join(traceback.format_exception(error)))
        else:
            self.fail('expected sanitized refusal')

    def test_dormant_import_and_constructor_do_not_activate_client_or_tls(self):
        other = importlib.util.spec_from_file_location('jwks_import_probe', Path(adapter.__file__))
        module = importlib.util.module_from_spec(other)
        sys.modules[other.name] = module
        try:
            with patch.object(httpx, 'AsyncClient', side_effect=AssertionError('activation')), \
                    patch.object(httpx, 'AsyncHTTPTransport', side_effect=AssertionError('activation')), \
                    patch.object(adapter.ssl.SSLContext, 'load_verify_locations', side_effect=AssertionError('activation')):
                other.loader.exec_module(module)
                module.HttpsJwksSnapshotFetcher(self.policy)
        finally:
            sys.modules.pop(other.name, None)

    def test_explicit_policy_canonical_endpoint_and_immutability(self):
        with self.assertRaises(TypeError): adapter.HttpsJwksSnapshotFetcher()
        for value in (None, {}, self.policy.jwks_uri):
            with self.assertRaises(auth.AuthFailure): adapter.HttpsJwksSnapshotFetcher(value)
        for uri in ('http://offline.invalid/keys', 'https://user:pass@offline.invalid/keys',
                    'https://OFFLINE.invalid/keys', 'https://offline.invalid:443/keys',
                    'https://offline.invalid:0/keys', 'https://offline.invalid:99999/keys',
                    'https://offline.invalid', 'https://offline.invalid/keys?', 'https://offline.invalid/keys#',
                    'https://offline.invalid/%6beys', 'https://offline.invalid/a/../keys',
                    'https://offline.invalid\\keys', 'https://offline.invalid./keys',
                    'https://.invalid/keys', 'https://-invalid/keys', 'https://offline.invalid/keys\n',
                    'https://離線.invalid/keys', 'https://offline.invalid/keys\u200b'):
            with self.subTest(uri=uri), self.assertRaises(auth.AuthFailure):
                adapter.HttpsJwksSnapshotFetcher(replace(self.policy, jwks_uri=uri))
        target = self.target(None)
        with self.assertRaises(FrozenInstanceError): target.policy = None
        self.assertNotIn(self.policy.jwks_uri, repr(target))
        with self.assertRaises(auth.AuthFailure): self.target(httpx.AsyncBaseTransport())
        with self.assertRaises(auth.AuthFailure): self.target(None, clock=None)

    def test_typed_explicit_revision_and_lifetime_never_send_on_invalid_values(self):
        calls = []
        async def handler(request): calls.append(request); raise AssertionError('send')
        target = self.target(httpx.MockTransport(handler))
        for revision in (0, -1, True, 1.0, '2', None, 2**63):
            self.denied(target(revision=revision, lifetime_seconds=60), 'AUTH_CONFIGURATION_INVALID')
        for lifetime in (0, -1, True, 1.0, '60', None, 3601):
            self.denied(target(revision=2, lifetime_seconds=lifetime), 'AUTH_CONFIGURATION_INVALID')
        for kwargs in ({}, {'revision': 2}, {'lifetime_seconds': 60},
                       {'revision': 2, 'lifetime_seconds': 60, 'url': 'https://other.invalid/keys'}):
            with self.assertRaises(TypeError): target(**kwargs)
        self.assertEqual(calls, [])

    def test_exact_get_no_auth_body_cookie_or_ambient_configuration(self):
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://' + CANARY, 'ALL_PROXY': 'http://' + CANARY,
                                    'NETRC': CANARY, 'SSL_CERT_FILE': CANARY, 'SSL_CERT_DIR': CANARY}):
            result, calls, _ = self.run_async(self.exchange())
        request = calls[0]
        self.assertEqual((request.method, str(request.url), request.content), ('GET', self.policy.jwks_uri, b''))
        self.assertNotIn('authorization', request.headers)
        self.assertNotIn('cookie', request.headers)
        self.assertNotIn('if-none-match', request.headers)
        self.assertEqual(request.headers['accept-encoding'], 'identity')
        self.assertEqual(set(request.extensions['timeout'].values()), {5})
        self.assertIs(type(result), auth.KeySnapshot)
        self.assertEqual((result.source_uri, result.revision, result.fetched_at, result.valid_until),
                         (self.policy.jwks_uri, 2, int(self.clock.wall), int(self.clock.wall) + 60))

    def test_production_factory_pins_verified_tls_no_environment_or_retries(self):
        seen, clients = {}, []
        async def handler(request): return httpx.Response(200, headers={'content-type':'application/json'}, stream=Stream())
        mock, real_client = httpx.MockTransport(handler), httpx.AsyncClient
        def transport(**kwargs): seen['transport'] = kwargs; return mock
        def client(**kwargs):
            seen['client'] = kwargs
            result = real_client(**kwargs); clients.append(result)
            self.assertFalse(result._trust_env); self.assertIsNone(result._auth); self.assertEqual(result._mounts, {})
            return result
        with patch.dict(os.environ, {'SSLKEYLOGFILE': CANARY, 'SSL_CERT_FILE': CANARY, 'SSL_CERT_DIR': CANARY}), \
                patch.object(adapter.httpx, 'AsyncHTTPTransport', side_effect=transport), \
                patch.object(adapter.httpx, 'AsyncClient', side_effect=client), \
                patch.object(adapter.ssl, 'create_default_context', side_effect=AssertionError('ambient TLS')), \
                patch.object(adapter.ssl.SSLContext, 'load_default_certs', side_effect=AssertionError('ambient CA')), \
                patch.object(adapter.ssl.SSLContext, 'load_cert_chain', side_effect=AssertionError('client certificate')):
            self.run_async(self.target(None)(revision=2, lifetime_seconds=60))
        for kwargs in seen.values():
            tls = kwargs['verify']
            self.assertEqual(tls.protocol, adapter.ssl.PROTOCOL_TLS_CLIENT)
            self.assertEqual(tls.verify_mode, adapter.ssl.CERT_REQUIRED); self.assertTrue(tls.check_hostname)
            self.assertIsNone(tls.keylog_filename)
            self.assertGreaterEqual(tls.minimum_version, adapter.ssl.TLSVersion.TLSv1_2)
            self.assertTrue(tls.verify_flags & adapter.ssl.VERIFY_X509_STRICT)
            self.assertTrue(tls.verify_flags & adapter.ssl.VERIFY_X509_PARTIAL_CHAIN)
            self.assertGreater(tls.cert_store_stats()['x509_ca'], 0)
            self.assertIs(kwargs['trust_env'], False)
            self.assertIs(kwargs['http1'], True); self.assertIs(kwargs['http2'], False)
            self.assertEqual((kwargs['limits'].max_connections, kwargs['limits'].max_keepalive_connections), (1, 0))
        self.assertIs(seen['client']['verify'], seen['transport']['verify'])
        self.assertEqual(seen['transport']['retries'], 0)
        self.assertIs(seen['client']['follow_redirects'], False)
        self.assertTrue(clients[0].is_closed)

    def test_status_redirects_and_304_never_read_retry_or_reuse_cache(self):
        for status in (301,302,303,304,307,308,400,401,403,429,500,503):
            stream = Stream((CANARY.encode(),))
            with self.subTest(status=status):
                self.denied(self.exchange(stream, status=status, headers={'location':'https://other.invalid/' + CANARY}))
                self.assertEqual(stream.reads, 0)

    def test_media_encoding_and_ambiguous_metadata_refuse_before_body(self):
        variants = [[], [('content-type','text/html')], [('content-type','application/json; charset=latin-1')],
                    [('content-type','application/json')]*2,
                    [('content-type','application/json'),('content-length','2'),('content-length','2')],
                    [('content-type','application/json'),('content-encoding','gzip')],
                    [('content-type','application/json'),('content-encoding','identity'),('content-encoding','identity')],
                    [('content-type','application/json'),('transfer-encoding','gzip')],
                    [('content-type','application/json'),('transfer-encoding','chunked'),('transfer-encoding','chunked')],
                    [('content-type','application/json'),('content-length','2'),('transfer-encoding','chunked')]]
        for headers in variants:
            stream = Stream((CANARY.encode(),))
            self.denied(self.exchange(stream, headers=headers)); self.assertEqual(stream.reads, 0)
        for media in adapter.JSON_TYPES:
            snapshot,_,_ = self.run_async(self.exchange(headers={'content-type':media}))
            self.assertEqual(snapshot.jwks, b'{"keys":[]}')

    def test_raw_header_bounds_exact_repeated_and_multibyte(self):
        for fields in ([(b'x-test', b'x'*8158)], [(b'x-test', b'x'*4076)]*2,
                       [(b'x-test', ('€'*2719).encode()+b'x')]):
            headers=[(b'content-type',b'application/json')]+fields
            self.assertEqual(sum(len(k)+len(v) for k,v in headers),8192)
            self.run_async(self.exchange(headers=headers))
            over=headers[:-1]+[(headers[-1][0],headers[-1][1]+b'x')]
            stream=Stream();self.denied(self.exchange(stream,headers=over));self.assertEqual(stream.reads,0)
        for values in ([('€'*3000).encode()], [('€'*1500).encode()]*2):
            headers=[(b'content-type',b'application/json')]+[(b'x-test',v) for v in values]
            self.assertLess(sum(len(k)+len(v) for k,v in httpx.Headers(headers).multi_items()),8192)
            stream=Stream();self.denied(self.exchange(stream,headers=headers));self.assertEqual(stream.reads,0)

    def test_declared_and_actual_body_limits_exact_and_no_full_consumption(self):
        for length in ('', '0', '-1', '+2', ' 2 ', '65537', '999999', '2,2', '2.0', CANARY):
            stream=Stream();self.denied(self.exchange(stream,headers={'content-type':'application/json','content-length':length}))
            self.assertEqual(stream.reads,0)
        for length in ('1','3'):
            self.denied(self.exchange(Stream((b'{}',)),headers={'content-type':'application/json','content-length':length}))
        exact,_,_=self.run_async(self.exchange(Stream((b'x'*4096,)*16),headers={'content-type':'application/json','content-length':'65536'}))
        self.assertEqual(len(exact.jwks),auth.MAX_JWKS)
        self.denied(self.exchange(Stream((b'',))))
        stream=Stream((b'x'*4096,)*1000)
        self.denied(self.exchange(stream));self.assertEqual(stream.reads,17)

    def test_errors_and_close_failures_are_sanitized_without_private_logs(self):
        output=io.StringIO();handler=logging.StreamHandler(output);logger=logging.getLogger('httpx');old=logger.level
        logger.addHandler(handler);logger.setLevel(logging.DEBUG)
        try:
            for error in (httpx.ConnectError(CANARY),httpx.ReadTimeout(CANARY),httpx.RemoteProtocolError(CANARY),RuntimeError(CANARY)):
                self.denied(self.exchange(error=error));self.denied(self.exchange(Stream(failure=error)))
            self.denied(self.exchange(Stream(close_error=True)))
        finally:logger.removeHandler(handler);logger.setLevel(old)
        self.assertNotIn(CANARY,output.getvalue())

    def test_header_wait_has_actual_overall_five_second_deadline(self):
        async def handler(request):await asyncio.Event().wait()
        started=time.monotonic()
        self.denied(self.target(httpx.MockTransport(handler))(revision=2,lifetime_seconds=60))
        self.assertGreaterEqual(time.monotonic()-started,4.7);self.assertLess(time.monotonic()-started,6.5)

    def test_dribbling_body_has_actual_overall_deadline(self):
        stream=Stream((b'x',)*30,delay=0.3);started=time.monotonic()
        self.denied(self.exchange(stream))
        self.assertGreaterEqual(time.monotonic()-started,4.7);self.assertLess(time.monotonic()-started,6.5)
        self.assertTrue(stream.cancelled);self.assertLess(stream.reads,30)

    def test_external_cancellation_during_headers_or_body_closes_and_propagates(self):
        async def headers():
            entered=asyncio.Event();clients=[];real=httpx.AsyncClient
            async def handler(request):entered.set();await asyncio.Event().wait()
            def client(**kwargs):result=real(**kwargs);clients.append(result);return result
            with patch.object(adapter.httpx,'AsyncClient',side_effect=client):
                task=asyncio.create_task(self.target(httpx.MockTransport(handler))(revision=2,lifetime_seconds=60))
                await entered.wait();task.cancel()
                with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.3)
            self.assertTrue(clients[0].is_closed)
        self.run_async(headers())
        stream=Stream((b'{}',),delay=10)
        async def body():
            task=asyncio.create_task(self.exchange(stream))
            while not stream.reads:await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.3)
        self.run_async(body());self.assertTrue(stream.cancelled);self.assertTrue(stream.closed)

    def test_response_close_cancellation_and_client_close_failure_preserve_cancellation(self):
        closing=asyncio.Event()
        class Closing(Stream):
            async def aclose(self):
                closing.set()
                try:await asyncio.Event().wait()
                finally:self.closed=True
        stream=Closing()
        async def check():
            task=asyncio.create_task(self.exchange(stream));await closing.wait();task.cancel()
            with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.3)
        self.run_async(check())
        stream=Stream((b'{}',),delay=10)
        async def handler(request):return httpx.Response(200,headers={'content-type':'application/json'},stream=stream)
        mock=httpx.MockTransport(handler)
        async def fail_close():raise RuntimeError(CANARY)
        mock.aclose=fail_close
        async def failure():
            task=asyncio.create_task(self.target(mock)(revision=2,lifetime_seconds=60))
            while not stream.reads:await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.3)
        self.run_async(failure());self.assertTrue(stream.closed)

    def test_request_start_freshness_expiry_and_clock_changes_fail_closed(self):
        self.denied(self.exchange(lifetime=1,hook=lambda:self.clock.advance(1)))
        self.denied(self.exchange(hook=lambda:setattr(self.clock,'wall',self.clock.wall-1)))
        self.clock.wall=2_000_000_000
        self.denied(self.exchange(hook=lambda:setattr(self.clock,'mono',self.clock.mono-1)))
        self.clock.mono=100
        self.denied(self.exchange(hook=lambda:setattr(self.clock,'wall',self.clock.wall+31)))
        self.clock.wall=2_000_000_000.75
        result,_,_=self.run_async(self.exchange(lifetime=3600,hook=lambda:self.clock.advance(0.1)))
        self.assertEqual((result.fetched_at,result.valid_until),(2_000_000_000,2_000_003_600))
        for value in (True,-1,float('nan'),float('inf'),2**63):
            async def handler(request):raise AssertionError('send')
            self.denied(self.target(httpx.MockTransport(handler),clock=lambda:value)(revision=2,lifetime_seconds=60))

    def test_no_shared_cookie_cache_or_implicit_fetch_on_unknown_key(self):
        calls=[]
        async def handler(request):
            calls.append(request);await asyncio.sleep(0)
            return httpx.Response(200,headers={'content-type':'application/json','set-cookie':'private='+CANARY,'cache-control':'max-age=999999'},stream=Stream((self.snapshot.jwks,)))
        target=self.target(httpx.MockTransport(handler))
        async def fetch_all():return await asyncio.gather(*(target(revision=i,lifetime_seconds=60) for i in (2,3)))
        results=self.run_async(fetch_all());self.assertEqual(len(calls),2)
        self.assertTrue(all('cookie' not in c.headers and 'authorization' not in c.headers for c in calls))
        self.assertTrue(all(r.valid_until-r.fetched_at==60 for r in results))
        self.verifier.install_snapshot(results[0])
        with self.assertRaises(auth.AuthFailure) as caught:
            self.verifier.verify_principal(self.token(headers={'kid':'unknown','typ':'at+jwt'}))
        self.assertEqual(caught.exception.code,'AUTH_KEY_UNKNOWN');self.assertEqual(len(calls),2)

    def test_candidate_requires_explicit_install_and_verifies_real_signed_token(self):
        previous=self.verifier._snapshot
        result,_,_=self.run_async(self.exchange(Stream((self.snapshot.jwks,))))
        self.assertIs(self.verifier._snapshot,previous)
        with self.assertRaises(FrozenInstanceError):result.revision=9
        before=self.verifier.verify_principal(self.token());self.assertEqual(before.key_revision,1)
        self.verifier.install_snapshot(result)
        after=self.verifier.verify_principal(self.token());self.assertEqual(after.key_revision,2)
        with self.assertRaises(auth.AuthFailure):self.verifier.recheck(before)

    def test_malformed_and_unsafe_key_candidates_reject_without_replacing_keys(self):
        weak = dict(self.jwk(), n=base64.urlsafe_b64encode(b'\x80' + b'\x01'*126 + b'\x03').rstrip(b'=').decode())
        self.assertEqual(auth.jwt.PyJWK.from_dict(weak, algorithm='RS256').key.key_size, 1024)
        bodies=[b'{',b'\xff',b'{"keys":[],"keys":[]}',b'{"keys":[]}',b'{"x":NaN}',
                json.dumps({'keys':[weak]}).encode(),
                json.dumps({'keys':[self.jwk(),self.jwk()]}).encode(),
                json.dumps({'keys':[dict(self.jwk(),d='synthetic-private')]}).encode(),
                json.dumps({'keys':[dict(self.jwk(),alg='HS256')]}).encode(),
                json.dumps({'keys':[dict(self.jwk(),use='enc')]}).encode(),
                json.dumps({'keys':[dict(self.jwk(),key_ops=['sign'])]}).encode(),
                json.dumps({'keys':[dict(self.jwk(),n='broken')]}).encode(),
                json.dumps({'keys':[self.jwk(kid=str(i)) for i in range(17)]}).encode()]
        previous=self.verifier._snapshot
        for data in bodies:
            candidate,_,_=self.run_async(self.exchange(Stream((data,))))
            with self.assertRaises(auth.AuthFailure):self.verifier.install_snapshot(candidate)
            self.assertIs(self.verifier._snapshot,previous)
            self.assertEqual(self.verifier.verify_principal(self.token()).subject,'offline-alice')

    def test_revision_order_rotation_and_source_binding_stay_at_install_boundary(self):
        candidate,_,_=self.run_async(self.exchange(Stream((self.snapshot.jwks,)),revision=1))
        with self.assertRaises(auth.AuthFailure):self.verifier.install_snapshot(candidate)
        rotated=json.dumps({'keys':[self.jwk(self.other_key,'next')]}).encode()
        candidate,_,_=self.run_async(self.exchange(Stream((rotated,)),revision=2))
        with self.assertRaises(auth.AuthFailure):self.verifier.install_snapshot(replace(candidate,source_uri='https://other.invalid/keys'))
        self.verifier.install_snapshot(candidate)
        with self.assertRaises(auth.AuthFailure) as caught:self.verifier.verify_principal(self.token())
        self.assertEqual(caught.exception.code,'AUTH_KEY_UNKNOWN')
        self.assertEqual(self.verifier.verify_principal(self.token(key=self.other_key,headers={'kid':'next','typ':'at+jwt'})).subject,'offline-alice')
        with self.assertRaises(auth.AuthFailure):self.verifier.install_snapshot(candidate)

    def test_expired_signed_token_snapshot_and_untrusted_key_urls_never_refresh(self):
        snapshot,calls,_=self.run_async(self.exchange(Stream((self.snapshot.jwks,))))
        self.verifier.install_snapshot(snapshot)
        with self.assertRaises(auth.AuthFailure):
            self.verifier.verify_principal(self.token(iat=int(self.clock.wall)-400,exp=int(self.clock.wall)-31))
        for name,value in [('jku','https://untrusted.invalid/keys'),('x5u','https://untrusted.invalid/cert')]:
            with self.assertRaises(auth.AuthFailure):self.verifier.verify_principal(self.token(headers={'kid':'offline','typ':'at+jwt',name:value}))
        self.clock.advance(60)
        with self.assertRaises(auth.AuthFailure) as caught:self.verifier.verify_principal(self.token())
        self.assertEqual(caught.exception.code,'AUTH_KEYS_STALE');self.assertEqual(len(calls),1)
        with self.assertRaises(auth.AuthFailure):self.verifier.install_snapshot(replace(snapshot,revision=3))

    def test_positive_effect_guards_block_network_database_environment_and_writes(self):
        import socket
        for callback in (lambda:socket.getaddrinfo('offline.invalid',443),
                         lambda:__import__('app.database'),lambda:open(PRIMARY/'.env'),
                         lambda:open('not-created','wb')):
            with self.assertRaises(AssertionError):callback()
        self.assertNotIn('app.config',sys.modules)
        self.assertNotIn('app.main',sys.modules)


if __name__ == '__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FetchTests))
    LOOP.run_until_complete(LOOP.shutdown_default_executor());LOOP.close()
    print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
                         network='NOT_USED',database='NOT_USED',transport='HTTPX MockTransport only')))
    raise SystemExit(not result.wasSuccessful() or bool(result.skipped))
