---
title: "Scale · 03 · Alta disponibilità"
description: "Replica asincrona, WAIT, Sentinel con quorum, failover manuale e automatico, split brain e min-replicas."
---

Costruiamo da zero 1 master + 2 replica + 3 Sentinel, e proviamo il failover in
entrambe le direzioni. Tutti i flussi di questa pagina sono stati eseguiti e
verificati.

---

## Esercizio 3.1 — Replica

```bash
mkdir -p ~/redis-lab/ha && cd ~/redis-lab/ha
redis-server --port 6379 --dir ~/redis-lab/ha --dbfilename m.rdb \
  --daemonize yes --logfile m.log
for p in 6380 6381; do
  redis-server --port $p --dir ~/redis-lab/ha --dbfilename r$p.rdb \
    --replicaof 127.0.0.1 6379 --daemonize yes --logfile r$p.log
done
```

Attendi la sincronizzazione — **con un'attesa condizionata, non con `sleep`**:

```bash
for i in $(seq 1 15); do
  st=$(redis-cli -p 6380 INFO replication | awk -F: '/master_link_status/{print $2}' | tr -d '\r')
  [ "$st" = "up" ] && break; sleep 1
done; echo "master_link_status(6380)=$st"
```

```bash
redis-cli -p 6379 INFO replication | grep -E 'role|connected_slaves|slave0'
```

**Output atteso:**

```
role:master
connected_slaves:2
slave0:ip=127.0.0.1,port=6380,state=online,offset=0,lag=0
```

**Verifica:** `state=online` e `lag` basso. Un `lag` che cresce indica replica
che non sta dietro (rete, disco o `client-output-buffer-limit replica` troppo
stretto).

---

## Esercizio 3.2 — La replica è asincrona: dimostrarlo

```bash
redis-cli -p 6379 SET chiave valore
redis-cli -p 6380 GET chiave              # già presente in loopback
redis-cli -p 6379 WAIT 2 100              # quante replica hanno confermato entro 100 ms
```

**Verifica:** `WAIT numreplicas timeout` restituisce il numero di replica che
hanno acknowledgeato. Non è una transazione distribuita: se restituisce meno di
`numreplicas`, la scrittura resta comunque committata sul master. È una
**misura**, non una garanzia.

Protezione reale contro le scritture su un master isolato:

```bash
redis-cli -p 6379 CONFIG SET min-replicas-to-write 1
redis-cli -p 6379 CONFIG SET min-replicas-max-lag 10
```

Con queste, il master **rifiuta le scritture** se non ha almeno 1 replica con
lag < 10 s. È il freno che evita di accumulare dati che il failover butterà via.

---

## Esercizio 3.3 — Full sync vs partial sync

```bash
redis-cli -p 6379 INFO stats | grep -E 'sync_full|sync_partial_ok|sync_partial_err'
redis-cli -p 6379 CONFIG GET repl-backlog-size repl-backlog-ttl
```

Simula una disconnessione breve:

```bash
redis-cli -p 6380 REPLICAOF NO ONE
sleep 3
redis-cli -p 6380 REPLICAOF 127.0.0.1 6379
sleep 2
redis-cli -p 6379 INFO stats | grep -E 'sync_full|sync_partial_ok'
```

**Verifica:** una riconnessione entro la finestra di backlog produce una
**partial sync** (`sync_partial_ok` +1). Se invece incrementa `sync_full`, il
backlog era troppo piccolo per il volume di scritture: alza
`repl-backlog-size`. In produzione le full sync ripetute sono devastanti —
ogni full sync è un `BGSAVE` sul master più il trasferimento dell'intero
dataset.

---

## Esercizio 3.4 — Sentinel

```bash
cd ~/redis-lab/ha
for p in 26379 26380 26381; do
cat > s$p.conf <<EOF
port $p
dir /tmp
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
daemonize yes
logfile $HOME/redis-lab/ha/sent$p.log
EOF
redis-sentinel s$p.conf
done
sleep 3
redis-cli -p 26379 SENTINEL master mymaster | head -6
redis-cli -p 26379 SENTINEL ckquorum mymaster
```

