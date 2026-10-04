# FinLens on Windows

Follow the root [Quick Start](README.md#quick-start): clone, copy examples, fill private database/contact values, start Docker PostgreSQL, install dependencies, migrate, run `python -m scripts.setup_demo`, then start both services.

The walkthrough uses the venv executable directly, so PowerShell activation is optional. Default ports are **backend 8000 / frontend 3000**. The frontend example targets `http://127.0.0.1:8000`.

The setup command prepares one official Apple filing and local embeddings without an OpenAI key. Complete data is reused; missing vectors are resumed. Set your real SEC contact before initial downloading. Do not enable offline model flags before the first MiniLM download.

## Production preview (optional)

From frontend after dependencies are installed:

```powershell
$env:FINLENS_API_BASE_URL='http://127.0.0.1:8000'
npm run build
npm run start -- --hostname 127.0.0.1 --port 3000
```

Stop the process already using port 3000 first. Development uses `.next`; production uses `.next-prod`. The production proxy target is built into rewrites, so rebuild after changing it. Restart the backend after changing private configuration.

Use Ctrl+C for backend/frontend and `docker compose down` to stop PostgreSQL while preserving its volume. Do not remove the volume to update the repository or change a password.

Recorded RAG tests/build/lineage pass. Real generated answers and claim audit remain incomplete because API credits were unavailable; setup does not require those calls.
