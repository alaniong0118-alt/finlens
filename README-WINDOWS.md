# FinLens on Windows

Use the [root README](README.md#local-setup) for current setup and verification status. This replaces the old empty-foundation guide.

Install Python, Node.js/npm, Git, and Docker Desktop with Docker Compose. Create private root `.env` with `POSTGRES_PASSWORD`. On a fresh checkout, copy `backend/.env.example` to `backend/.env`, then privately add matching `DATABASE_URL` and real `SEC_CONTACT_EMAIL`. Configure the API key/model only for live answers. Do not overwrite an existing configured env file.

Follow the root README commands for PostgreSQL, dependencies, migrations, seeding, Uvicorn, and Next.js. A fresh database needs explicit [data preparation](docs/architecture.md#data-preparation-on-a-fresh-checkout); it does not contain the recorded fixture.

## Alternate ports and production

For existing acceptance ports, start Uvicorn with `--port 8001`. Stop Next.js dev before building, then:

```powershell
cd frontend
$env:FINLENS_API_BASE_URL='http://127.0.0.1:8001'
npm run build
npm run start -- --hostname 127.0.0.1 --port 3001
```

The production proxy target is built into rewrites; rebuild after changing it. Restart the backend after changing private configuration.

Use Ctrl+C for backend/frontend and `docker compose down` to stop PostgreSQL while preserving its named volume. Do not remove the volume to update the repository.

Recorded tests/build/lineage pass. Real answers and full claim audit remain incomplete because credits were unavailable; see [verification](backend/reports/final_verification.md).
