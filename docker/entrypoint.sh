#!/usr/bin/env bash
set -euo pipefail

>&2 echo "[entrypoint] running alembic upgrade head..."
alembic upgrade head

>&2 echo "[entrypoint] starting fastapi..."
exec "$@"
