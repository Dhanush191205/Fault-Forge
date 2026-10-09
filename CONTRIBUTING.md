# Working on Fault Forge

Application changes belong in `application/`; shared repository automation belongs in `.github/`. Add equipment through versioned data packs rather than machine-specific engine branches.

## Local checks

From `application/backend`:

```sh
uv sync --frozen --python 3.12 --extra vector
uv run ruff check app tests
uv run pytest -q
```

From `application/frontend`:

```sh
npm ci
npm run build
```

Browser checks require the local services and seeded synthetic accounts. Follow the [application guide](application/README.md). GitHub Actions also exercises PostgreSQL and the browser workflows.

Preserve grounding, server validation, instructor publication gates, version history and private answer keys. Update the [strict-rule matrix](application/docs/STRICT-RULES.md) and tests when changing those contracts.

Keep secrets in environment variables. Never commit `.env`, `local-access.txt`, databases, installed dependencies or browser traces. The [verification record](application/docs/VERIFICATION.md) distinguishes completed local checks from remaining production qualification.
