---
title: "Scale · 06 · Memoria e tuning"
description: "Encoding e soglie listpack, maxmemory e policy di eviction, frammentazione e activedefrag, fork e impostazioni del kernel, lazy free."
---

Redis è un database in memoria: la memoria non è una risorsa da monitorare, è
**la** risorsa. Questa unità è quella con il miglior rapporto tra sforzo e
risparmio: le soglie di encoding da sole valgono più di qualunque altro tuning.

Prerequisito: istanza di lab su 6379.

---

## Esercizio 6.1 — Dove va la memoria

```bash
redis-cli INFO memory | grep -E 'used_memory_human|used_memory_rss_human|used_memory_peak_human|used_memory_lua|used_memory_dataset|maxmemory_human|maxmemory_policy|mem_fragmentation_ratio|mem_allocator'
redis-cli MEMORY STATS | head -30
```

Le voci che contano:

| Voce | Cosa misura |
|---|---|
| `used_memory` | quanto ha allocato Redis (visione dell'allocatore) |
| `used_memory_rss` | quanto vede il sistema operativo |
| `used_memory_dataset` | i soli dati, al netto dell'overhead |
| `used_memory_peak` | il picco storico — è questo che dimensiona il nodo |
| `mem_fragmentation_ratio` | `rss / used_memory` |

**Verifica:** dimensiona sempre sul **picco**, non sul valore corrente. Il picco
include l'overhead del fork durante il `BGSAVE`, ed è il numero che determina se
il nodo va in OOM alle 3 di notte.

---

## Esercizio 6.2 — Encoding: il tuning che rende di più

Redis usa rappresentazioni compatte (`listpack`, `intset`) finché la collezione
resta sotto una soglia, poi passa a strutture con puntatori (`hashtable`,
`skiplist`) molto più costose in memoria.

```bash
redis-cli CONFIG GET hash-max-listpack-entries hash-max-listpack-value \
  zset-max-listpack-entries set-max-intset-entries list-max-listpack-size
```

**Default misurati (Redis 7.0):**

```
hash-max-listpack-entries   512
hash-max-listpack-value     64
zset-max-listpack-entries   128
set-max-intset-entries      512
list-max-listpack-size      -2      (negativo = limite per dimensione, non per numero)
```

Osserva la conversione:

```bash
{ for i in $(seq 1 600); do echo "HSET h3 f$i v$i"; done; } | redis-cli --pipe
redis-cli OBJECT ENCODING h3
redis-cli MEMORY USAGE h3

redis-cli CONFIG SET hash-max-listpack-entries 1000
{ for i in $(seq 1 600); do echo "HSET h4 f$i v$i"; done; } | redis-cli --pipe
redis-cli OBJECT ENCODING h4
redis-cli MEMORY USAGE h4
```

**Output misurato:**

```
h3  600 campi, soglia 512   -> hashtable    32296 byte
h4  600 campi, soglia 1000  -> listpack      7216 byte
```

**4,5× di memoria in meno** con lo stesso identico dato, cambiando un parametro.

:::caution[Il prezzo]
Il `listpack` è una struttura lineare: l'accesso a un campo è **O(n)**. Alzare
le soglie oltre qualche migliaio di elementi scambia memoria con CPU e latenza.
Regola pratica: alza la soglia fino a coprire il 95° percentile della
cardinalità reale delle tue collezioni, mai "il più possibile".
:::

Encoding degli insiemi:

```bash
redis-cli DEL s; redis-cli SADD s 1 2 3; redis-cli OBJECT ENCODING s   # intset
redis-cli SADD s ciao;                   redis-cli OBJECT ENCODING s   # hashtable
```

**Verifica:** un solo elemento non numerico fa perdere l'`intset` all'intero
set. Se un'applicazione mescola id numerici e stringhe nello stesso set, il
costo in memoria esplode: è un finding da girare agli AM con il numero in mano
(`MEMORY USAGE` prima e dopo).

:::note[Versioni]
`set-max-listpack-entries` (listpack anche per i set di stringhe) esiste da
Redis 7.2. Su 7.0 il `CONFIG GET` non restituisce nulla per quel parametro.
Prima di 7.0 le stesse strutture si chiamavano `ziplist`: i nomi dei parametri
erano `hash-max-ziplist-entries` e simili, oggi mantenuti come alias.
:::

---

## Esercizio 6.3 — `maxmemory` e le policy di eviction

```bash
redis-cli FLUSHALL
redis-cli CONFIG SET maxmemory 3mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
{ for i in $(seq 1 40000); do echo "SET big:$i payloadpayloadpayloadpayload$i"; done; } | redis-cli --pipe
redis-cli INFO stats  | grep evicted_keys
redis-cli DBSIZE
redis-cli INFO memory | grep -E 'used_memory_human|maxmemory_human'
```

**Output misurato:**

```
evicted_keys:23231
DBSIZE:16549
used_memory_human:3.00M
maxmemory_human:3.00M
```

Redis ha scritto tutte le 40000 chiavi, ne ha sfrattate 23231 e si è **fermato
esattamente sul limite**. Nessun errore lato client: il comportamento corretto
per una cache.

Ora la stessa prova con la policy di default:

```bash
redis-cli CONFIG SET maxmemory-policy noeviction
{ for i in $(seq 1 20000); do echo "SET oom:$i payloadpayloadpayload$i"; done; } | redis-cli --pipe
```

**Output misurato:**

```
errors: 19999, replies: 20000
OOM command not allowed when used memory > 'maxmemory'.
```

**Verifica:** questa è la differenza tra una cache e un data store, e si decide
con un solo parametro.

| Uso | `maxmemory-policy` | Effetto al limite |
|---|---|---|
| Cache | `allkeys-lru` / `allkeys-lfu` | sfratta le chiavi meno usate, il servizio continua |
| Data store | `noeviction` | rifiuta le scritture con `OOM`, nessun dato perso |
| Sessioni con TTL | `volatile-lru` / `volatile-ttl` | sfratta solo le chiavi con TTL |

:::caution[`volatile-*` senza TTL]
Con una policy `volatile-*`, se le chiavi **non hanno TTL** Redis non ha niente
da sfrattare e si comporta come `noeviction`: errori `OOM` su un'istanza che
credevi fosse una cache. Verifica prima:

```bash
redis-cli --scan --count 1000 | head -100 | while read k; do redis-cli TTL "$k"; done | sort | uniq -c
```
(`-1` = nessun TTL)
:::

`maxmemory 0` è il default: **nessun limite**, crescita fino all'OOM killer del
kernel. Su ogni istanza cache va impostato esplicitamente.

---

## Esercizio 6.4 — Frammentazione e defrag attivo

```bash
redis-cli INFO memory | grep -E 'mem_fragmentation_ratio|mem_allocator'
redis-cli MEMORY DOCTOR
redis-cli CONFIG GET activedefrag active-defrag-threshold-lower active-defrag-ignore-bytes active-defrag-cycle-min
```

Interpretazione — l'unica tabella da ricordare:

| `mem_fragmentation_ratio` | Significato | Azione |
|---|---|---|
| ~1.0–1.4 | normale | nessuna |
| > 1.5 | frammentazione reale | valuta `activedefrag yes` |
| < 1.0 | **il processo sta swappando** | emergenza: RAM insufficiente |
| molto alto su istanza quasi vuota | falso positivo | l'overhead fisso domina |

```bash
redis-cli CONFIG SET activedefrag yes        # richiede allocatore jemalloc
redis-cli INFO memory | grep active_defrag
```

**Verifica:** `activedefrag` funziona solo con jemalloc (`mem_allocator:jemalloc`,
il default nei build ufficiali). Costa CPU: il defrag gira sul thread
principale, quindi va acceso con `active-defrag-cycle-min` basso e verificato
sullo slowlog.

---

## Esercizio 6.5 — Il fork, la RAM e il kernel

Il punto che manda in OOM i nodi: `BGSAVE` e `BGREWRITEAOF` fanno `fork()`, e le
pagine modificate durante lo snapshot vengono copiate.

```bash
redis-cli INFO stats | grep latest_fork_usec
cat /proc/meminfo | grep -E 'MemTotal|MemAvailable|Committed_AS'
sysctl vm.overcommit_memory vm.swappiness
cat /sys/kernel/mm/transparent_hugepage/enabled
```

**Output misurato su un host non preparato:**

```
vm.overcommit_memory = 0
vm.swappiness = 60
always [madvise] never        <- THP attive
```

Tutte e tre le impostazioni sono sbagliate per Redis. Correzione persistente:

```bash
cat > /etc/sysctl.d/99-redis.conf <<'EOF'
vm.overcommit_memory = 1
vm.swappiness = 1
net.core.somaxconn = 1024
EOF
sysctl --system
```

```bash
# THP: latenza del fork fino a 10x. Disattivare, in modo persistente.
echo never > /sys/kernel/mm/transparent_hugepage/enabled
```

Su RHEL, in modo che sopravviva al reboot:

```bash
grubby --update-kernel=ALL --args="transparent_hugepage=never"
# oppure una unit systemd che scrive il valore prima di redis.service
```

**Verifica:** con `vm.overcommit_memory = 0` il `fork()` può **fallire** quando
`used_memory` supera metà della RAM libera, e il `BGSAVE` non parte:
`rdb_last_bgsave_status:err` senza altri sintomi. È la causa più comune di
backup silenziosamente assenti.

Regola di sizing: `maxmemory` ≈ **60–70%** della RAM del nodo. Il resto serve al
fork, al buffer di replica e all'output buffer dei client.

---

## Esercizio 6.6 — Lazy free

La cancellazione di una chiave enorme è sincrona per default: blocca l'istanza
per tutto il tempo della `free()`.

```bash
redis-cli CONFIG GET lazyfree-lazy-eviction lazyfree-lazy-expire \
  lazyfree-lazy-server-del lazyfree-lazy-user-del replica-lazy-flush
```

**Default misurati: tutti `no`.** Attivali su istanze con collezioni grandi:

```bash
for p in lazyfree-lazy-eviction lazyfree-lazy-expire lazyfree-lazy-server-del lazyfree-lazy-user-del replica-lazy-flush; do
  redis-cli CONFIG SET $p yes
done
```

Equivalente puntuale, senza cambiare la configurazione:

```bash
redis-cli UNLINK chiave-enorme      # asincrono, invece di DEL
redis-cli FLUSHALL ASYNC
```

**Verifica:** con `lazyfree-lazy-expire no`, la scadenza simultanea di molte
chiavi grandi produce spike visibili in `LATENCY HISTORY expire-cycle`. È il
sospettato numero uno quando la latenza ha picchi periodici senza carico
corrispondente.

---

## Esercizio 6.7 — Memoria dei client (Redis 7+)

```bash
redis-cli CONFIG GET maxmemory-clients
redis-cli CLIENT NO-EVICT on          # esenta il tuo client di ops dall'eviction
redis-cli INFO clients | grep -E 'client_recent_max_output_buffer|client_recent_max_input_buffer'
```

`maxmemory-clients` (default `0` = disattivato) limita la memoria **complessiva**
dei buffer client e sfratta le connessioni più esose invece di far crescere
`used_memory` fino all'OOM. Valore ragionevole: `5%` o un valore assoluto.
Ricordati di esentare le connessioni di monitoraggio e le replica.

---

## Esercizio 6.8 — Trovare cosa occupa la memoria

```bash
redis-cli --bigkeys                 # la chiave più grande per tipo, via SCAN
redis-cli --memkeys                 # ordinamento per memoria occupata
redis-cli --memkeys-samples 0       # campionamento esatto (più lento)
redis-cli MEMORY USAGE <chiave> SAMPLES 0
```

Distribuzione per prefisso — il comando che serve davvero per parlare con gli AM:

```bash
redis-cli --scan --count 1000 | awk -F: '{print $1}' | sort | uniq -c | sort -rn | head -20
```

**Verifica:** tutti usano `SCAN` sotto il cofano, quindi sono sicuri in
produzione. `KEYS *` no: è O(n) sul thread principale e su milioni di chiavi
congela l'istanza per secondi. Se lo trovi in uno slowlog, è un finding da
change immediato.

---

## Checklist del modulo

- [ ] `maxmemory` impostato (mai 0 su una cache), a ~60–70% della RAM del nodo
- [ ] `maxmemory-policy` coerente con l'uso (cache vs data store)
- [ ] con policy `volatile-*`, verificato che le chiavi abbiano davvero un TTL
- [ ] soglie di encoding tarate sul 95° percentile delle collezioni reali
- [ ] `mem_fragmentation_ratio` monitorato, con allerta separata per `< 1.0`
- [ ] THP disattivate in modo persistente
- [ ] `vm.overcommit_memory = 1`, `vm.swappiness = 1`
- [ ] `lazyfree-*` attivi se esistono collezioni grandi
- [ ] `used_memory_peak` usato per il sizing, non `used_memory`

---

## Domande di verifica

1. Stesso hash da 600 campi, 32 KB in un caso e 7 KB nell'altro. Cosa è
   cambiato e cosa hai pagato in cambio?
2. Policy `volatile-lru` e istanza che risponde `OOM`. Qual è la causa?
3. `mem_fragmentation_ratio` a 0.7: `activedefrag` risolve?
4. `rdb_last_bgsave_status:err` con disco libero e permessi corretti. Quale
   parametro del kernel guardi?

Prossimo passo: [07 · Capstone](/scale/07-capstone/).
