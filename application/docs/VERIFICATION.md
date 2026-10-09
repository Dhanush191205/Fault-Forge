# Verification record — 9 October 2026

## Verified on this workstation

| Check | Actual result |
|---|---|
| Backend domain/API regression suite | **60 passed**, SQLite with both real migrations and immutable-history triggers |
| Installed Chroma engine integration | **2 passed**, ephemeral Chroma 1.5.9; machine/ID scoping and stale checksum rejection using supplied deterministic test vectors |
| Browser workflows | **6 passed**, installed Microsoft Edge through Playwright; final pass completed in 19.7 seconds |
| Python lint | Passed for application and tests |
| Public Python function/endpoint documentation | Passed AST documentation check |
| TypeScript + Vite production build | Passed |
| Deployment configuration | Docker Compose configuration parsed successfully without printing environment secrets |
| Packaged Windows launcher | Started local API, worker and frontend; idempotent seeding preserved existing records |
| PDF export | HTTP integration verified PDF signature; browser downloaded the actual assessment report |

Backend tests cover empty evidence with zero provider calls; exactly one JSON parse retry; successful fence-stripped recovery; schema errors; all three machines and difficulty profiles; component/range/joint-state/citation/prose rejection; vector misses; source permissions; no automatic publication; safe rejection audit; fourth-machine import; server grading; human rationale review; duplicate/stale actions and submissions; no answer-key leakage; user/role isolation; CSRF/session revocation; strict error envelopes; source/scenario/grade immutability; nonempty provenance; leased worker fencing; source revocation; unsafe production config; and admission/body-size limits.

The Chroma checks use the real local engine with test vectors. They verify database/query behavior, **not semantic embedding quality**, remote Chroma authentication or NVIDIA embedding service availability. No network model call was fabricated.

Browser workflows:

1. Instructor opens a validated draft, reviews the exact content, explicitly publishes it, and sees it in the catalog.
2. Trainee completes a CNC investigation, reloads/resumes progress, opens the 3D view, submits a correct assessment and downloads its PDF.
3. Expert session hides hints, requires reasoning, records a provisional score and receives a separate instructor review.
4. Queued generation is processed by the standalone worker and produces a draft without publication.
5. Mobile viewport at 390 × 844 remains usable without horizontal overflow.
6. Forced WebGL failure shows the functional component map and retains component selection.

The seeded curriculum is three authored cases × three levels = nine initial drafts. Browser tests generate additional versions and publish fixture drafts through the instructor UI; the current local catalog can therefore contain more than nine versions. All are explicitly synthetic. Test activity is not claimed as human curriculum certification.

## Frontend loading evidence

Final production build separates the main application (approximately **276 kB**, **86 kB gzip**) from the lazy 3D view (approximately **901 kB**, **244 kB gzip**). The generated HTML references only the main application and stylesheet; it has no 3D module preload. Vite reports its normal large-chunk advisory for the optional 3D bundle. This advisory is not hidden. Geometry is generated from local config and does not depend on downloaded GLB assets.

## Reproduction

```text
# From backend (use a fresh project-local --basetemp on Windows if system temp is restricted):
uv run pytest -q
uv run ruff check app tests
uv run python ../tools/check_docstrings.py

# From frontend, with local API, worker and web running:
npm ci
npm run build
npm run test:e2e
```

The browser configuration uses installed Edge locally and Playwright Chromium in CI. CI provisions isolated PostgreSQL with a random password, then reruns the backend suite using `TEST_DATABASE_URL`; each test uses its own random schema. Those remote CI jobs have been authored, **not executed in GitHub during this session**.

## Still unverified

- Docker Desktop did not establish its Linux engine on this workstation. Compose configuration validation passed, but PostgreSQL container integration and full container startup did not run.
- Live NVIDIA generation and embeddings require actual endpoint/model credentials; current local generation is the explicitly labeled fixture provider.
- No GPU benchmark, representative 100-learner load/soak test, physical calibration, production restore exercise or semantic retrieval evaluation was performed.
- No GitHub source push/PR or Vercel deployment was performed. Both are deployment-ready configurations, not published resources. A backend host and production domains still need to be selected/configured.
- Real-equipment qualification, content rights and operating limits require instructor approval for the exact machine revision. The user chose synthetic fixtures for this release.

Screenshots and a downloaded example PDF are in `docs/screenshots/`. Local `.env`, access notes, databases, dependency caches and browser traces are excluded from the source package. The single backend warning is an upstream Starlette notice about future TestClient transport migration; it did not affect the checks.
