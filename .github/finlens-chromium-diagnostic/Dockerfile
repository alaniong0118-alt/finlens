FROM --platform=linux/amd64 mcr.microsoft.com/playwright@sha256:06a9939e57531807f8d5fd76ce44b53165ffb7d7501d87ab10e285c20b1e971f
ENV NEXT_TELEMETRY_DISABLED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /diagnostic
COPY package.json package-lock.json ./
RUN test "$(node -p 'process.versions.node.split(".")[0]')" = 24 \
    && npm ci --omit=optional --ignore-scripts --no-audit --no-fund --registry=https://registry.npmjs.org \
    && test "$(node -p 'require("@playwright/test/package.json").version')" = 1.64.0
COPY --chown=pwuser:pwuser playwright.config.ts offline-browser-smoke.spec.ts ./
RUN chown pwuser:pwuser /diagnostic
USER pwuser
ENTRYPOINT ["/diagnostic/node_modules/.bin/playwright", "test", "-c", "playwright.config.ts"]
