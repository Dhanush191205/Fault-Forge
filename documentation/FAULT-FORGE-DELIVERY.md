# Fault Forge implementation handover

The runnable application created for the current request is **`application/`**. Earlier `PS015-*` documents and `PROJECT-ACCOMPLISHMENTS.md` are preserved as historical context; their descriptions of older, unavailable implementations are not evidence about this build.

- [Start here](../application/README.md)
- [Actual verification and remaining release gates](../application/docs/VERIFICATION.md)
- [All 15 strict requirements mapped to implementation](../application/docs/STRICT-RULES.md)
- [Deployment guide](../application/docs/DEPLOYMENT.md)
- [Operations runbook](../application/docs/OPERATIONS.md)
- [Workspace screenshot](../application/docs/screenshots/workspace-preview.png)
- [Example training report](../application/docs/screenshots/example-training-report.pdf)

Workspace-relative paths below start at the project root. Earlier documents are grouped in [history](history/README.md); packaged source is in [releases](../releases/README.md).

The user approved synthetic training fixtures for this first release. The complete local workflow covers CNC, hydraulic press and conveyor training, three difficulty levels, approved-source generation, instructor publication, 3D/component-map exploration, diagnostic assessment, instructor reasoning review and PDF export. Original `knowledge-library/` material is not automatically approved for generation.

Launch at `http://localhost:5173` using `application/start-local.ps1`; unique generated local credentials are in `application/local-access.txt`. This private file is excluded from source packaging.

The code and deployment configurations are delivered locally. Live NVIDIA inference, PostgreSQL/container verification, representative load testing and production qualification are separate outstanding gates; see the verification record for exact evidence.
