"""Offline MockTransport and existing signed callback fixture, no live services."""
import asyncio
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
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = ROOT/"backend"
if not (PRIMARY/"tests/test_private_workspace_login.py").is_file():
    PRIMARY = Path("D:/Projects/finlens-foundation/backend")  # Isolated scratch only.
sys.path[:0] = [str(PRIMARY/".venv/Lib/site-packages"), str(PRIMARY), str(PRIMARY/"tests")]

# Reuse the maintained wakeup loop, no-network/no-DB/private-environment guard,
# real JWT fixtures and in-memory ownership repository. No second harness/store.
from test_private_workspace_login import LoginTests, LOOP, login, COOKIE

spec = importlib.util.spec_from_file_location("token_exchange_candidate", ROOT/"backend/app/private_workspace_token_exchange.py")
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)
import httpx
from app.models import ResearchAccount

ENDPOINT = "https://offline.invalid/token"
CANARY = "SYNTHETIC-CREDENTIAL-CANARY-123"
BODY = ("grant_type=authorization_code&code="+CANARY+"&code_verifier="+CANARY).encode()


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks=(b"{}",), delay=0, failure=None, closing_failure=False):
        self.chunks, self.delay, self.failure = chunks, delay, failure
        self.closing_failure = closing_failure
        self.closed, self.reads, self.cancelled = False, 0, False

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
        if self.closing_failure:
            raise RuntimeError(CANARY)


