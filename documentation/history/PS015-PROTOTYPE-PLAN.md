# PS015 prototype implementation: start to finish

Planning estimate • 6 October 2026 • Eight weeks for two engineers with scheduled maintenance-instructor support

Use [architecture](PS015-ARCHITECTURE.md) and [data model](PS015-DATA-MODEL.md). The schedule is an estimate, not a delivery promise. It assumes access to authorized manuals, an instructor, a suitable inference endpoint and a deployment host. A solo part-time project needs a longer schedule or reduced scope.

## 1. Deliverable and scope

Demonstrate this complete workflow: an instructor selects approved machine documentation, generates a grounded scenario and quiz, reviews and publishes them; a trainee completes a simulated investigation; an instructor sees the replay and server-scored result.

Initial vertical slice: one motor, one reviewed failure case, five guided steps and five quiz questions. Expanded pilot: Motor, CNC and Compressor, reusing the documented 18-case/90-question curriculum only if its actual content can be recovered and approved. Do not present an unrecovered bank as newly built.

The MVP includes login/roles, scoped document ingestion, scenario generation, review, quiz bank, deterministic simulation, resume/replay, grading and operational visibility. Optional 3D should follow working 2D interactions. Live PLC control, broad factory diagnosis, physical simulation calibration, autonomous repair recommendations and training a foundation model are outside this prototype.

## 2. Execution phases

| Phase | Indicative timing | Work | Exit evidence |
|---|---|---|---|
| 0. Recover and define | Days 1–2 | Obtain actual source/migrations or choose a new implementation; inventory current features; define users, equipment, source rights and target host; agree SLOs | Reproducible checkout, written scope, source inventory, hardware/provider choice |
| 1. Foundations | Days 3–5 | Repository layout, dependency locks, CI, PostgreSQL/pgvector, object storage, API/UI skeleton, sessions/roles, one organization/site, migrations | Fresh database migration and authenticated instructor/learner smoke test |
| 2. Curriculum and ingestion | Week 2 | Instructor-authored seed case, failure taxonomy, competencies/rubric; manual upload/versioning/chunking; traceable source locations | One valid five-step case, quiz keys hidden, searchable approved evidence |
| 3. Grounded generation | Week 3 | Provider adapter, durable job leases, semantic embeddings, hybrid retrieval, structured generation, citations, validation, instructor review | Real provider creates a source-backed draft; publish and rejection flows verified |
| 4. Simulator and assessment | Week 4 | Deterministic engine, CAS/idempotency, action log, resume, public projections, quiz freezing, server assessment | Complete journey with reload, duplicate retry, stale action and replay checks |
| 5. Curriculum expansion and quality | Week 5 | Add machine cases/questions; build held-out retrieval/generation test sets; adversarial and equipment-scope tests; instructor review | Approved coverage matrix and measured generation/retrieval quality |
| 6. NVIDIA deployment and tuning | Week 6 | Configure actual NIM/profile if local serving selected; benchmark inference, tune bounds/precision; verify networking and source consent | Pinned deployment manifest, real GPU/provider results, rollback path |
| 7. Reliability and capacity | Week 7 | Shared limits for replicas, monitoring, PostgreSQL concurrency tests, LAN/browser checks, mixed-load soak, failure injection, restore exercise | Agreed SLO results, no lost/duplicate grades/actions, demonstrated recovery |
| 8. Pilot and handover | Week 8 | Instructor/technician pilot, fix observed issues, deployment/runbooks, limitations and demo video | Signed pilot acceptance, reproducible build, documented operating limits |

If the described application is recovered, phases 1, 2 and 4 become verification and targeted upgrade work. Do not rebuild working authentication, jobs or replay simply because this proposal names a target module differently.

## 3. Build details

### Phase 0 — decisions and evidence

Record the selected machine model/revision, user roles, learner cohort size, expected action frequency, expected authors/minute, document languages, maximum file size and whether manuals may leave the organization. Inspect the actual GPU with `nvidia-smi` on the intended serving host, rather than assuming this Windows workstation is the final GPU server.

