# ⚙️ Fault-Forge

**GenAI-Powered Industrial Maintenance Training Simulator**

Fault-Forge is an educational industrial-training platform designed to simulate realistic equipment-failure scenarios, guide technicians through diagnostic workflows, assess their decisions, and visualize equipment through a 3D digital-twin interface.

> This project is intended for training and simulation only. It does not connect to or control physical machinery.

## Project Goals

- Generate realistic maintenance-failure scenarios from technical documents and case histories
- Provide interactive branching diagnostic simulations
- Create quiz banks and structured assessments
- Score trainee performance using configurable rubrics
- Maintain trainee attempt and assessment history
- Visualize equipment using 3D digital twins
- Support instructor and administrator workflows

## Planned / Current Architecture

```text
React Frontend
├── Dashboard
├── Scenario Console
├── Quiz Runner
├── Assessment History
├── Admin / Documentation Panel
└── 3D Digital Twin Viewer

FastAPI Backend
├── Authentication & Users
├── Scenario Engine
├── Assessment Engine
├── Document / RAG Pipeline
├── Job Worker
└── REST / Streaming APIs

Data Layer
├── PostgreSQL
└── pgvector

Infrastructure
└── Docker Compose
```

## Core Technology Stack

- React + Vite
- Python + FastAPI
- PostgreSQL
- pgvector
- Docker / Docker Compose
- Three.js / React Three Fiber
- Generative AI / RAG

## Main Functional Areas

1. **Authentication and Roles** — administrator, instructor, and trainee access
2. **Scenario Generation** — grounded failure scenarios from manuals and historical cases
3. **Interactive Simulation** — evidence gathering and diagnostic decision workflows
4. **Quiz & Assessment** — structured knowledge checks and scoring
5. **Training Records** — saved attempts, submissions, and assessment results
6. **3D Digital Twin** — interactive equipment visualization
7. **Documentation** — academic and project reporting outputs

## Recommended Repository Structure

```text
Fault-Forge/
├── frontend/
├── backend/
├── worker/
├── docs/
├── tests/
├── scripts/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Development Status

**Active Development**

This repository is being structured as the main portfolio-grade implementation of Fault-Forge.

## Engineering Principles

- Keep training logic deterministic where required
- Never expose hidden answer keys before submission
- Keep physical machinery completely disconnected
- Separate frontend, backend, worker, and data responsibilities
- Document architecture and setup clearly
- Use environment variables for secrets and deployment configuration

## Author

**M Dhanush**  
GitHub: `Dhanush191205`
