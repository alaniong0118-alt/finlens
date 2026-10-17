param(
    [string]$ProjectRoot = "D:\Projects\finlens-foundation",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$StopDatabase
)

# Port numbers and command-line substrings cannot establish process ownership.
# Keep the old entry point fail-closed so saved shortcuts cannot kill listeners.
throw 'Automatic shutdown is disabled. Press Ctrl+C in each original FinLens service terminal, then close it. To stop PostgreSQL, separately authorize and run docker compose stop postgres from the intended project. Never delete volumes. See docs/local-demo.md. No process or database was stopped.'