Use a Linux deployment host supported by the chosen container/runtime. Windows may remain the development workstation; verify any WSL2/container-GPU route explicitly. If no suitable GPU is available, use an authorized NVIDIA-hosted provider for the first real-model slice and retain the same provider interface for later local serving.

Recover the handover's migrations and application before assigning a migration number. Its reported head `0007` is historical evidence only. Capture actual database/schema version, backups and a baseline test run. No PostgreSQL/Docker executable was found on the current review environment's PATH; that says nothing about the future deployment host.

### Phase 1 — repository and services

Suggested new-project layout; adapt recovered source instead of moving files unnecessarily:

```text
backend/app/
  identity/ knowledge/ curriculum/ generation/
  simulation/ assessment/ models/ operations/
backend/migrations/
backend/tests/
frontend/src/features/
  catalog/ authoring/ simulator/ assessments/
contracts/
data/fixtures/
evaluation/
deploy/
docs/
```

Create a locked Python environment and TypeScript frontend. Introduce PostgreSQL/pgvector from the first integration test, including an object-store emulator or a documented development filesystem adapter. Use immutable object keys and metadata checksums. A local filesystem adapter must not masquerade as shared multi-replica storage.

Start API, generation worker, PostgreSQL and web app. Add a separate ingestion worker when document work would delay generation. Redis is optional for the single-process milestone; it becomes required for the selected shared-limit implementation before using multiple API replicas. Store sample configuration without secrets; pin production container digests during deployment.

Use CI for schema/contract checks, meaningful unit/integration tests, frontend build, dependency/security checks and migration validation. GitHub Actions is a suitable pipeline location; creation of a remote repository or publication is a later explicit delivery action, not a prerequisite for this design.

### Phase 2 — establish correct content before generation

Have a maintenance instructor author one complete case and rubric. Record what a learner initially knows, what each action reveals, plausible alternative diagnoses and the final evidence needed. Treat numerical readings as synthetic unless they are linked to an approved recorded source with known units.

Ingest a small authorized corpus, initially about 10–20 source items if available. Store original bytes, content hashes, extraction version and source locations. Quarantine unsupported/invalid files. Extract ordinary text first; add OCR/table/diagram extraction only for documents that require it.

Choose chunking around sections and procedures; begin with approximately 400–800 tokens and modest overlap, then evaluate actual manuals. Keep warnings, numbered procedures and table context together where possible. Split lengths must respect the selected embedder's actual tokenizer and limits.

### Phase 3 — generation workflow

Implement `POST /api/generation/scenarios` as an authenticated instructor operation returning `202` and a job/status link. Pin source versions and the request hash at admission. Add `GET /api/jobs/{id}` and instructor-only draft edit/review/publication endpoints. Preserve compatible existing routes where available.

Workers claim with leases, retrieve permitted evidence, call the selected endpoint with bounded context/output, validate the returned draft and persist either a draft or an explicit error. Permit bounded transient retries. An invalid draft can be repaired only under a recorded bounded policy and must pass all checks again; never fabricate a successful scenario on provider failure.

Add two-step review: inspect public trainee preview and private instructor solution side by side; approve a content hash. Publication atomically creates/finalizes the scenario, quiz and rubric references. Expose version information and source locations to instructors.

### Phase 4 — interactive training

Provide catalog, scenario briefing, available actions, evidence panel, current state and quiz. Begin with a 2D component diagram; add lazy 3D only if it improves a learning objective. State shown in the UI comes from committed server state.

Implement start/resume, action, events, quiz, submit and result endpoints. Require expected revision and idempotency key on action requests. The browser sends answers and diagnosis; it never supplies authoritative duration, action history, score or reference key.

Demonstrate this race: two requests submit the same action at revision 2. One transition is committed. An identical-key retry returns the stored result; a conflicting request returns 409. A network disconnect after commit does not duplicate the action when the browser retries.

