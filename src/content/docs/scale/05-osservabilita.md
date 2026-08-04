---
title: "Scale · 05 · Osservabilità"
description: "INFO, SLOWLOG, LATENCY, MEMORY, --bigkeys, exporter Prometheus e le soglie che contano davvero."
---

Un'istanza che non sai osservare non è in produzione, è in speranza. Questa
unità costruisce la catena diagnostica completa.

Prerequisito: istanza di lab su 6379 avviata con `--enable-debug-command yes`.

---

## Esercizio 5.1 — `INFO` come fonte primaria

```bash
redis-cli INFO server      | grep -E 'redis_version|uptime_in_days|config_file'
redis-cli INFO clients     | grep -E 'connected_clients|blocked_clients|maxclients'
redis-cli INFO memory      | grep -E 'used_memory_human|used_memory_rss_human|maxmemory_human|mem_fragmentation_ratio'
redis-cli INFO persistence | grep -E 'rdb_last_bgsave_status|aof_last_write_status|loading'
redis-cli INFO stats       | grep -E 'instantaneous_ops_per_sec|keyspace_hits|keyspace_misses|evicted_keys|expired_keys|rejected_connections|latest_fork_usec'
redis-cli INFO replication | grep -E 'role|connected_slaves|master_link_status'
```

Hit ratio calcolato al volo:

```bash
redis-cli INFO stats | awk -F: '/keyspace_hits/{h=$2} /keyspace_misses/{m=$2} END{printf "hit ratio: %.2f%%\n", h/(h+m)*100}'
```

**Verifica:** su una cache un hit ratio sotto il 70–80% significa che il dataset
non ci sta in memoria o che il TTL è troppo aggressivo. Su un data store, l'hit
ratio non è una metrica significativa: sapere quale dei due casi hai davanti è
il prerequisito di ogni allerta.

---

## Esercizio 5.2 — SLOWLOG

```bash
redis-cli CONFIG GET slowlog-log-slower-than slowlog-max-len
redis-cli CONFIG SET slowlog-log-slower-than 1000     # µs, quindi 1 ms
redis-cli SLOWLOG RESET
redis-cli DEBUG SLEEP 0.1
redis-cli SLOWLOG GET 1
redis-cli SLOWLOG LEN
```

**Output misurato:**

```
1                       # id
1785845406              # timestamp
100196                  # durata in microsecondi
DEBUG SLEEP 0.1         # comando
127.0.0.1:60992         # client
```

**Verifica:** la soglia è in **microsecondi**, non millisecondi — l'errore più
comune è impostare 10000 credendo di dire 10 s quando si stanno dicendo 10 ms.
Lo slowlog vive in memoria e si perde al restart: se ti serve storico, scrapalo.

Comandi da cercare in uno slowlog reale: `KEYS`, `FLUSHALL`, `SMEMBERS` su set
enormi, `HGETALL` su hash da milioni di campi, script Lua lunghi.

---

## Esercizio 5.3 — LATENCY monitor

```bash
redis-cli CONFIG GET latency-monitor-threshold
redis-cli CONFIG SET latency-monitor-threshold 100    # ms
redis-cli LATENCY RESET
redis-cli DEBUG SLEEP 0.3
redis-cli LATENCY LATEST
redis-cli LATENCY HISTORY command
redis-cli LATENCY DOCTOR
```

**Output misurato:**

```
command  1785845406  300  300
```
```
1. command: 1 latency spikes (average 300ms, mean deviation 0ms, period 1.00 sec).
   Worst all time event 300ms.
```

**Verifica:** il monitor è **disattivato di default**
(`latency-monitor-threshold 0`) — se non lo abiliti, `LATENCY LATEST` restituisce
sempre vuoto e ti convinci che non ci siano spike. Attivarlo a 100 ms su tutta
la flotta è a costo trascurabile e ti dà l'evento quando serve.

Gli eventi che vedrai in produzione: `command`, `fork`, `aof-fsync-always`,
`expire-cycle`, `eviction-del`. Ognuno punta a una causa diversa.

---

## Esercizio 5.4 — Memoria e chiavi patologiche

```bash
redis-cli INFO memory | grep -E 'used_memory_human|used_memory_rss_human|used_memory_peak_human|mem_fragmentation_ratio|mem_allocator'
redis-cli MEMORY DOCTOR
redis-cli MEMORY STATS | head -20
redis-cli MEMORY USAGE <chiave>
```

