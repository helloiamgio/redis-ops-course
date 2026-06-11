#!/usr/bin/env bash
# Avvia un Redis Cluster locale a 6 nodi (3 master + 3 replica) per i lab.
# Validato su Redis 7.x/8.x. Uso: ./cluster-up.sh [BASE_DIR]
set -euo pipefail
BASE_DIR="${1:-$HOME/redis-lab/cluster}"
PORTS=(7000 7001 7002 7003 7004 7005)

echo ">> Avvio nodi in $BASE_DIR"
for p in "${PORTS[@]}"; do
  mkdir -p "$BASE_DIR/$p"
  redis-server --port "$p" \
    --cluster-enabled yes \
    --cluster-config-file "$BASE_DIR/$p/nodes.conf" \
    --cluster-node-timeout 5000 \
    --appendonly yes \
    --dir "$BASE_DIR/$p" \
    --daemonize yes \
    --logfile "$BASE_DIR/$p/redis.log"
done
sleep 2

echo ">> Creazione cluster (3 master + 1 replica ciascuno)"
redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1 --cluster-yes

echo ">> Stato:"
redis-cli -p 7000 cluster info | grep -E 'cluster_state|cluster_slots_assigned'
echo ">> Pronto. Connettiti con:  redis-cli -c -p 7000"
