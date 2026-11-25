"""Keep HTTP probes private; no redirects, network fallback or mock responses."""
import http.client
import time

def ready(port, path):
    for attempt in range(20):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            if response.status == 200:
                return
        except OSError:
            pass
        finally:
            connection.close()
        time.sleep(0.5)
    raise RuntimeError("loopback entrypoint not ready")

ready(8000, "/health")
ready(3000, "/")