Scansione delle chiavi grandi — **safe in produzione**, usa `SCAN` non `KEYS`:

```bash
redis-cli --bigkeys
redis-cli --memkeys        # ordina per memoria occupata
redis-cli --hotkeys        # richiede maxmemory-policy allkeys-lfu
```

**Verifica:**

- `mem_fragmentation_ratio` > 1.5 → frammentazione; valuta
  `activedefrag yes`.
- `mem_fragmentation_ratio` < 1.0 → **il processo sta swappando**: è
  un'emergenza, non un tuning.
- `used_memory_rss` molto sopra `used_memory` con ratio alto e `maxmemory`
  vicino → il prossimo `BGSAVE` può innescare l'OOM killer.

Eviction:

```bash
redis-cli CONFIG GET maxmemory maxmemory-policy
redis-cli INFO stats | grep -E 'evicted_keys|expired_keys'
```

`maxmemory 0` (default) su un'istanza usata come cache significa: nessun limite,
crescita fino all'OOM del kernel. Su ogni istanza cache va impostato
`maxmemory` (tipicamente 60–70% della RAM del nodo, per lasciare spazio al fork)
più una policy `allkeys-lru` o `allkeys-lfu`.

---

## Esercizio 5.5 — Monitoraggio live

```bash
redis-cli --stat              # una riga al secondo: keys, mem, clients, ops
redis-cli --latency-history   # serie di latenza nel tempo
redis-cli --latency-dist      # distribuzione (spettro)
redis-cli MONITOR             # ogni comando, in tempo reale
```

:::caution[`MONITOR` costa]
`MONITOR` replica **ogni** comando verso il tuo client: su un'istanza carica può
degradare il throughput in modo misurabile. Usalo per pochi secondi, mai in uno
script di monitoring, e mai lasciato aperto in una sessione dimenticata.
:::

---

## Esercizio 5.6 — Esporre le metriche a Prometheus

```bash
# redis_exporter, binario singolo, nessuna dipendenza
REDIS_ADDR=redis://127.0.0.1:6379 ./redis_exporter --web.listen-address=:9121 &
curl -s localhost:9121/metrics | grep -E '^redis_(up|connected_clients|memory_used_bytes|commands_processed_total|rejected_connections_total)'
```

Regole di allerta minime, in ordine di priorità:

| Allerta | Espressione | Perché |
|---|---|---|
| Istanza giù | `redis_up == 0` | ovvio, ma va scritta |
| Replica rotta | `redis_master_link_up == 0` | HA compromessa in silenzio |
| Connessioni rifiutate | `rate(redis_rejected_connections_total[5m]) > 0` | saturazione `maxclients` |
| Memoria | `redis_memory_used_bytes / redis_memory_max_bytes > 0.85` | eviction imminente |
| Swap | `redis_mem_fragmentation_ratio < 1` | il processo sta swappando |
| Persistenza | `redis_rdb_last_bgsave_status == 0` | backup non funzionante |
| Fork lento | `redis_latest_fork_usec > 500000` | spike di latenza da snapshot |

**Verifica:** l'allerta che manca quasi sempre è `master_link_up`. Una replica
scollegata non genera errori applicativi: te ne accorgi al failover, quando è
tardi.

---

## Esercizio 5.7 — La catena diagnostica completa

Da eseguire in ordine quando arriva "Redis è lento":

```bash
redis-cli PING                                    # 1. risponde?
redis-cli --intrinsic-latency 5                   # 2. è l'host?
redis-cli --latency                               # 3. è la rete?
redis-cli SLOWLOG GET 10                          # 4. sono i comandi?
redis-cli LATENCY LATEST                          # 5. sono gli eventi interni?
redis-cli INFO memory | grep fragmentation        # 6. è la memoria/swap?
redis-cli INFO stats | grep -E 'rejected|evicted' # 7. è la saturazione?
redis-cli INFO replication | grep master_link     # 8. è la replica?
```

Otto comandi, otto ipotesi escluse o confermate. Questa sequenza è il contenuto
del runbook di primo livello.

---

## Domande di verifica

1. `LATENCY LATEST` è vuoto su un'istanza con spike evidenti. Perché?
2. `mem_fragmentation_ratio` è 0.7. Cosa fai per primo?
3. `slowlog-log-slower-than 10000`: quale soglia hai impostato davvero?
4. Quale singola allerta rileva un'HA rotta prima del failover?

Prossimo passo: [06 · Capstone](/scale/06-capstone/).
