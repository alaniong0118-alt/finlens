export type IgnoredAbortDelivery = { path: string; query: string; pin: string | null; status: number; signalAborted: boolean };

// Passed directly to addInitScript. Keep this function self-contained: Playwright
// serializes it into the browser, without its module's imports or closures.
export function installIgnoredAbort({ path }: { path: string }) {
  const selectedPath = path.startsWith('/api/finlens/') ? path : `/api/finlens${path}`;
  if (!selectedPath.startsWith('/api/finlens/companies/')) throw new Error('Invalid ignored-abort API path');
  const nativeFetch = window.fetch.bind(window);
  const deliveries: IgnoredAbortDelivery[] = [];
  Object.assign(window, { qaDelivered: 0, qaDeliveries: deliveries });
  window.fetch = async (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href);
    if (url.origin !== location.origin || url.pathname !== selectedPath) return nativeFetch(input, init);
    const signal = init?.signal === undefined ? (input instanceof Request ? input.signal : null) : init.signal;
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    // null also overrides a Request object's inherited signal. The caller's
    // original signal remains intact for the real API/component lifecycle guards.
    const response = await nativeFetch(input, { ...init, signal: null });
    if (deliveries.length >= 200) throw new Error('Ignored-abort delivery limit exceeded');
    deliveries.push({ path: url.pathname, query: url.search, pin: headers.get('X-FinLens-Data-Version'), status: response.status, signalAborted: signal?.aborted ?? false });
    Object.assign(window, { qaDelivered: deliveries.length });
    return response;
  };
}
