#!/usr/bin/env bash
# Arresta lo stack Sentinel locale e (opzionale) pulisce i dati.
# Uso: ./sentinel-down.sh [BASE_DIR] [--purge]
set -uo pipefail
BASE_DIR="${1:-$HOME/redis-lab/sentinel}"
for p in 26379 26380 26381 6379 6380 6381; do
  redis-cli -p "$p" shutdown nosave 2>/dev/null || true
done
echo ">> Stack Sentinel arrestato."
if [[ "${2:-}" == "--purge" ]]; then
  rm -rf "$BASE_DIR"
  echo ">> Dati rimossi: $BASE_DIR"
fi
