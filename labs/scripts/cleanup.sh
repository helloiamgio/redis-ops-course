#!/usr/bin/env bash
# Arresta tutte le istanze dei lab (standalone, sentinel, cluster) sulle porte note.
set -uo pipefail
PORTS=(6379 6380 6381 7000 7001 7002 7003 7004 7005 7006 26379 26380 26381)
for p in "${PORTS[@]}"; do
  redis-cli -p "$p" shutdown nosave 2>/dev/null || true
done
echo ">> Tutte le istanze dei lab sono state arrestate."
