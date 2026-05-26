#!/usr/bin/env bash
set -euo pipefail

>&2 echo "[worker-entrypoint] running prefect init..."
python docker/prefect_init.py

>&2 echo "[worker-entrypoint] starting prefect worker..."
exec prefect worker start --pool local-pool
