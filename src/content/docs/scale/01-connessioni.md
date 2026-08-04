---
title: "Scale · 01 · Connessioni"
description: "Esercizi su maxclients, file descriptor, rejected_connections, CLIENT LIST/KILL/PAUSE, pipelining e socket UNIX."
---

Il livello connessione è dove finiscono la maggior parte degli incidenti "Redis è
lento". Teoria nel [modulo 13](/13-connessioni-client-tuning/); qui si esegue.

Prerequisito: istanza di lab su 6379 ([setup](/scale/00-setup/)).

---

## Esercizio 1.1 — Leggere i limiti reali

**Obiettivo:** distinguere il valore configurato dal limite effettivo.

```bash
redis-cli CONFIG GET maxclients
redis-cli CONFIG GET timeout tcp-keepalive tcp-backlog io-threads
pid=$(pgrep -o redis-server)
grep 'open files' /proc/$pid/limits
ls /proc/$pid/fd | wc -l
```

**Output atteso** (default su Ubuntu/RHEL):

```
maxclients      10000
tcp-backlog     511
tcp-keepalive   300
timeout         0
io-threads      1
```

**Verifica:** `Max open files` del processo deve essere ≥ `maxclients` + 32.
Se è inferiore, Redis abbassa `maxclients` **silenziosamente all'avvio** e lo
scrive nel log:

```bash
grep -i maxclients ~/redis-lab/single/r.log
```

---

## Esercizio 1.2 — Saturare `maxclients` e vederlo nei contatori

**Obiettivo:** produrre `rejected_connections > 0` in modo controllato e sapere
dove si legge.

```bash
mkdir -p ~/redis-lab/mc
redis-server --port 6390 --dir ~/redis-lab/mc --daemonize yes \
  --logfile r.log --maxclients 12
sleep 1
redis-cli -p 6390 CONFIG GET maxclients
```

Apri più connessioni bloccanti del consentito:

```bash
for i in $(seq 1 20); do redis-cli -p 6390 BLPOP nolist 6 >/dev/null 2>&1 & done
sleep 2
redis-cli -p 6390 INFO clients | grep -E 'connected_clients|blocked_clients'
redis-cli -p 6390 INFO stats  | grep rejected_connections
```

**Output atteso** (misurato):

```
maxclients:12
rejected_connections:10
```

**Verifica:** `rejected_connections` è un contatore **cumulativo dall'avvio**,
non un gauge. In produzione ciò che conta è la sua *derivata*: se cresce, i
client stanno sbattendo contro il limite adesso. Mettilo in allerta come
`rate(redis_rejected_connections_total[5m]) > 0`.

Teardown:

```bash
redis-cli -p 6390 SHUTDOWN NOSAVE 2>/dev/null; rm -rf ~/redis-lab/mc
```

---

## Esercizio 1.3 — Identificare chi consuma le connessioni

**Obiettivo:** dalla connessione risalire al client, e chiuderlo in modo mirato.

```bash
redis-cli CLIENT LIST
redis-cli CLIENT INFO
redis-cli CLIENT LIST TYPE normal
```

Aggregazione per IP sorgente — il comando che userai davvero in incident:

```bash
redis-cli CLIENT LIST \
| awk '{for(i=1;i<=NF;i++) if($i ~ /^addr=/){split($i,a,"="); split(a[2],b,":"); print b[1]}}' \
| sort | uniq -c | sort -rn | head
```

I client con output buffer che cresce (`omem`) sono i candidati numero uno:

```bash
redis-cli CLIENT LIST \
| awk '{for(i=1;i<=NF;i++) if($i ~ /^(id|addr|age|idle|omem|qbuf|cmd)=/) printf "%s ",$i; print ""}' \
| sort -t= -k5 -rn | head -5
```

Chiusura mirata e pausa controllata:

```bash
redis-cli CLIENT KILL ID <id>
redis-cli CLIENT KILL ADDR 127.0.0.1:12345
redis-cli CLIENT PAUSE 3000 WRITE       # blocca le sole scritture per 3 s
redis-cli CLIENT UNPAUSE
```

**Verifica:** `CLIENT KILL` restituisce il numero di connessioni chiuse. Con
`TYPE normal SKIPME yes` chiudi tutti i client applicativi tranne te stesso —
comando da incidente, non da manutenzione ordinaria.

:::caution[Differenze di versione]
`CLIENT NO-TOUCH` esiste da Redis 7.2. Su 7.0 risponde
`ERR unknown subcommand 'NO-TOUCH'`. `CLIENT NO-EVICT` è disponibile da 7.0.
:::

---

## Esercizio 1.4 — Quantificare il costo del round trip

**Obiettivo:** dimostrare con numeri che la latenza percepita è rete, non
server.

```bash
redis-cli --intrinsic-latency 3            # solo host, nessuna rete
redis-cli --latency                         # RTT client→server (Ctrl-C per uscire)
redis-benchmark -n 20000 -c 10 -t set -q
redis-benchmark -n 20000 -c 10 -t set -P 16 -q
```

**Output misurato** in loopback su un host di lab:

```
SET: 80000.00 requests per second, p50=0.079 msec      # senza pipelining
SET: 249999.98 requests per second, p50=0.295 msec     # con -P 16
```

**Verifica:** ~3× di throughput con lo stesso server e lo stesso carico. Il p50
per *richiesta* sale (la pipeline aggrega), il tempo totale crolla. È il dato
da mostrare quando un AM sostiene che "Redis è lento": se
`--intrinsic-latency` è basso e `--latency` è alto, il collo di bottiglia è
rete o client.

---

## Esercizio 1.5 — Socket UNIX e confronto

**Obiettivo:** misurare quanto costa lo stack TCP quando client e server sono
sullo stesso host.

```bash
redis-cli -s ~/redis-lab/single/redis.sock PING
redis-benchmark -s ~/redis-lab/single/redis.sock -n 20000 -c 10 -t set -q
redis-benchmark -n 20000 -c 10 -t set -q          # TCP, per confronto
```

**Verifica:** il socket UNIX è tipicamente più veloce del loopback TCP. Utile
solo in colocation (sidecar, agent sullo stesso nodo): irrilevante se il client
è su un altro host.

---

## Esercizio 1.6 — Timeout, keepalive e connessioni zombie

**Obiettivo:** capire l'interazione tra `timeout` server-side e pool client.

```bash
redis-cli CONFIG SET timeout 5
redis-cli -p 6379 --no-raw CLIENT INFO | grep -o 'age=[0-9]*'
# apri una connessione e lasciala idle
(redis-cli -p 6379 --timeout 30 SUBSCRIBE canale &) ; sleep 8
redis-cli CLIENT LIST | wc -l
redis-cli CONFIG SET timeout 0
```

**Verifica:** una connessione in `SUBSCRIBE` non è idle (riceve push), quindi
`timeout` non la chiude. Le connessioni di un pool applicativo invece sì: un
`timeout` aggressivo contro un pool persistente produce errori al primo
riutilizzo. Regola: `timeout 0` + `tcp-keepalive 300`, e il keepalive più corto
del timer idle del firewall.

---

## Domande di verifica

1. `maxclients` è 10000 ma `INFO clients` mostra `maxclients:4064`. Dove
   guardi per capire perché?
2. `rejected_connections` è a 15000 ma il servizio funziona. È un incidente?
3. Il p50 per richiesta peggiora con `-P 16`. Perché non è un problema?
4. Un client ha `omem=250mb`. Cosa sta succedendo e quale parametro lo
   limiterà?

Prossimo passo: [02 · Persistenza](/scale/02-persistenza/).
