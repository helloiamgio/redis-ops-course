---
title: "Scale · 07 · Workload applicativi reali"
description: "Un generatore di carico che riproduce i pattern applicativi tipici — e le loro patologie — per fare tuning su qualcosa che si comporta come la produzione."
---

Fino a qui hai misurato Redis con `redis-benchmark`, che genera un carico
sintetico e uniforme. La produzione non è così: ha chiavi calde, TTL, pool mal
dimensionati, hash che crescono, endpoint che fanno `KEYS`. Questa unità mette
un'applicazione vera davanti a Redis e ti fa correggere quello che emerge.

:::note[Perimetro]
Il codice non è tuo e non lo diventerà. Il generatore serve a **produrre il
sintomo** in laboratorio, così impari a riconoscerlo in produzione e sai
esattamente quale evidenza portare all'AM. Metà delle correzioni di questa unità
sono lato server: le altre sono richieste di modifica documentate con numeri.
:::

---

## 7.0 Il generatore

Il file è nel repository: `labs/app/workload.py`. Unica dipendenza `redis-py`.

```bash
pip install redis
cd labs/app && chmod +x workload.py
python3 workload.py --help
```

| Profilo | Cosa riproduce |
|---|---|
| `sessions` | cache di sessione con TTL e accessi zipfiani |
| `nopool` | una connessione TCP nuova a ogni comando |
| `pool` | stesso carico, connessione riusata |
| `roundtrip` | comandi singoli contro pipeline |
| `bighash` | hash che supera la soglia di encoding |
| `hotkey` | tutto il traffico su una sola chiave |
| `scanner` | endpoint "dashboard" che usa `KEYS` |
| `blocking` | consumer che occupano connessioni con comandi bloccanti |

Tutti accettano `--host` e `--port`: puoi puntarli al master Sentinel
dell'[unità 03](/scale/03-alta-disponibilita/) o a un nodo del cluster
dell'[unità 04](/scale/04-scalabilita/).

---

## Esercizio 7.1 — Connessioni: il costo del mancato pooling

**Sintomo in produzione:** `total_connections_received` che cresce come le
operazioni, latenza alta senza carico sul server.

```bash
redis-cli CONFIG RESETSTAT
python3 workload.py nopool --ops 2000
redis-cli INFO stats | grep total_connections_received

redis-cli CONFIG RESETSTAT
python3 workload.py pool --ops 2000
redis-cli INFO stats | grep total_connections_received
```

**Output misurato:**

```
2000 comandi senza pool in 2.41s (830/s)
2000 comandi con pool  in 0.13s (15941/s)
```

**19× di differenza** con lo stesso identico server. Il costo è tutto nel
`connect()`/`close()`.

**Diagnosi lato server** — come lo riconosci senza vedere il codice:

```bash
redis-cli INFO stats | awk -F: '/total_connections_received/{c=$2} /total_commands_processed/{n=$2} END{printf "comandi per connessione: %.1f\n", n/c}'
```

**Verifica:** un valore vicino a 1 significa una connessione per comando →
nessun pool. Un'applicazione sana ha migliaia di comandi per connessione. Questo
singolo rapporto è l'evidenza da portare all'AM: non richiede accesso al codice
e non è opinabile.

---

## Esercizio 7.2 — Round trip: pipeline sullo stesso lavoro

```bash
python3 workload.py roundtrip --ops 5000
```

**Output misurato:**

```
singoli : 0.33s (15358/s)
pipeline: 0.06s (88278/s)
speedup : 5.7x
```

**Verifica:** in loopback il guadagno è 5,7×. Su rete reale con RTT di 0,5 ms lo
stesso test dà uno o due ordini di grandezza, perché il round trip domina.
Rifai la prova puntando il generatore a un host remoto (`--host`) e confronta:
è il numero che chiude la discussione quando l'applicazione fa N chiamate
singole in un ciclo.

Nota che il server non è mai stato il collo di bottiglia: `INFO stats` mostra le
stesse `instantaneous_ops_per_sec` di picco in entrambi i casi.

---

## Esercizio 7.3 — Cache di sessione: hit ratio e dimensionamento

```bash
redis-cli FLUSHALL
redis-cli CONFIG RESETSTAT
python3 workload.py sessions --ops 8000 --keyspace 20000 --ttl 300
redis-cli INFO stats | grep -E 'keyspace_hits|keyspace_misses'
redis-cli DBSIZE
redis-cli INFO memory | grep used_memory_human
```

**Output misurato (cache fredda):**

```
hit ratio applicativo: 79.5%
keyspace_hits:6370   keyspace_misses:1637
DBSIZE: 1637         used_memory_human: 1.69M
```

