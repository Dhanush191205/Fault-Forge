# Strict-rule implementation map

The user selected synthetic fixtures for the initial release. All real-equipment boundaries still apply.

| Rule | Enforcement | Verification |
|---|---|---|
| A1: never call generator without RAG | `EvidenceBundle.require_grounding` runs on admission and before every model call/retry; case plus manual mandatory | Empty-context mock proves zero model calls; missing/wrong-machine source tests |
| A2: component IDs | Query authoritative `components` table and compare with selected case before persistence | Unknown/cross-machine IDs rejected; failed job audit has safe code |
| A3: sensor ranges | Finite JSON/Pydantic numbers; normal/abnormal range check; exact joint case state; recheck before rendering | Huge values, wrong state, unknown sensor, plausible-but-inconsistent value rejected |
| A4: no auto-publication | Worker stages draft, automatic validation and private quiz rows in one transaction; explicit instructor hash approval required | Trainee catalog empty after seed; worker success remains draft |
| B5: defensive JSON | Complete fence stripping, bounded payload, duplicate-key/NaN rejection; exactly two calls after repeated parse errors, one after schema failure | Parametrized malformed-response and recovery tests |
| B6: consistent errors | Domain, schema, framework and DB errors produce `{error:{code,message,request_id}}` | HTTP validation, malformed body, hidden route, quota and size-limit tests |
| C7: backend difficulty | `PROFILES` enforces hints, unique distractor counts and mandatory free text at submission | Nine machine/level combinations; tampered hints/options and missing reasoning rejected |
| D8: provenance | Non-null `generator_version`, `source_case_ids`; nonempty DB guard; immutable source manifest and content hash | Required provenance and DB constraints; pinned source invalidation tests |
| D9: preserve history | Retirement only; new content uses new IDs; DB triggers reject source/scenario/quiz/history replacement and completed result overwrites | Delete/update guard tests; retirement retains existing session |
| E10: secrets | Environment-only provider/DB/bootstrap secrets; `.env.example` has empty secret fields; local setup creates random credentials | Ignored local secret files; static source review |
| E11: validate inputs | Strict bounded contracts, normalized plain text, identifier allowlists, ORM bind parameters, JSON-encoded prompt data, isolated system instructions | Forged grade fields and SQL-like identifiers rejected; prompt encoding test |
| F12: separate modules | Public service functions for RAG, provider, validator, scenario engine, simulation, assessment and reports | Independent unit and full API workflow suites |
| F13: documentation | Public functions/endpoints have docstrings; frontend exports use JSDoc; OpenAPI at `/api/docs` | Source lint and documentation contract check |
| F14: configuration-only equipment | Generic machine/component/sensor/geometry/case contracts | Fourth-machine import/generation regression test |
| G15: procedural safety | All generated displayed prose must exactly match approved source text; regex screening adds conservative detection; instructor safety review before publication | Unsafe and novel text rejection, enforced safety-first action sequence |

The safety scanner deliberately rejects some negated unsafe phrases too. It is a conservative triage mechanism, not a semantic proof of safe natural language. Exact reviewed-text selection and human review provide the stronger boundary. Instructors must review imported source correctness; the application cannot establish the truth of an authored manual or validate a real machine's physics by inspecting JSON.

SQLAlchemy statements bind values. Chroma is never allowed to broaden a machine or source selection on a retrieval miss. The frontend receives public projections; source text, answer keys and draft content remain instructor-only until intentional post-assessment feedback.