class TransportTests(unittest.TestCase):
    def run_async(self, awaitable):
        return LOOP.run_until_complete(awaitable)

    def request(self, **changes):
        return replace(login.TokenExchange(ENDPOINT, BODY), **changes)

    async def exchange(self, stream=None, *, status=200, headers=None, request=None, error=None):
        stream = Stream() if stream is None else stream
        calls, clients = [], []
        real_client = httpx.AsyncClient
        async def handler(message):
            calls.append(message)
            if error:
                raise error
            return httpx.Response(status, headers={"Content-Type":"application/json"} if headers is None else headers,
                                  stream=stream)
        mock = httpx.MockTransport(handler)
        def client(**kwargs):
            result = real_client(**kwargs)
            clients.append(result)
            return result
        try:
            with patch.object(adapter.httpx, "AsyncClient", side_effect=client):
                reply = await adapter.HttpsTokenExchange(ENDPOINT, mock)(request or self.request())
            return reply, calls, stream
        finally:
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(clients), 1)
            self.assertTrue(clients[0].is_closed)
            if error is None:
                self.assertTrue(stream.closed)

    def denied(self, awaitable):
        try:
            self.run_async(awaitable)
        except login.LoginFailure as error:
            self.assertEqual((error.status, error.code, str(error)), (503,"LOGIN_UNAVAILABLE","LOGIN_UNAVAILABLE"))
            self.assertNotIn(CANARY, "".join(traceback.format_exception(error)))
        else:
            self.fail("expected sanitized refusal")

    def test_endpoint_configuration_is_explicit_canonical_and_immutable(self):
        with self.assertRaises(TypeError): adapter.HttpsTokenExchange()
        instance = adapter.HttpsTokenExchange(ENDPOINT)
        with self.assertRaises(FrozenInstanceError): instance.endpoint = "https://other.invalid/token"
        self.assertNotIn(ENDPOINT, repr(instance))
        for value in (None, "", "http://offline.invalid/token", "https://user:secret@offline.invalid/token",
                      "https://offline.invalid/token?x=1", "https://offline.invalid/token?",
                      "https://offline.invalid/token#", "https://OFFLINE.invalid/token", "https://offline.invalid:443/token",
                      "https://offline.invalid:0/token", "https://offline.invalid:99999/token", "https://offline.invalid",
                      "https://offline.invalid/a/../token", "https://offline.invalid/%74oken", "https://offline.invalid\\token",
                      "https://.invalid/token", "https://-invalid/token", "https://offline.invalid/token\n", "https://離線.invalid/token"):
            with self.subTest(value=value), self.assertRaises(login.LoginFailure): adapter.HttpsTokenExchange(value)
        adapter.HttpsTokenExchange("https://offline.invalid:8443/token")
        with self.assertRaises(login.LoginFailure): adapter.HttpsTokenExchange(ENDPOINT, httpx.AsyncBaseTransport())

    def test_dormant_import_does_not_construct_or_install_http_client(self):
        other=importlib.util.spec_from_file_location("token_exchange_import_probe",Path(adapter.__file__))
        module=importlib.util.module_from_spec(other);sys.modules[other.name]=module
        try:
            with patch.object(httpx,"AsyncHTTPTransport",side_effect=AssertionError("activation")), \
                    patch.object(httpx,"AsyncClient",side_effect=AssertionError("activation")):
                other.loader.exec_module(module)
                module.HttpsTokenExchange(ENDPOINT)
        finally:sys.modules.pop(other.name,None)

    def test_typed_contract_mismatch_never_reaches_transport(self):
        calls = []
        async def handler(request): calls.append(request); raise AssertionError("unexpected send")
        target = adapter.HttpsTokenExchange(ENDPOINT, httpx.MockTransport(handler))
        for request in (None, {}, *[self.request(**changes) for changes in (
                {"url":"https://other.invalid/token"}, {"url":ENDPOINT+"/"}, {"url":ENDPOINT+"?"},
                {"url":"https://OFFLINE.invalid/token"}, {"body":b""}, {"body":"string"},
                {"body":b"x"*(adapter.MAX_REQUEST_BYTES+1)}, {"timeout_seconds":0}, {"timeout_seconds":6},
                {"timeout_seconds":True}, {"timeout_seconds":1.0}, {"max_response_bytes":0},
                {"max_response_bytes":32769}, {"max_response_bytes":True}, {"follow_redirects":True},
                {"follow_redirects":0}, {"content_type":"application/json"})]):
            with self.subTest(request=type(request).__name__): self.denied(target(request))
        self.assertEqual(calls, [])

    def test_exact_form_no_auth_cookies_or_ambient_configuration(self):
        async def check():
            reply, calls, stream = await self.exchange(Stream((b'{"opaque":',b'"bytes"}')))
            self.assertIs(type(reply), login.TokenReply)
            self.assertEqual((reply.status, reply.content_type, reply.body), (200,"application/json",b'{"opaque":"bytes"}'))
            self.assertEqual(str(calls[0].url), ENDPOINT);self.assertEqual(calls[0].method,"POST")
            self.assertEqual(calls[0].content,BODY)
            self.assertNotIn("authorization",calls[0].headers);self.assertNotIn("cookie",calls[0].headers)
            self.assertEqual(calls[0].headers["content-type"],"application/x-www-form-urlencoded")
            self.assertEqual(calls[0].headers["accept-encoding"],"identity")
            self.assertEqual(set(calls[0].extensions["timeout"].values()),{5})
            self.assertNotIn(CANARY,repr(reply))
        with patch.dict(os.environ, {"HTTPS_PROXY":"http://"+CANARY, "ALL_PROXY":"http://"+CANARY,
                "SSL_CERT_FILE":CANARY, "SSL_CERT_DIR":CANARY, "NETRC":CANARY}):
            self.run_async(check())

    def test_production_client_enforces_tls_no_environment_no_retries(self):
        seen, clients, calls = {}, [], []
        async def handler(request): calls.append(request);return httpx.Response(200,headers={"content-type":"application/json"},stream=Stream())
        mock = httpx.MockTransport(handler);real_client=httpx.AsyncClient
        def transport(**kwargs): seen["transport"]=kwargs;return mock
        def client(**kwargs):
            seen["client"]=kwargs
            result=real_client(**kwargs);clients.append(result)
            self.assertFalse(result._trust_env);self.assertIsNone(result._auth);self.assertEqual(result._mounts,{})
            return result
        with patch.object(adapter.httpx,"AsyncHTTPTransport",side_effect=transport), \
                patch.object(adapter.httpx,"AsyncClient",side_effect=client), \
                patch.object(adapter.ssl,"create_default_context",side_effect=AssertionError("ambient TLS helper")):
            self.run_async(adapter.HttpsTokenExchange(ENDPOINT)(self.request()))
        for where in ("transport","client"):
            tls=seen[where]["verify"]
            self.assertIsInstance(tls,adapter.ssl.SSLContext)
            self.assertEqual(tls.verify_mode,adapter.ssl.CERT_REQUIRED);self.assertTrue(tls.check_hostname)
            self.assertIsNone(tls.keylog_filename);self.assertIs(seen[where]["trust_env"],False)
            self.assertEqual(seen[where]["limits"].max_connections,1)
            self.assertEqual(seen[where]["limits"].max_keepalive_connections,0)
        self.assertIs(seen['client']['verify'],seen['transport']['verify'])
        self.assertEqual(seen["transport"]["retries"],0);self.assertIs(seen["client"]["follow_redirects"],False)
        self.assertTrue(clients[0].is_closed);self.assertEqual(len(calls),1)

    def test_tls_context_ignores_ambient_keylog_certificate_and_client_credentials(self):
        with patch.dict(os.environ,{'SSLKEYLOGFILE':CANARY,'SSL_CERT_FILE':CANARY,'SSL_CERT_DIR':CANARY}), \
                patch.object(adapter.ssl,'create_default_context',side_effect=AssertionError('ambient TLS helper')), \
                patch.object(adapter.ssl.SSLContext,'load_default_certs',side_effect=AssertionError('ambient trust paths')), \
                patch.object(adapter.ssl.SSLContext,'load_cert_chain',side_effect=AssertionError('client certificate')):
            context=adapter._tls_context()
        self.assertEqual(context.protocol,adapter.ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(context.verify_mode,adapter.ssl.CERT_REQUIRED);self.assertTrue(context.check_hostname)
        self.assertGreaterEqual(context.minimum_version,adapter.ssl.TLSVersion.TLSv1_2)
        self.assertTrue(context.verify_flags & adapter.ssl.VERIFY_X509_STRICT)
        self.assertTrue(context.verify_flags & adapter.ssl.VERIFY_X509_PARTIAL_CHAIN)
        self.assertIsNone(context.keylog_filename);self.assertGreater(context.cert_store_stats()['x509_ca'],0)

    def test_fresh_client_cannot_carry_provider_cookies_to_next_exchange(self):
        calls=[]
        async def handler(request):
            calls.append(request)
            return httpx.Response(200,headers={"content-type":"application/json","set-cookie":"secret="+CANARY},stream=Stream())
        target=adapter.HttpsTokenExchange(ENDPOINT,httpx.MockTransport(handler))
        self.run_async(target(self.request()));self.run_async(target(self.request()))
        self.assertEqual(len(calls),2);self.assertTrue(all("cookie" not in c.headers for c in calls))

    def test_status_and_redirects_are_refused_without_reading_or_retrying(self):
        for status in (301,302,303,307,308,400,401,403,429,500,503):
            stream=Stream((CANARY.encode(),))
            with self.subTest(status=status):
                self.denied(self.exchange(stream,status=status,headers={"location":"https://other.invalid/"+CANARY}))
                self.assertEqual(stream.reads,0)

    def test_metadata_ambiguity_and_compression_are_refused_before_body(self):
        for extra in ([('content-type','application/json'),('content-type','application/json')],
                [('content-type','text/html')], [('content-type','application/json; charset=latin-1')], [],
                [('content-type','application/json'),('content-length','2'),('content-length','2')],
                [('content-type','application/json'),('content-encoding','gzip')],
                [('content-type','application/json'),('content-encoding','identity'),('content-encoding','identity')],
                [('content-type','application/json'),('transfer-encoding','chunked'),('transfer-encoding','chunked')],
                [('content-type','application/json'),('content-length','2'),('transfer-encoding','chunked')],
                [('content-type','application/json'),('transfer-encoding','gzip')],
                [('content-type','application/json'),('x-private',CANARY*300)]):
            stream=Stream((CANARY.encode(),))
            with self.subTest(metadata=len(extra)):self.denied(self.exchange(stream,headers=extra));self.assertEqual(stream.reads,0)

    def test_declared_length_admission_and_exact_actual_match(self):
        for length in ("", "0", "-1", "+2", " 2 ", "2,2", "32769", "999999", "2.0", CANARY):
            stream=Stream()
            with self.subTest(length=length):
                self.denied(self.exchange(stream,headers={"content-type":"application/json","content-length":length}))
                self.assertEqual(stream.reads,0)
        for length in ("1","3"):
            self.denied(self.exchange(Stream(),headers={"content-type":"application/json","content-length":length}))
        reply,_,_=self.run_async(self.exchange(Stream(),headers={"content-type":"application/json; charset=utf-8","content-length":"2"}))
        self.assertEqual(reply.body,b"{}")

    def test_utf8_single_and_repeated_headers_cannot_bypass_raw_byte_limit(self):
        for values,total in (([('€'*3000).encode()],9034),
                             ([('€'*1500).encode(),('€'*1500).encode()],9040)):
            headers=[(b'content-type',b'application/json')]+[(b'x-test',value) for value in values]
            self.assertEqual(sum(len(k)+len(v) for k,v in headers),total)
            decoded=httpx.Headers(headers).multi_items()
            self.assertLess(sum(len(k)+len(v) for k,v in decoded),adapter.MAX_HEADER_BYTES)
            stream=Stream()
            with self.subTest(repeated=len(values)>1):
                self.denied(self.exchange(stream,headers=headers));self.assertEqual(stream.reads,0)

    def test_raw_header_byte_boundary_counts_each_repeated_field(self):
        variants=[[(b'x-test',b'a'*8158)],
                  [(b'x-test',b'a'*4076),(b'x-test',b'b'*4076)],
                  [(b'x-test',('€'*2719).encode()+b'a')]]
        for fields in variants:
            headers=[(b'content-type',b'application/json')]+fields
            self.assertEqual(sum(len(k)+len(v) for k,v in headers),adapter.MAX_HEADER_BYTES)
            with self.subTest(repeated=len(fields)>1,utf8=b'\xe2' in fields[0][1]):
                reply,_,_=self.run_async(self.exchange(Stream(),headers=headers));self.assertEqual(reply.body,b'{}')
                over=headers[:-1]+[(headers[-1][0],headers[-1][1]+b'x')]
                self.assertEqual(sum(len(k)+len(v) for k,v in over),adapter.MAX_HEADER_BYTES+1)
                stream=Stream();self.denied(self.exchange(stream,headers=over));self.assertEqual(stream.reads,0)

    def test_streaming_actual_body_limit_without_declared_length(self):
        reply,_,_=self.run_async(self.exchange(Stream((b"x"*4096,)*8)))
        self.assertEqual(len(reply.body),32768)
        self.denied(self.exchange(Stream((b"x"*4096,)*8+(b"x",))))
        self.denied(self.exchange(Stream((b"",))))
        self.denied(self.exchange(Stream((b"123",)),request=self.request(max_response_bytes=2)))
        reply,_,_=self.run_async(self.exchange(Stream((b"12",)),request=self.request(max_response_bytes=2)))
        self.assertEqual(reply.body,b"12")

    def test_transport_stream_and_close_failures_are_secret_safe(self):
        output=io.StringIO();handler=logging.StreamHandler(output);logger=logging.getLogger("httpx");old=logger.level
        logger.addHandler(handler);logger.setLevel(logging.DEBUG)
        try:
            for error in (httpx.ConnectError(CANARY),httpx.ReadTimeout(CANARY),httpx.RemoteProtocolError(CANARY),RuntimeError(CANARY)):
                self.denied(self.exchange(error=error))
                self.denied(self.exchange(Stream(failure=error)))
            self.denied(self.exchange(Stream(closing_failure=True)))
        finally:logger.removeHandler(handler);logger.setLevel(old)
        self.assertNotIn(CANARY,output.getvalue())

    def test_overall_deadline_stops_dribbling_not_only_individual_reads(self):
        stream=Stream((b"x",)*8,delay=0.3);started=time.monotonic()
        self.denied(self.exchange(stream,request=self.request(timeout_seconds=1)))
        elapsed=time.monotonic()-started
        self.assertGreaterEqual(elapsed,0.85);self.assertLess(elapsed,1.5)
        self.assertTrue(stream.cancelled);self.assertTrue(stream.closed);self.assertLess(stream.reads,8)

    def test_overall_deadline_includes_response_header_wait(self):
        async def handler(request):await asyncio.Event().wait()
        target=adapter.HttpsTokenExchange(ENDPOINT,httpx.MockTransport(handler));started=time.monotonic()
        self.denied(target(self.request(timeout_seconds=1)))
        self.assertGreaterEqual(time.monotonic()-started,0.85);self.assertLess(time.monotonic()-started,1.5)

    def test_stream_limit_stops_before_consuming_large_response(self):
        stream=Stream((b"x"*4096,)*1000)
        self.denied(self.exchange(stream));self.assertEqual(stream.reads,9);self.assertTrue(stream.closed)

    def test_cancellation_during_headers_closes_client_and_is_not_wrapped(self):
        clients=[];entered=asyncio.Event();real_client=httpx.AsyncClient
        async def handler(request):entered.set();await asyncio.Event().wait()
        def client(**kwargs):result=real_client(**kwargs);clients.append(result);return result
        async def check():
            target=adapter.HttpsTokenExchange(ENDPOINT,httpx.MockTransport(handler))
            task=asyncio.create_task(target(self.request()))
            await entered.wait();task.cancel()
            with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.25)
        with patch.object(adapter.httpx,"AsyncClient",side_effect=client):self.run_async(check())
        self.assertEqual(len(clients),1);self.assertTrue(clients[0].is_closed)

    def test_cancellation_during_stream_closes_response_and_client(self):
        stream=Stream((b"x",)*10,delay=10)
        async def check():
            task=asyncio.create_task(self.exchange(stream))
            while not stream.reads:await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.25)
        self.run_async(check());self.assertTrue(stream.cancelled);self.assertTrue(stream.closed)

    def test_cancellation_during_response_closure_still_closes_client(self):
        closing=asyncio.Event()
        class Closing(Stream):
            async def aclose(self):
                closing.set()
                try:await asyncio.Event().wait()
                finally:self.closed=True
        stream=Closing()
        async def check():
            task=asyncio.create_task(self.exchange(stream));await closing.wait();task.cancel()
            with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.25)
        self.run_async(check());self.assertTrue(stream.closed)

    def test_client_close_error_cannot_replace_external_cancellation(self):
        stream=Stream((b"x",),delay=10)
        async def handler(request):return httpx.Response(200,headers={"content-type":"application/json"},stream=stream)
        mock=httpx.MockTransport(handler)
        async def close():raise RuntimeError(CANARY)
        mock.aclose=close
        async def check():
            task=asyncio.create_task(adapter.HttpsTokenExchange(ENDPOINT,mock)(self.request()))
            while not stream.reads:await asyncio.sleep(0)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await asyncio.wait_for(task,0.25)
        self.run_async(check());self.assertTrue(stream.cancelled);self.assertTrue(stream.closed)

    def test_unrelated_tasks_remain_responsive_and_no_shared_client_exists(self):
        stream=Stream((b"{}",),delay=0.1)
        async def check():
            task=asyncio.create_task(self.exchange(stream));await asyncio.sleep(0.01)
            self.assertFalse(task.done());self.assertFalse(stream.closed);await task
        self.run_async(check())


class CallbackIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls): LoginTests.setUpClass()

    def test_real_signed_callback_uses_mock_https_transport_once(self):
        fixture=LoginTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        calls=[]
        async def handler(request):
            calls.append(request)
            self.assertEqual(str(request.url),fixture.cfg.token_endpoint)
            fields=parse_qs(request.content.decode(),strict_parsing=True)
            self.assertEqual(set(fields),{'grant_type','code','redirect_uri','client_id','code_verifier'})
            self.assertEqual(fields['grant_type'],['authorization_code']);self.assertEqual(fields['code'],['offline-code'])
            self.assertEqual(fields['redirect_uri'],[fixture.cfg.redirect_uri]);self.assertEqual(fields['client_id'],[fixture.policy.client_id])
            self.assertNotIn('authorization',request.headers);self.assertNotIn('cookie',request.headers)
            self.assertEqual(fields['code_verifier'][0],captured_verifier[0])
            body=json.dumps(dict(access_token=fixture.next_token,token_type='Bearer',expires_in=300,scope='finlens.private')).encode()
            return httpx.Response(200,headers={'content-type':'application/json'},stream=Stream((body,)))
        exchange=adapter.HttpsTokenExchange(fixture.cfg.token_endpoint,httpx.MockTransport(handler))
        fixture.app=login.PrivateWorkspaceLogin(fixture.workspace,configuration=fixture.cfg,exchange=exchange,
            clock=lambda:fixture.clock.wall,monotonic=lambda:fixture.clock.mono)
        params,corr,_=fixture.begin();captured_verifier=[fixture.app._flows[params['state'][0]].verifier]
        result=fixture.finish(params,corr);self.assertEqual(result[0],303)
        research=fixture.cookie(result,COOKIE);self.assertTrue(research)
        state=fixture.state(research);self.assertEqual(state[0],200);self.assertEqual(json.loads(state[1])['status'],'authenticated')
        self.assertEqual(fixture.finish(params,corr)[0],400);self.assertEqual(len(calls),1)
        self.assertEqual(len(fixture.db.rows[ResearchAccount]),1)


if __name__ == '__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(TransportTests),
                             unittest.defaultTestLoader.loadTestsFromTestCase(CallbackIntegration)])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    LOOP.run_until_complete(LOOP.shutdown_default_executor());LOOP.close()
    print(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                         database='NOT_USED',network='NOT_USED',transport='HTTPX MockTransport only')))
    raise SystemExit(not result.wasSuccessful())
