"""Independent in-runtime boundary gate, invoked before project imports."""
from pathlib import Path
import errno
import socket

assert {x.name for x in Path("/sys/class/net").iterdir()} == {"lo"}
for path, col, header in (("/proc/net/route", 0, True), ("/proc/net/ipv6_route", -1, False)):
    lines = Path(path).read_text().splitlines()[int(header):]
    assert all(line.split()[col] == "lo" for line in lines if line.strip()), "non-loopback route"
for family, local, remote in ((socket.AF_INET, ("127.0.0.1", 0), ("192.0.2.1", 443)),
                              (socket.AF_INET6, ("::1", 0), ("2001:db8::1", 443, 0, 0))):
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
    except OSError as exc:
        if family == socket.AF_INET6 and exc.errno in {errno.EPFNOSUPPORT, errno.EAFNOSUPPORT}:
            continue
        raise
    with sock:
        try:
            sock.bind(local)
        except OSError as exc:
            if family == socket.AF_INET6 and exc.errno == errno.EADDRNOTAVAIL:
                continue
            raise
        # Datagram connect checks routes without sending payload bytes.
        try:
            sock.connect(remote)
        except OSError as exc:
            assert exc.errno in {errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EADDRNOTAVAIL}, "unexpected route status"
        else:
            raise RuntimeError("reachable non-loopback route")
