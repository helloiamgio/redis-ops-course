#!/usr/bin/env bash
# Avvia uno stack HA locale: 1 master + 2 replica + 3 Sentinel (quorum 2).
# Validato su Redis 7.x/8.x. Uso: ./sentinel-up.sh [BASE_DIR]
# Nota: se manca il binario 'redis-sentinel', sostituiscilo con
#       'redis-server <conf> --sentinel'.
set -euo pipefail
BASE_DIR="${1:-$HOME/redis-lab/sentinel}"
mkdir -p "$BASE_DIR"

echo ">> Master 6379 + replica 6380/6381"
redis-server --port 6379 --dir "$BASE_DIR" --dbfilename m.rdb \
  --daemonize yes --logfile "$BASE_DIR/m.log"
for p in 6380 6381; do
  redis-server --port "$p" --dir "$BASE_DIR" --dbfilename "r$p.rdb" \
    --replicaof 127.0.0.1 6379 --daemonize yes --logfile "$BASE_DIR/r$p.log"
done

echo ">> Attendo la sincronizzazione delle replica..."
for i in $(seq 1 15); do
  st=$(redis-cli -p 6380 info replication | awk -F: '/master_link_status/{print $2}' | tr -d '\r')
  [ "$st" = "up" ] && break; sleep 1
done
echo "   master_link_status(6380)=$st"

echo ">> 3 Sentinel (26379/26380/26381), quorum 2"
for p in 26379 26380 26381; do
  cat > "$BASE_DIR/sentinel-$p.conf" <<CONF
port $p
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
CONF
  redis-sentinel "$BASE_DIR/sentinel-$p.conf" --daemonize yes \
    --logfile "$BASE_DIR/sentinel-$p.log"
done
sleep 2
echo ">> Master secondo Sentinel:"
redis-cli -p 26379 sentinel get-master-addr-by-name mymaster
echo ">> Pronto. Prova un failover con:  redis-cli -p 6379 shutdown nosave"