For spectating, retain conditional nonoverlapping polling initially. When moving to SSE, authorize subscriptions, send only committed public events, support cursor-based reconnect and reconcile against a current snapshot if the event-retention window has passed.

### Phase 5 — evaluate educational quality

Freeze an evaluation set before tuning: start with 30–50 instructor-authored retrieval questions across the equipment, plus 30 distinct generation briefs with multiple seeds. Hold out complete case/manual families where practical, rather than splitting near-duplicate chunks across train and test. This is a screening set; it cannot establish rare-failure probabilities.

Recommended measured criteria:

| Criterion | Definition | Proposed initial gate |
|---|---|---|
| Retrieval hit@8 | Queries with at least one instructor-labeled relevant authorized passage among eight results / eligible queries | ≥ 90%, reported by machine and query type |
| Citation validity | Resolved citations inside the authorized pinned bundle / emitted citations | 100% before publication |
| Claim support | Reviewed technical claims actually supported by cited evidence / reviewed claims | ≥ 95% on evaluation; no unsupported critical claim in a published case |
| First-pass draft validity | First model responses passing the output contract / generation attempts | ≥ 95%; also report after-repair rate and repair cost |
| Expert acceptance | Drafts usable with at most minor edits / reviewed drafts | Initial target ≥ 80%; distinguish minor/major/rejected |
| Critical defects | Published safety contradiction, answer leakage or wrong private key in reviewed release set | Zero known defects at publication |
| Replay/grade integrity | Verified final states and identical deterministic grades on recorded accepted inputs | 100% in the test suite |
| Curriculum coverage | Approved cases/questions per machine, difficulty and competency | Instructor-approved matrix; avoid unsupported broad coverage claims |

LLM judges can help triage support/clarity but cannot replace instructor decisions. Store judge model/version and compare against human ratings. Report denominators, uncertainty and per-equipment failures; a single aggregate “accuracy” hides different tasks.

Use a counterbalanced pre/post exercise with equivalent unseen cases to assess learning. Record completion, diagnostic correctness, evidence selection and instructor feedback. A small pilot may suggest improvement; it does not establish causal workforce productivity gains without an appropriate study.

The historical motor detector stays disabled until independent transfer validation passes. Do not tune and evaluate on overlapping windows from the same recording. Partition detector data by machine/session/run when metadata permits; report limitations when it does not.

### Phase 6 — NVIDIA optimization

Select an actual model and compatible deployment from measured quality results. Record model revision, tokenizer revision, image digest, NIM profile, GPU, driver/runtime, precision, sequence limits and concurrency. Check the image's profile listing and official support matrix; do not copy a profile from a different model or GPU.

Benchmark representative manual context and output lengths at increasing request concurrency. Measure queue wait, full draft time, tokens/second, memory and validation rate. Optimize prompt length and output size first, then batching/caching and supported precision. Compare quality after each change. Reserve GPU headroom so ingestion/reranking cannot evict or starve interactive serving.

The documented local provider currently permits only loopback HTTP. A container DNS hostname or remote GPU server needs an intentional allowlist/network configuration change with tests. Keep TLS/authentication and source-processing permissions explicit.

For a prototype demo, show one actual NVIDIA-backed generation and its deployment metadata. If only hosted inference is used, say so; do not label it locally GPU-benchmarked. If the provider is unavailable, clearly show the reviewed pre-generated training catalog and failed generation status.

### Phase 7 — hardening

Use production-like PostgreSQL tests for SKIP LOCKED claims, concurrent quotas, stale worker completion, publication, duplicate submission and tenant isolation. Include killed workers, expired leases, model timeout/OOM, database restarts, lost stream connections, revoked access and malformed document/model content.

Run the load profile in the architecture document: 100 authenticated learners, sustained mixed reads/actions, explicit bursts and simultaneous bounded authoring. Exercise actual browser devices separately because API load does not measure 3D rendering performance. Count queue rejection and failure behavior in results.

