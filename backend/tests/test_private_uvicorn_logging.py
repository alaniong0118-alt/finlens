"""Offline synthetic checks against the installed Uvicorn AccessFormatter."""
import importlib.util
import io
import logging
import os
from pathlib import Path
import socket
import sys
import unittest
from http import HTTPStatus

ROOT=Path(__file__).resolve().parents[2]
PRIMARY=ROOT/'backend'
if not (PRIMARY/'.venv/Lib/site-packages/uvicorn').is_dir():
    PRIMARY=Path('D:/Projects/finlens-foundation/backend')  # Isolated scratch only.
sys.path.insert(0,str(PRIMARY/'.venv/Lib/site-packages'))
from uvicorn.logging import AccessFormatter
from uvicorn.middleware.message_logger import message_with_placeholders
spec=importlib.util.spec_from_file_location('redaction_candidate',ROOT/'backend/app/private_uvicorn_logging.py')
safe=importlib.util.module_from_spec(spec);spec.loader.exec_module(safe)

def audit(event,args):
    if event.startswith(('socket.','subprocess.')) or event in {'sqlite3.connect','os.system'}:
        raise AssertionError('offline_effect_forbidden')
    if event=='open' and ((args[1] and any(c in args[1] for c in 'wax+')) or args[2] & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
        raise AssertionError('offline_write_forbidden')
sys.addaudithook(audit)

CANARIES=('SYNTHETIC-CODE-CANARY','SYNTHETIC-STATE-CANARY','SYNTHETIC-TOKEN-CANARY','SYNTHETIC-COOKIE-CANARY')

class LoggingTests(unittest.TestCase):
    def access(self,path,*,extra=None):
        r=logging.LogRecord('uvicorn.access',logging.INFO,__file__,1,'%s - "%s %s HTTP/%s" %d',
            ('127.0.0.1:9','GET',path,'1.1',303),None)
        r.extra_secret=extra;return r

    def format_access(self,r):
        return AccessFormatter('%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',use_colors=False).format(r)

    def test_observed_leak_is_removed_and_status_path_remain(self):
        r=self.access('/private-research/login/callback?code='+CANARIES[0]+'&state='+CANARIES[1],extra=CANARIES[3])
        self.assertIn(CANARIES[0],self.format_access(r));safe.PrivateUvicornFilter().filter(r)
        rendered=self.format_access(r);self.assertIn('/private-research/login/callback',rendered);self.assertIn('303',rendered)
        for secret in CANARIES:self.assertNotIn(secret,repr(r.__dict__));self.assertNotIn(secret,rendered)

    def test_access_query_dropped_for_other_paths_and_unknown_private_path_masked(self):
        for path,expected in [('/companies/AAPL?access_token='+CANARIES[2],'/companies/AAPL'),
                              ('/private-research/'+CANARIES[0]+'?x=1','/private-research/[other]'),
                              ('/private-research/login/callback%3Fcode%3D'+CANARIES[0],'/private-research/[other]'),
                              ('/api/finlens/private-research/'+CANARIES[1]+'?x=1','/api/finlens/private-research/[other]')]:
            r=self.access(path);safe.PrivateUvicornFilter().filter(r);rendered=self.format_access(r)
            self.assertIn(expected,rendered)
            for secret in CANARIES:self.assertNotIn(secret,rendered)

    def test_trace_scope_and_unknown_extra_fields_never_formatted(self):
        scope={'type':'http','path':'/private-research/login/callback','query_string':CANARIES[0].encode(),
               'headers':[(b'cookie',CANARIES[3].encode())],'state':{'token':CANARIES[2]}}
        logged=message_with_placeholders(scope)
        r=logging.LogRecord('uvicorn.asgi',5,__file__,1,'%s [%d] Started scope=%s',('client',1,logged),None)
        self.assertIn(CANARIES[0],r.getMessage());safe.PrivateUvicornFilter().filter(r)
        self.assertEqual(r.getMessage(),'ASGI started [details redacted]')
        for secret in CANARIES:self.assertNotIn(secret,repr(r.__dict__))
        self.assertEqual(scope['query_string'],CANARIES[0].encode())

    def test_malformed_record_is_bounded_and_never_raises(self):
        r=logging.LogRecord('uvicorn.access',logging.INFO,__file__,1,CANARIES[0],({'cookie':CANARIES[3]},),None)
        safe.PrivateUvicornFilter().filter(r);text=self.format_access(r)
        for secret in CANARIES:self.assertNotIn(secret,repr(r.__dict__));self.assertNotIn(secret,text)

    def test_unrelated_error_keeps_original_message_exception_and_metadata(self):
        for name in ('uvicorn.error','uvicorn.access','uvicorn.asgi'):
            try:raise ValueError('unrelated diagnostic')
            except ValueError:
                r=logging.LogRecord(name,logging.ERROR,__file__,1,'unrelated error',(),sys.exc_info())
            r.extra_marker=object();original=dict(r.__dict__);safe.PrivateUvicornFilter().filter(r)
            self.assertEqual(r.__dict__,original);self.assertIn('unrelated diagnostic',logging.Formatter().format(r))

    def test_opt_in_only_and_idempotent_install_does_not_change_levels(self):
        loggers=[logging.getLogger(x) for x in ('uvicorn.access','uvicorn.asgi')]
        before=[(list(x.filters),x.level,list(x.handlers),x.propagate) for x in loggers]
        try:
            safe.install_private_uvicorn_filter();safe.install_private_uvicorn_filter()
            for logger,state in zip(loggers,before):
                self.assertEqual(sum(type(x) is safe.PrivateUvicornFilter for x in logger.filters),1)
                self.assertEqual((logger.level,list(logger.handlers),logger.propagate),state[1:])
        finally:
            for logger,state in zip(loggers,before):logger.filters[:]=state[0]

    def test_installed_filter_sanitizes_before_handler_formatting(self):
        logger=logging.getLogger('uvicorn.access');before=(list(logger.filters),logger.level,list(logger.handlers),logger.propagate)
        trace=logging.getLogger('uvicorn.asgi');trace_before=list(trace.filters)
        output=io.StringIO();handler=logging.StreamHandler(output)
        handler.setFormatter(AccessFormatter('%(request_line)s %(status_code)s',use_colors=False))
        try:
            logger.handlers[:]=[handler];logger.setLevel(logging.INFO);logger.propagate=False
            safe.install_private_uvicorn_filter()
            logger.info('%s - "%s %s HTTP/%s" %d','client','GET',
                '/private-research/login/callback?code='+CANARIES[0]+'&state='+CANARIES[1],'1.1',303,
                extra={'private_payload':CANARIES[2]})
            text=output.getvalue();self.assertIn('/private-research/login/callback',text);self.assertIn('303',text)
            for secret in CANARIES:self.assertNotIn(secret,text)
        finally:
            logger.filters[:]=before[0];logger.setLevel(before[1]);logger.handlers[:]=before[2];logger.propagate=before[3]
            trace.filters[:]=trace_before

    def test_http_status_enum_remains_visible(self):
        r=self.access('/healthz?token='+CANARIES[2]);r.args=(*r.args[:-1],HTTPStatus.NOT_FOUND)
        safe.PrivateUvicornFilter().filter(r);self.assertIn('404',self.format_access(r))

    def test_import_never_installs_or_resolves_loggers(self):
        from unittest.mock import patch
        other=importlib.util.spec_from_file_location('redaction_import_probe',Path(safe.__file__))
        module=importlib.util.module_from_spec(other)
        with patch.object(logging,'getLogger',side_effect=AssertionError('unexpected activation')):
            other.loader.exec_module(module)

    def test_positive_effect_guard(self):
        with self.assertRaises(AssertionError):socket.socket()
        with self.assertRaises(AssertionError):open('not-created','wb')

if __name__=='__main__':unittest.main(verbosity=2)