Rilancia lo stesso comando senza svuotare:

```
hit ratio applicativo: 86.6%
```

**Verifica:** la cache si scalda e il hit ratio sale. Da qui ricavi il
dimensionamento reale, che è l'unico modo onesto di rispondere a "quanta RAM
serve?":

```bash
redis-cli INFO memory | awk -F: '/used_memory:/{m=$2} END{print "byte totali:", m}'
redis-cli DBSIZE
# byte per chiave = used_memory / DBSIZE, poi moltiplica per il keyspace atteso
```

Con `--value-size` e `--keyspace` riproduci il profilo del cliente e ottieni una
stima misurata invece che dichiarata.

**Tuning da applicare e rimisurare:**

```bash
redis-cli CONFIG SET maxmemory 2mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
python3 workload.py sessions --ops 8000 --keyspace 20000
redis-cli INFO stats | grep -E 'evicted_keys|keyspace_hits|keyspace_misses'
```

Osserva il hit ratio scendere man mano che l'eviction morde: è la curva che
giustifica la richiesta di RAM.

---

## Esercizio 7.4 — L'hash che supera la soglia

**Sintomo in produzione:** la memoria salta di colpo senza che il numero di
chiavi cambi in proporzione.

```bash
python3 workload.py bighash --fields 700 --step 100
```

**Output misurato:**

```
   100 campi  listpack      2096 byte
   200 campi  listpack      5168 byte
   300 campi  listpack      7216 byte
   400 campi  listpack     10288 byte
   500 campi  listpack     12336 byte
   600 campi  hashtable    41896 byte   <-- CONVERSIONE
   700 campi  hashtable    47496 byte
```

**Verifica:** attraversando `hash-max-listpack-entries` (512) la stessa
collezione passa da 12 KB a 42 KB — **3,4× di colpo**, per 100 campi in più.
Moltiplicalo per un milione di hash e hai l'incidente di capacità.

Correzione lato server, se il 95° percentile della cardinalità reale lo
giustifica:

```bash
redis-cli CONFIG SET hash-max-listpack-entries 1000
python3 workload.py bighash --fields 700 --step 100
```

