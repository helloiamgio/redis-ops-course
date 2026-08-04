---
title: "Scale · 04 · Scalabilità"
description: "Redis Cluster da zero: hash slot, MOVED, hash tag, CROSSSLOT, resharding, rebalance, failover manuale e automatico."
---

Sei nodi, 3 master e 3 replica, 16384 slot. Ogni comando di questa pagina è
stato eseguito su un cluster reale.

---

## Esercizio 4.1 — Creare il cluster

```bash
mkdir -p ~/redis-lab/cl && cd ~/redis-lab/cl
for p in 7000 7001 7002 7003 7004 7005; do
  mkdir -p $p
  redis-server --port $p \
    --cluster-enabled yes \
    --cluster-config-file ~/redis-lab/cl/$p/nodes.conf \
    --cluster-node-timeout 5000 \
    --appendonly yes \
    --dir ~/redis-lab/cl/$p \
    --daemonize yes --logfile ~/redis-lab/cl/$p/r.log
done
sleep 2

redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1 --cluster-yes
```

```bash
redis-cli -p 7000 CLUSTER INFO | grep -E 'cluster_state|cluster_slots_ok|cluster_known_nodes|cluster_size'
```

**Output atteso a regime:**

```
cluster_state:ok
cluster_slots_ok:16384
cluster_known_nodes:6
cluster_size:3
```

:::caution[Subito dopo la create è normale vedere `fail`]
Nei primi secondi `cluster_state:fail` anche se `--cluster create` ha risposto
`[OK] All 16384 slots covered`: il gossip deve ancora convergere. Misurato:
**~10 secondi** con `cluster-node-timeout 5000`. Uno script di provisioning che
verifica lo stato immediatamente dopo la create fallisce a intermittenza — metti
un'attesa condizionata:

```bash
for i in $(seq 1 30); do
  s=$(redis-cli -p 7000 CLUSTER INFO | awk -F: '/cluster_state/{print $2}' | tr -d '\r')
  [ "$s" = ok ] && break; sleep 1
done; echo "cluster_state=$s"
```
:::

Topologia:

```bash
redis-cli -p 7000 CLUSTER NODES | awk '{split($2,a,"@"); print a[1], $3, $9}' | sort
redis-cli -p 7000 CLUSTER SHARDS | head -20
```

---

## Esercizio 4.2 — MOVED: il client deve sapere

```bash
redis-cli -p 7000 SET foo bar        # senza -c
redis-cli -c -p 7000 SET foo bar     # con -c (cluster mode)
redis-cli -p 7000 CLUSTER KEYSLOT foo
```

**Output misurato:**

```
MOVED 12182 127.0.0.1:7002
OK
12182
```

**Verifica:** un client non cluster-aware riceve `MOVED` e si ferma. `redis-cli
-c` segue il redirect. In produzione questo è **il** requisito da imporre agli
AM: la libreria deve essere cluster-aware e mantenere la slot map in cache,
altrimenti ogni comando costa due round trip.

---

## Esercizio 4.3 — Hash tag e CROSSSLOT

```bash
redis-cli -p 7000 CLUSTER KEYSLOT "{user:1}:profile"
redis-cli -p 7000 CLUSTER KEYSLOT "{user:1}:sessions"
redis-cli -c -p 7000 MSET k1 1 k2 2
redis-cli -c -p 7000 MSET "{u1}:a" 1 "{u1}:b" 2
```

**Output misurato:**

```
10778
10778
CROSSSLOT Keys in request don't hash to the same slot
OK
```

**Verifica:** solo la parte tra graffe entra nella funzione di hash, quindi le
due chiavi `{user:1}:*` finiscono nello stesso slot e i comandi multi-chiave
funzionano. Senza hash tag, `MSET`/`MGET`/transazioni/Lua su più chiavi
falliscono con `CROSSSLOT`.

:::caution[Il rovescio della medaglia]
Hash tag troppo grossolani (es. `{tenant}`) concentrano un tenant intero su un
solo slot → **hot slot**, impossibile da bilanciare con il resharding. È una
decisione di data modeling che ricade sull'infrastruttura: falla emergere in
fase di design, non in produzione.
:::

Conteggio chiavi per slot — da eseguire **sul nodo proprietario**:

```bash
SLOT=$(redis-cli -p 7000 CLUSTER KEYSLOT foo)
redis-cli -p 7000 CLUSTER COUNTKEYSINSLOT $SLOT    # 0: lo slot non è suo
redis-cli -p 7002 CLUSTER COUNTKEYSINSLOT $SLOT    # il valore reale
redis-cli -p 7002 CLUSTER GETKEYSINSLOT $SLOT 10
```

---

## Esercizio 4.4 — Popolare e osservare la distribuzione

```bash
for i in $(seq 1 200); do redis-cli -c -p 7000 SET key:$i $i > /dev/null; done
redis-cli --cluster call 127.0.0.1:7000 DBSIZE
redis-cli --cluster info 127.0.0.1:7000
```