**Output atteso:**

```
OK 3 usable Sentinels. Quorum and failover authorization can be reached
```

**Verifica:** il quorum (2) serve a **dichiarare** il master down; per
autorizzare il failover serve la maggioranza dei Sentinel (2 su 3). Con 2 soli
Sentinel e quorum 1 hai lo split brain garantito: **sempre dispari, sempre ≥ 3,
su fault domain diversi**.

:::caution[Il file di configurazione è mutabile]
Sentinel **riscrive** il proprio file di configurazione a ogni cambio di
topologia. Non versionarlo come immutabile e non distribuirlo con Ansible in
modalità `template` senza escludere le righe generate (`sentinel known-replica`,
`sentinel current-epoch`, `myid`).
:::

---

## Esercizio 3.5 — Failover manuale

```bash
redis-cli -p 26379 SENTINEL failover mymaster
sleep 12
redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
for p in 6379 6380 6381; do
  echo -n "$p: "; redis-cli -p $p INFO replication | awk -F: '/^role/{print $2}' | tr -d '\r'
done
```

**Output misurato:**

```
127.0.0.1
6381
6379: slave
6380: slave
6381: master
```

**Verifica:** il vecchio master (6379) è stato **riconfigurato come replica**
del nuovo, non spento. È il comportamento corretto: chi torna su dopo un
failover non deve mai ripresentarsi come master.

---

## Esercizio 3.6 — Failover automatico

```bash
MASTER_PORT=$(redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster | tail -1)
PID=$(pgrep -a redis-server | grep ":$MASTER_PORT" | awk '{print $1}')
echo "uccido il master $MASTER_PORT (pid $PID)"
kill -9 "$PID"
```

Osserva l'elezione in tempo reale:

```bash
tail -f ~/redis-lab/ha/sent26379.log     # +sdown, +odown, +vote, +switch-master
```

```bash
sleep 12
redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

**Verifica:** la sequenza nei log è `+sdown` (un Sentinel lo vede giù) →
`+odown` (raggiunto il quorum) → `+vote` → `+switch-master`. Il tempo totale è
circa `down-after-milliseconds` + elezione. Se ti serve un RTO più stretto
abbassi `down-after-milliseconds`, ma sotto ~3 s inizi a generare failover
spuri su reti con jitter.

:::caution[`pgrep -f` che si autouccide]
Se cerchi il pid con `pgrep -f "port 6379"` da uno script, il pattern può
matchare la shell che sta eseguendo il comando stesso e ti ammazzi lo script.
Usa una classe di caratteri: `pgrep -f "[p]ort 6379"`.
:::

---

## Esercizio 3.7 — Il client deve essere Sentinel-aware

```bash
redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
redis-cli -p 26379 SENTINEL replicas mymaster | head -4
redis-cli -p 26379 SENTINEL sentinels mymaster | head -4
```

**Verifica:** questi sono esattamente i comandi che il client library esegue per
scoprire la topologia. Un'applicazione configurata con l'IP statico del master
sopravvive fino al primo failover e poi scrive su una replica → errore
`READONLY You can't write against a read only replica`. È il controllo numero
uno da fare in handover con gli AM.

Teardown:

```bash
pkill -f "[r]edis-sentinel"
for p in 6379 6380 6381; do redis-cli -p $p SHUTDOWN NOSAVE 2>/dev/null; done
rm -rf ~/redis-lab/ha
```

---

## Domande di verifica

1. Quorum 2 su 3 Sentinel: quanti ne servono per **dichiarare** il down e
   quanti per **eseguire** il failover?
2. `WAIT 2 1000` restituisce 1. La scrittura è persa?
3. `sync_full` cresce di continuo. Quale parametro guardi per primo?
4. Il vecchio master torna online dopo un failover. Cosa deve succedere e chi
   lo garantisce?

Prossimo passo: [04 · Scalabilità](/scale/04-scalabilita/).
