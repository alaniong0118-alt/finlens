"""Optional Uvicorn access/ASGI TRACE safeguard; never installed on import.

Trusted server bootstrap must explicitly install before accepting traffic. This
does not sanitize application errors, Next, reverse proxies, or external APM.
"""
import logging
import re
from http import HTTPStatus

_METHODS = frozenset({'GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'})
_VERSIONS = frozenset({'1.0','1.1','2','3'})
_PATH = re.compile(r'/[A-Za-z0-9/._~%+\-]{0,2047}\Z')


def _clean(record, message, args):
    """Discard arbitrary extras, cached formatting, traceback and stack fields."""
    fresh = logging.LogRecord(record.name, record.levelno, __file__, 0, message, args, None)
    record.__dict__.clear()
    record.__dict__.update(fresh.__dict__)


class PrivateUvicornFilter(logging.Filter):
    def filter(self, record):
        if record.name == 'uvicorn.access' and record.levelno == logging.INFO:
            args = record.args
            if type(args) is tuple and len(args) == 5:
                _, method, target, version, status = args
                method = method if type(method) is str and method in _METHODS else 'OTHER'
                version = version if type(version) is str and version in _VERSIONS else '?'
                status = int(status) if (type(status) is int or type(status) is HTTPStatus) and 100 <= status <= 599 else 0
                path = target.split('?',1)[0].split('#',1)[0] if type(target) is str else ''
                path = path if _PATH.fullmatch(path) else '/[redacted]'
                # A malformed private subpath is never echoed. The actual
                # callback URI is a constant; query parameters are never logged.
                for prefix in ('/private-research', '/api/finlens/private-research'):
                    if path == prefix or path.startswith(prefix+'/'):
                        suffix = path[len(prefix):]
                        if suffix not in {'/login/start','/login/callback','/login/cancel',
                                          '/state','/notes','/note','/sources','/export','/logout'}:
                            path = prefix + '/[other]'
                        break
                _clean(record, '%s - "%s %s HTTP/%s" %d', ('[client]',method,path,version,status))
            else:
                _clean(record, '%s - "%s %s HTTP/%s" %d', ('[client]','OTHER','/[redacted]','?',0))
        elif record.name == 'uvicorn.asgi' and record.levelno == 5:
            # TRACE scope and extension dictionaries can contain arbitrary data.
            # Preserve an event category, never serialize scope/message contents.
            message = record.msg if type(record.msg) is str else ''
            phase = ('started' if 'Started scope=' in message else 'receive' if 'Receive ' in message
                     else 'send' if 'Send ' in message else 'raised' if 'Raised exception' in message
                     else 'completed' if 'Completed' in message else 'event')
            _clean(record, 'ASGI %s [details redacted]', (phase,))
        return True


def install_private_uvicorn_filter():
    """Explicit, idempotent in-process opt-in; does not change handlers or levels."""
    for name in ('uvicorn.access','uvicorn.asgi'):
        logger = logging.getLogger(name)
        if not any(type(f) is PrivateUvicornFilter for f in logger.filters):
            logger.addFilter(PrivateUvicornFilter())
