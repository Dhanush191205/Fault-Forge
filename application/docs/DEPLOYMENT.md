# Deployment guide

## Local container stack

Copy `.env.example` to `.env` or run `tools/setup_local.py`. Set the independent PostgreSQL password. The provided Compose file is a **loopback-only development profile**; it keeps PostgreSQL and Chroma on the internal network.

```powershell
docker compose up --build -d
docker compose --profile setup run --rm seed
```

Open `http://localhost:8080`. The API container applies migrations before listening; the worker waits for API readiness. Synthetic seed data is mounted read-only into the one-time seed service. Persistent Docker volumes hold DB/index state. Do not use `docker compose down -v` for a deployed training installation.

For a production release, use a separately reviewed deployment manifest with HTTPS, private database/vector networking, backups, pinned image digests, explicit frontend origin and `ENVIRONMENT=production`, `DEMO_MODE=false`, `SECURE_COOKIES=true`. Fixture backends are rejected in this mode. Run migrations once as a release job before adding replicas; runtime roles should have no DDL permission. Never expose Chroma publicly without authentication/TLS. The application is a single-organization installation; do not host unrelated tenants together without adding tenant scoping and isolation tests.

## GitHub

The connected repository discovered during implementation is `Dhanush191205/Fault-Forge`; it contained a README only. The deliverable is in the local `application/` directory. No existing remote history was overwritten. The supplied `.github/workflows/ci.yml` belongs at repository root if `application/` becomes the repository itself. If using it as a subdirectory, change the workflow path defaults to `application/backend` and `application/frontend`.

Use a feature branch and pull request after reviewing the local implementation and verification results. Include only source, locks, fixtures, docs and tests. Exclude `.env`, `local-access.txt`, database files, dependencies, logs, and browser traces. Keep screenshots only after confirming they contain no personal data or credentials.

## Vercel frontend with an independently deployed API/worker

The Vercel connector found no existing Fault Forge project. The frontend is a Vite deployment. API/worker processes and persistent PostgreSQL/Chroma belong on an environment suited to their lifecycle; the standalone leased worker is not a Vercel request handler.

1. Deploy the API and generation worker to your chosen host, sharing PostgreSQL and the configured Chroma endpoint. Keep secrets server-side.
2. Provision an instructor using `BOOTSTRAP_PASSWORD` from the environment:

   ```text
   python -m app.admin --email instructor@example.org --name "Training instructor" --role instructor
   ```

3. Import approved equipment-specific curriculum through the authenticated UI/API and index it with the configured embedder. Production rejects synthetic sources.
4. Set `ALLOWED_ORIGINS` to the exact HTTPS frontend domain. Keep session cookies secure. Use a stable custom domain or explicitly approved preview origins; never `*`.
5. Configure a concrete same-origin API gateway before deploying the frontend:

   ```text
   python tools/configure_vercel.py https://your-backend.example.org
   ```

6. Deploy with Vercel project root `frontend`, Vite framework, `npm run build`, output `dist`. `VITE_API_URL` should remain `/api`; secrets must never use the public `VITE_` prefix.
7. Verify Set-Cookie behavior through the proxy, sign-in, CSRF origin checks, generation polling, a complete assessment, PDF download and source/answer access isolation.

The checked-in `vercel.json` intentionally has no invented backend URL. It serves the frontend and leaves `/api/` unconfigured until the gateway script is run. Publishing this file alone would not deploy a working full-stack application.

## NVIDIA serving and capacity

The provider uses NVIDIA's documented OpenAI-compatible chat-completions interface. Pin the actual model revision, NIM image digest, serving profile, GPU, driver/runtime and context limits in the deployment release record. Hosted inference and local NIM use the same application adapter; credentials and endpoint/model names are environment configuration.

Do not infer hardware needs from the product name. Use the selected model's supported profiles and a representative benchmark. Measure full draft latency, token usage, rejection rate, queue wait, memory headroom and cost per approved scenario. Keep GPU inference outside learner action transactions. Scale API replicas and workers separately; each worker currently handles one bounded job at a time. PostgreSQL workers use row locks, SKIP LOCKED claims and expiring lease tokens.

NVIDIA's catalog lists `rag-blueprint` and `rag-eval`; they are useful optional companions for deployment/reference evaluation. They were not installed or substituted for the requested FastAPI/Chroma architecture. Optional installation after approval: `npx skills add nvidia/skills --skill rag-eval --agent codex --global --yes`. First useful prompt: “Evaluate machine-scoped retrieval against instructor-labeled held-out cases and report misses by machine and difficulty.”

Official references consulted: [NVIDIA NIM API reference](https://docs.nvidia.com/nim/large-language-models/latest/reference/api-reference.html), [NVIDIA skill catalog](https://github.com/NVIDIA/skills/tree/main/skills), [Chroma query documentation](https://docs.trychroma.com/docs/querying-collections/query-and-get), [Vercel Vite deployment](https://vercel.com/docs/frameworks/frontend/vite), [Vercel environment variables](https://vercel.com/docs/environment-variables/framework-environment-variables).