Il costo è l'accesso O(n) sul listpack: verifica sempre il contro-effetto con
`redis-cli --latency` mentre il carico gira. Se le collezioni sono grandi *e*
accedute per campo singolo, la soglia va lasciata bassa e la correzione è di
data modeling (spezzare l'hash) — richiesta all'AM, con questo output allegato.

---

## Esercizio 7.5 — `KEYS` in un endpoint

**Sintomo in produzione:** picchi di latenza su tutta l'istanza a intervalli
regolari, correlati con l'apertura di una dashboard.

```bash
{ for i in $(seq 1 500000); do echo "SET session:$i x"; done; } | redis-cli --pipe
redis-cli CONFIG SET slowlog-log-slower-than 10000
redis-cli SLOWLOG RESET
python3 workload.py scanner
redis-cli SLOWLOG GET 5
```

**Output misurato su 500.000 chiavi:**

```
KEYS  -> 500000 chiavi in 1207.6 ms
SCAN  -> 500000 chiavi in  936.0 ms
```

E nello slowlog:

```
161197   KEYS  session:*
```

**Verifica:** il dato che conta non è il tempo totale (`SCAN` è persino più
veloce end-to-end), è che **`KEYS` ha tenuto il thread principale occupato per
161 ms**. In quei 161 ms *nessun altro client* è stato servito: con 20.000 ops/s
significa 3.200 richieste in coda. `SCAN` non compare affatto nello slowlog
perché ogni iterazione dura microsecondi.

```bash
redis-cli SLOWLOG GET 10 | grep -c SCAN     # 0
```

Non esiste un tuning che salvi da `KEYS`: la correzione è applicativa. La tua
parte è produrre questa evidenza e, nel frattempo, mitigare:

```bash
redis-cli ACL SETUSER app on '>password' '~*' '+@all' '-keys' '-flushall' '-flushdb'
```

Una ACL che rimuove `KEYS` all'utenza applicativa è una mitigazione legittima e
tracciabile — da concordare in change, non da applicare a sorpresa.

---

## Esercizio 7.6 — Comandi bloccanti e saturazione delle connessioni

**Sintomo in produzione:** `connected_clients` alto e stabile, `blocked_clients`
altrettanto, nuove connessioni rifiutate.

```bash
redis-cli CONFIG SET maxclients 15
redis-cli CONFIG RESETSTAT
python3 workload.py blocking --workers 25 --seconds 4
redis-cli CONFIG SET maxclients 10000
```

**Output misurato:**

```
worker 18: ConnectionError: max number of clients reached
worker 20: ConnectionError: max number of clients reached
connected_clients=4  blocked_clients=3
rejected_connections=113
```

**Verifica:** ogni worker in `BLPOP` occupa una connessione per **tutta la
durata del blocco**, e quella connessione non torna nel pool. Il conto delle
connessioni va quindi fatto così:

```
connessioni ≈ (istanze × pool_size) + (worker bloccanti) + (connessioni pub/sub)
```

I due addendi finali sono quelli che nessuno dichiara in fase di handover, e
sono la causa più frequente di `maxclients` sottodimensionato. Il numero
`rejected_connections` (113 per 25 worker, per via dei retry del client) mostra
anche l'effetto amplificatore del retry automatico: la saturazione si
auto-alimenta.

---

## Esercizio 7.7 — Hot key e hot slot

```bash
python3 workload.py hotkey --ops 5000
redis-cli --hotkeys       # richiede maxmemory-policy allkeys-lfu
```

**Output misurato:** `5000 INCR sulla stessa chiave in 0.27s (18271/s)`.

Su istanza singola una hot key non è un problema: Redis è single-thread e la
serializzazione è comunque totale. **Su cluster lo è**: tutte le operazioni
finiscono sullo stesso slot, quindi sullo stesso master, e aggiungere shard non
serve a niente.

Riproducilo sul cluster dell'unità 04:

```bash
python3 workload.py hotkey --port 7000 --ops 5000
redis-cli -p 7000 CLUSTER KEYSLOT counter:global
# poi guarda le ops solo sul nodo proprietario di quello slot:
redis-cli -p 7002 INFO stats | grep instantaneous_ops_per_sec
```

**Verifica:** il carico è concentrato su un solo nodo mentre gli altri sono a
zero. Nessun resharding può risolverlo: uno slot è indivisibile. La correzione è
applicativa (sharding della chiave, contatori locali aggregati), e la tua è
dimostrare la concentrazione con questi due comandi.

---

## Esercizio 7.8 — Il ciclo completo di tuning

Metti insieme il tutto: carico realistico, misura, correzione, rimisura.

```bash
# 1. baseline
redis-cli CONFIG RESETSTAT && redis-cli FLUSHALL
python3 workload.py sessions --ops 20000 --keyspace 50000 --value-size 500 &
redis-cli --stat            # osserva mentre gira
```

```bash
# 2. raccolta evidenze
redis-cli INFO stats | grep -E 'keyspace_|expired_|evicted_|rejected_'
redis-cli INFO memory | grep -E 'used_memory_human|used_memory_peak_human|mem_fragmentation_ratio'
redis-cli SLOWLOG GET 10
redis-cli LATENCY LATEST
redis-cli --bigkeys
```

```bash
# 3. correzioni lato server (una alla volta, rimisurando ogni volta)
redis-cli CONFIG SET maxmemory <valore-dal-sizing>
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG SET lazyfree-lazy-expire yes
redis-cli CONFIG SET hash-max-listpack-entries <dal-p95-reale>
```

Compila la tabella — è il deliverable dell'esercizio:

| Metrica | Prima | Dopo | Correzione applicata |
|---|---|---|---|
| ops/s | | | |
| hit ratio | | | |
| `used_memory_peak` | | | |
| `evicted_keys` | | | |
| slowlog: comandi > 10 ms | | | |
| `rejected_connections` | | | |

:::caution[Una alla volta]
La tentazione è applicare tutte le correzioni insieme e dichiarare vittoria. Se
lo fai non sai quale ha funzionato, e al prossimo incidente riparti da zero. Una
modifica, una misura, una riga in tabella.
:::

---

## Cosa portare all'AM

Le tre evidenze di questa unità che non richiedono accesso al codice e non sono
opinabili:

1. **Comandi per connessione** vicino a 1 → manca il connection pool
2. **`KEYS` nello slowlog** con la durata in microsecondi → quanti millisecondi
   di blocco totale dell'istanza, per ogni chiamata
3. **Concentrazione delle ops su un solo nodo del cluster** → hot slot, non
   risolvibile con resharding

Tre numeri, tre richieste di modifica. Il resto è tuning tuo.

---

## Domande di verifica

1. `total_commands_processed / total_connections_received` vale 1,3. Cosa
   deduci?
2. `SCAN` impiega più tempo di `KEYS` end-to-end. Perché lo imponi comunque?
3. Un hash passa da 12 KB a 42 KB aggiungendo 100 campi. Alzi la soglia: cosa
   verifichi subito dopo?
4. Hot key su cluster: il resharding aiuta? Perché?

Prossimo passo: [08 · Capstone](/scale/08-capstone/).