**Verifica:** con 200 chiavi la distribuzione non è perfettamente uniforme —
CRC16 è uniforme sugli slot, non sul numero di chiavi a campione piccolo. La
distribuzione converge su volumi reali.

---

## Esercizio 4.5 — Resharding online

**Obiettivo:** spostare 500 slot da un master a un altro **senza downtime**.

```bash
SRC=$(redis-cli -p 7000 CLUSTER MYID)
DST=$(redis-cli -p 7001 CLUSTER MYID)

redis-cli --cluster reshard 127.0.0.1:7000 \
  --cluster-from "$SRC" --cluster-to "$DST" \
  --cluster-slots 500 --cluster-yes
```

```bash
redis-cli -p 7000 CLUSTER NODES | awk '/master/{split($2,a,"@"); print a[1], $9, $10}'
```

**Output misurato:**

```
127.0.0.1:7001  0-499  5461-10922
127.0.0.1:7000  500-5460
127.0.0.1:7002  10923-16383
```

**Verifica:** durante la migrazione di uno slot il nodo sorgente risponde `ASK`
per le chiavi già spostate; il client cluster-aware segue il redirect
temporaneo. Il traffico non si ferma. Nota che 7001 ora possiede due range non
contigui: è normale e non ha impatto sulle prestazioni.

Bilanciamento automatico:

```bash
redis-cli --cluster rebalance 127.0.0.1:7000            # esegue
redis-cli --cluster rebalance 127.0.0.1:7000 --cluster-simulate   # dry-run
```

:::caution
`rebalance` si rifiuta di procedere se il cluster ha problemi aperti
(`*** Please fix your cluster problems before rebalancing`). Prima
`redis-cli --cluster check 127.0.0.1:7000`, poi `--cluster fix` se ci sono slot
in stato *migrating*/*importing* rimasti appesi da un resharding interrotto.
:::

---

## Esercizio 4.6 — Failover manuale (manutenzione pianificata)

Da eseguire **sulla replica** che vuoi promuovere:

```bash
MASTER_ID=$(redis-cli -p 7000 CLUSTER MYID)
REP=$(redis-cli -p 7000 CLUSTER NODES | awk -v m="$MASTER_ID" '$4==m{split($2,a,"@"); split(a[1],b,":"); print b[2]}')
echo "replica di 7000 = $REP"
redis-cli -p $REP CLUSTER FAILOVER
sleep 5
redis-cli -p 7000 CLUSTER NODES | awk '{split($2,a,"@"); print a[1], $3, $9}' | sort
```

**Verifica:** `CLUSTER FAILOVER` senza opzioni è **coordinato**: il master
smette di accettare scritture, la replica si allinea all'offset, poi promuove.
Zero perdita di dati. `CLUSTER FAILOVER FORCE` salta il coordinamento (master
irraggiungibile), `TAKEOVER` salta anche il consenso degli altri master — usalo
solo in disaster recovery consapevole, può creare divergenza.

Questo è il comando da mettere nel runbook di patching: promuovi, patcha il
nodo ex-master, riporta indietro.

---

## Esercizio 4.7 — Failover automatico

```bash
pgrep -a redis-server | grep 7001
kill -9 <pid del master 7001>
sleep 14
redis-cli -p 7000 CLUSTER INFO | grep cluster_state
redis-cli -p 7000 CLUSTER NODES | awk '{split($2,a,"@"); print a[1], $3, $9}' | sort
```

**Output misurato:**

```
cluster_state:ok
127.0.0.1:7001 master,fail
127.0.0.1:7004 master 0-499       <- promosso
```

**Verifica:** il cluster resta `ok` perché ogni slot ha un proprietario vivo. Il
nodo morto resta in `fail` finché non torna o non lo rimuovi con
`CLUSTER FORGET`. Tempo di failover ≈ `cluster-node-timeout` + elezione: con
5000 ms hai ~10 s di indisponibilità sugli slot di quel master.

:::caution[`cluster-require-full-coverage`]
Con il default `yes`, se uno slot resta **senza** proprietario l'intero cluster
smette di servire, anche gli slot sani.

```bash
redis-cli -p 7000 CONFIG GET cluster-require-full-coverage
```

Metterlo a `no` è una scelta di prodotto (disponibilità parziale invece che
indisponibilità totale): decidila con l'AM e scrivila nel runbook, non
improvvisarla durante un incidente.
:::

Teardown:

```bash
for p in 7000 7001 7002 7003 7004 7005; do redis-cli -p $p SHUTDOWN NOSAVE 2>/dev/null; done
rm -rf ~/redis-lab/cl
```

---

## Domande di verifica

1. Perché `CLUSTER COUNTKEYSINSLOT` restituisce 0 su un nodo che non possiede
   lo slot, invece di un errore?
2. Differenza operativa tra `MOVED` e `ASK`?
3. Un tenant è tutto sotto `{tenant:42}`. Il resharding può alleggerirlo?
4. Master morto e `cluster-require-full-coverage yes`: cosa succede agli slot
   degli altri master?

Prossimo passo: [05 · Osservabilità](/scale/05-osservabilita/).
