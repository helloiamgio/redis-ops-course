#!/usr/bin/env bash
# Arresta il cluster locale a 6 nodi e (opzionale) pulisce i dati.
# Uso: ./cluster-down.sh [BASE_DIR] [--purge]
set -uo pipefail
BASE_DIR="${1:-$HOME/redis-lab/cluster}"
for p in 7000 7001 7002 7003 7004 7005; do
  redis-cli -p "$p" shutdown nosave 2>/dev/null || true
done
echo ">> Cluster arrestato."
if [[ "${2:-}" == "--purge" ]]; then
  rm -rf "$BASE_DIR"
  echo ">> Dati rimossi: $BASE_DIR"
fi
