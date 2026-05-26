# Contributing to Hazlo

Thanks for your interest! This project is early-stage and maintained by a small team.

## Quick Start

```bash
git clone https://github.com/oliverma/hazlo.git
cd hazlo
mise install && uv venv && source .venv/bin/activate && uv sync
cp .env.example .env
docker compose up -d
mise run migrate && mise run dev
```

See [README.md](README.md) for full setup details.

## Before Committing

```bash
mise run fmt          # format
mise run lint         # lint
mise run typecheck    # type-check
mise run test         # test suite
```

### TDD Enforcement

A pre-commit hook (`.githooks/pre-commit`) enforces test-driven development:

- If you change `hazlo/*.py` files, you **must** also change `tests/*.py` files in the same commit
- Exceptions: `__init__.py`, `templates/`, `static/`, `docker/`, `alembic/`
- Emergency bypass: `git commit --no-verify` (document why in commit message)

Write the test **before** the implementation. Watch it fail. Then make it pass.

## Conventions

- **Architecture**: DDD — domain has zero framework imports. See [docs/ai-context.md](docs/ai-context.md).
- **Frontend architecture (mandatory)**: HTMX + Jinja SSR with persistent shell.
	- Hard refresh: full-page render (`base.html`).
	- Internal navigation: swap only `#main-content`.
	- Never replace full `<body>` during admin navigation.
	- Use canonical trailing-slash admin URLs to avoid redirects.
- **Versioning**: Timestamp format `YYYYMMDDHHMM` — **no semver**. Dev: `0.0.0`, release: automatic on merge to `main`.
- **Branching**: `dev` for daily work, `main` for releases. PRs target `dev`.
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) — `feat(scope):`, `fix(scope):`, `docs:`, etc.
- **Type annotations**: required on all function signatures.
- **Tests**: before or alongside implementation. Domain tests = pure unit, no I/O.

## Pull Requests

1. Create a feature branch from `dev`
2. Make changes, add tests
3. Run `mise run fmt && mise run lint && mise run typecheck && mise run test`
4. Open a PR — fill in the template

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## License

Contributions are licensed under [HSEL-1.0](LICENSE). See [ETHICAL-USE.md](ETHICAL-USE.md) for restrictions.