Demonstrate restore of both PostgreSQL and referenced source objects to a consistent point. Proposed production planning objectives: recovery point ≤ 15 minutes and recovery time ≤ 4 hours, subject to the selected backup infrastructure and a measured restore exercise. Keep these separate from prototype acceptance if the pilot has no operations coverage.

### Phase 8 — pilot delivery

Run a facilitated session with approximately 5–10 technicians and 1–2 instructors, subject to availability. Capture usability issues, misunderstood questions and unrealistic evidence. Fix blocking issues, rerun affected checks and record the approved release manifest.

Handover includes source, migrations, deployment manifests, dependency locks, sample data rights, content provenance, model/profile record, evaluation set/results, load report, screenshots/demo, operations and restore runbooks, limitations and a prioritized backlog. Define who owns curriculum approval, application operations and model release decisions.

## 4. Upgrading the documented existing pilot

1. Recover source and database; reproduce checks on the real baseline. Verify backup restoration before changing production data.
2. Add organizations/sites and nullable scoped columns. Produce an owner-to-organization mapping for review; quarantine ambiguous ownership. Backfill in batches.
3. Add composite FKs/indexes and validate tenant/site policies. Deploy compatible application reads/writes, then enforce non-null scope and RLS. Test pooled connections and workers.
4. Add model/embedding-space registries and a separate semantic index generation. Shadow-test retrieval with exact authorization filters and a held-out question set.
5. Switch retrieval through a pinned configuration only after quality/capacity gates pass. Retain lexical baseline and previous index for explicit rollback, not silent fallback.
6. Introduce shared rate limiting and outbox delivery while preserving persisted attempt authority. Reconcile duplicate-delivery behavior before enabling multiple consumers.
7. Introduce new scenario/question/rubric versions; preserve legacy engines, referenced content, scores and audit hashes. No unverified historical event fields are invented.
8. Canary live inference and multi-replica deployment. Roll back application/configuration if thresholds fail; use additive schema changes so rollback can still read old data.

## 5. Cost model and scope control

Do not quote a GPU purchase or cloud budget before model/profile, region and usage are known. Estimate monthly cost as GPU-host hours × verified hourly rate + storage/backup + CPU/database + network + hosted tokens where applicable. For hosted calls, record input/output tokens and retries. Track cost per instructor-approved scenario, since rejected drafts and repair calls are part of the true cost.

Prefer spending the first iteration on correct curriculum, retrieval evaluation and replay integrity. Add fine-tuning only after a documented failure analysis shows that better sources, retrieval and prompts are insufficient. If used later, train on curated accepted examples with case-family-disjoint evaluation and a rollbackable adapter version.

Add Kafka when sustained stream volume, fan-out or replay retention warrants a broker. Add a dedicated vector system when scoped PostgreSQL search fails measured requirements. Add Dynamo when distributed inference is needed. Add Omniverse when richer scenes support a tested training need. Each addition has its own benchmark and operational owner.

## 6. Final demonstration checklist

- Instructor uploads or selects an authorized manual and sees its exact version.
- Real model generation creates a grounded draft and quiz, with visible job state and citations.
- Invalid citations or unsupported equipment combinations are rejected.
- Instructor reviews both trainee view and private keys, then publishes an immutable release.
- Trainee starts, investigates, refreshes/resumes, answers questions and receives server-scored feedback.
- Instructor views recorded actions and replay; duplicate requests cannot change the grade.
- Unauthorized users cannot access another organization's sources, private keys or attempts.
- Generation outage does not interrupt existing training sessions.
- Performance, quality and recovery results are reported with their actual test conditions.

Completion means this workflow passes on the intended pilot environment with reviewed content and known operating limits. Production readiness additionally requires sustained-load evidence, deployment/restore verification, operational ownership and the agreed release gates.
