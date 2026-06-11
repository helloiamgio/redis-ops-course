---
title: "09 · Laboratori pratici"
description: "Otto laboratori più capstone, eseguibili su RHEL o macOS, con soluzioni. Tutti i flussi sono stati validati su Redis reale."
---

Workbook pratico del corso. Ogni lab è autonomo, eseguibile su **una sola
macchina** (RHEL 9 o macOS), e include: obiettivo, prerequisiti, passi, verifica,
soluzione e domande di consolidamento.

Convenzione: dove serve, lavoriamo in `~/redis-lab` con istanze su porte diverse,
così non tocchiamo l'eventuale Redis di sistema.

```bash
mkdir -p ~/redis-lab && cd ~/redis-lab
```

> **macOS**: assicurati di avere `redis-server`, `redis-cli`, `redis-sentinel`,
> `redis-benchmark` nel PATH (`brew install redis`).
> **RHEL**: installa Redis come nel modulo 02; per i lab multi-istanza lanceremo
> processi a mano (non via systemd), quindi basta avere i binari.

Indice:
- Lab 1 — Installazione e prima messa in sicurezza
- Lab 2 — Persistenza e crash recovery
- Lab 3 — ACL e TLS
- Lab 4 — Replica + Sentinel + failover
- Lab 5 — Redis Cluster: build, reshard, node failure
- Lab 6 — Monitoring, benchmark, tuning
- Lab 7 — Backup e restore (con DR simulato)
- Lab 8 — Troubleshooting: scenari guasti da risolvere
- Capstone — Stack HA end-to-end

---

## Lab 1 — Installazione e prima messa in sicurezza
**Obiettivo**: installare Redis, avviarlo, e portarlo da "default insicuro" a
"minimamente sicuro" (auth + bind + protected-mode).

**Passi**

1. Installa Redis (modulo 02) e verifica:

```bash
redis-server --version && redis-cli ping
```

2. Avvia un'istanza dedicata al lab con config inline:

```bash
redis-server --port 7000 --dir ~/redis-lab --daemonize yes --logfile ~/redis-lab/7000.log
```

3. Imposta una password e una bind sicura a caldo:

```bash
redis-cli -p 7000 CONFIG SET requirepass 'Lab1Password!'
```

```bash
redis-cli -p 7000 -a 'Lab1Password!' CONFIG SET bind '127.0.0.1' 2>/dev/null
```

**Verifica**

```bash
redis-cli -p 7000 ping        # atteso: errore NOAUTH
```

```bash
redis-cli -p 7000 -a 'Lab1Password!' ping 2>/dev/null   # atteso: PONG
```

**Soluzione / spiegazione**: senza password, `PING` funziona per chiunque; dopo
`requirepass`, i client devono autenticarsi (`-a` o `REDISCLI_AUTH`). In
produzione faresti tutto questo nel `redis.conf` versionato, non a caldo.

**Domande**
1. Perché `protected-mode yes` non basta da solo a mettere in sicurezza Redis?
2. Dove finisce la password se usi `CONFIG REWRITE`? E se non lo usi?

Cleanup:

```bash
redis-cli -p 7000 -a 'Lab1Password!' shutdown nosave 2>/dev/null
```

---

## Lab 2 — Persistenza e crash recovery
**Obiettivo**: osservare RDB e AOF, e simulare un crash per verificare il
recupero dei dati.

**Passi**

1. Avvia un'istanza con **solo RDB** (no AOF), senza save automatico:

```bash
redis-server --port 7000 --dir ~/redis-lab --save '' --appendonly no --daemonize yes --logfile ~/redis-lab/7000.log
```

2. Scrivi dati e simula un crash **senza** salvare:

```bash
redis-cli -p 7000 mset a 1 b 2 c 3 && redis-cli -p 7000 dbsize
```

```bash
# crash "hard" simulato: uccidiamo il processo sulla 7000 (come farebbe un OOM kill)
kill -9 $(redis-cli -p 7000 INFO server | awk -F: '/process_id/{print $2}' | tr -d '\r'); sleep 1
```

3. Riavvia e osserva: i dati sono **persi** (nessuno snapshot era stato fatto).

```bash
redis-server --port 7000 --dir ~/redis-lab --save '' --appendonly no --daemonize yes --logfile ~/redis-lab/7000.log && redis-cli -p 7000 dbsize
```

4. Ora ripeti **con AOF attivo**:

```bash
redis-cli -p 7000 config set appendonly yes && sleep 1 && redis-cli -p 7000 mset x 10 y 20 z 30
```

```bash
kill -9 $(redis-cli -p 7000 INFO server | awk -F: '/process_id/{print $2}' | tr -d '\r'); sleep 1
```

```bash
redis-server --port 7000 --dir ~/redis-lab --save '' --appendonly yes --daemonize yes --logfile ~/redis-lab/7000.log && redis-cli -p 7000 keys '*'
```

**Verifica**: dopo il secondo crash, con AOF attivo, `x y z` ci sono ancora.

**Soluzione / spiegazione**: senza persistenza un crash perde tutto; con AOF
(`everysec`) recuperi fino all'ultima scrittura (max ~1s di perdita). `BGSAVE`
manuale avrebbe salvato uno snapshot RDB anche nel primo caso.

**Domande**
1. Perché in produzione non useresti `SAVE` ma `BGSAVE`?
2. Con AOF + RDB entrambi attivi, da quale file riparte Redis?

Cleanup:

```bash
redis-cli -p 7000 shutdown nosave 2>/dev/null; rm -rf ~/redis-lab/appendonlydir ~/redis-lab/dump.rdb
```

---

## Lab 3 — ACL e TLS
**Obiettivo**: creare utenti ACL con permessi granulari e abilitare il TLS.

**Parte A — ACL**

```bash
redis-server --port 7000 --dir ~/redis-lab --daemonize yes --logfile ~/redis-lab/7000.log
```

```bash
redis-cli -p 7000 ACL SETUSER app on '>AppPass!' '~cache:*' '+@read' '+@write' '-@dangerous'
```

```bash
redis-cli -p 7000 ACL SETUSER readonly on '>RoPass!' '~*' '+@read'
```

Test dei confini di permesso:

```bash
redis-cli -u 'redis://app:AppPass!@127.0.0.1:7000' set cache:1 ok        # OK
```

```bash
redis-cli -u 'redis://app:AppPass!@127.0.0.1:7000' set altro:1 ko        # atteso: NOPERM (chiave fuori pattern)
```

```bash
redis-cli -u 'redis://readonly:RoPass!@127.0.0.1:7000' set cache:2 ko    # atteso: NOPERM (no write)
```

**Verifica**

```bash
redis-cli -p 7000 ACL LIST
```

**Parte B — TLS** (richiede Redis con TLS; modulo 03 per i certificati)

Genera i certificati di lab:

```bash
cd ~/redis-lab && openssl genrsa -out ca.key 4096 && openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -subj "/CN=Lab-CA" -out ca.crt && openssl genrsa -out redis.key 2048 && openssl req -new -key redis.key -subj "/CN=redis" -out redis.csr && openssl x509 -req -in redis.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 365 -sha256 -out redis.crt
```

Avvia un'istanza solo-TLS sulla 7001:

```bash
redis-server --port 0 --tls-port 7001 --tls-cert-file ~/redis-lab/redis.crt --tls-key-file ~/redis-lab/redis.key --tls-ca-cert-file ~/redis-lab/ca.crt --tls-auth-clients no --dir ~/redis-lab --daemonize yes --logfile ~/redis-lab/7001.log
```

```bash
redis-cli --tls --cacert ~/redis-lab/ca.crt -p 7001 ping        # atteso: PONG
```

```bash
redis-cli -p 7001 ping        # atteso: errore (porta in chiaro disabilitata)
```

**Domande**
1. Come toglieresti del tutto i poteri all'utente `default` senza chiuderti fuori?
2. Cosa cambia con `tls-auth-clients yes` (mTLS)?

Cleanup:

```bash
redis-cli -p 7000 shutdown nosave 2>/dev/null; redis-cli --tls --cacert ~/redis-lab/ca.crt -p 7001 shutdown nosave 2>/dev/null
```

---

## Lab 4 — Replica + Sentinel + failover
**Obiettivo**: costruire 1 master + 2 replica + 3 Sentinel su una macchina, e
osservare un failover automatico.

**Passi**

1. Avvia master e replica:

```bash
redis-server --port 6379 --dir ~/redis-lab --dbfilename m.rdb --daemonize yes --logfile ~/redis-lab/m.log
```

```bash
redis-server --port 6380 --dir ~/redis-lab --dbfilename r1.rdb --replicaof 127.0.0.1 6379 --daemonize yes --logfile ~/redis-lab/r1.log
```

```bash
redis-server --port 6381 --dir ~/redis-lab --dbfilename r2.rdb --replicaof 127.0.0.1 6379 --daemonize yes --logfile ~/redis-lab/r2.log
```

2. Verifica la replica. **Attendi che il link sia `up`** prima di testare la
   propagazione: la prima sincronizzazione (full resync) richiede qualche secondo,
   quindi non basta uno `sleep` fisso — si controlla lo stato reale:

```bash
redis-cli -p 6379 INFO replication | grep -E 'role|connected_slaves'
```

```bash
for i in $(seq 1 15); do st=$(redis-cli -p 6380 INFO replication | awk -F: '/master_link_status/{print $2}' | tr -d '\r'); [ "$st" = "up" ] && break; sleep 1; done; echo "master_link_status=$st"
```

```bash
redis-cli -p 6379 set chiave-test ok && sleep 1 && redis-cli -p 6380 get chiave-test
```

3. Crea 3 file Sentinel e avviali:

> Se sulla tua distribuzione manca il binario `redis-sentinel` (alcuni pacchetti
> non lo includono), puoi avviare un Sentinel con `redis-server <conf> --sentinel`.
> Sui pacchetti RHEL ufficiali e su Homebrew il binario `redis-sentinel` è
> presente.

```bash
for p in 26379 26380 26381; do cat > ~/redis-lab/sentinel-$p.conf <<EOF
port $p
sentinel monitor mymaster 127.0.0.1 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
EOF
redis-sentinel ~/redis-lab/sentinel-$p.conf --daemonize yes --logfile ~/redis-lab/sentinel-$p.log
done
```

4. Chiedi ai Sentinel chi è il master:

```bash
redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

5. **Provoca il failover** uccidendo il master:

```bash
redis-cli -p 6379 shutdown nosave 2>/dev/null
```

Attendi ~10 secondi e richiedi il master:

```bash
sleep 10 && redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

**Verifica**: l'indirizzo del master è cambiato (ora è 6380 o 6381). La replica
promossa risponde in scrittura:

```bash
NEWPORT=$(redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster | sed -n 2p); redis-cli -p $NEWPORT set post-failover ok && redis-cli -p $NEWPORT get post-failover
```

**Soluzione / spiegazione**: dopo `down-after-milliseconds` e l'accordo del
quorum (2 su 3), i Sentinel promuovono una replica e riconfigurano l'altra come
sua replica. Se riavvii il vecchio master, diventa replica del nuovo.

**Domande**
1. Perché 3 Sentinel e non 2?
2. Cosa succede ai client connessi per IP fisso al vecchio master?

Cleanup:

```bash
for p in 6380 6381 26379 26380 26381; do redis-cli -p $p shutdown nosave 2>/dev/null; done
```

---

## Lab 5 — Redis Cluster: build, reshard, node failure
**Obiettivo**: creare un cluster a 6 nodi (3 master + 3 replica), aggiungere un
nodo con resharding, e simulare il guasto di un master.

**Passi**

1. Prepara e avvia 6 istanze cluster-enabled:

```bash
for p in 7000 7001 7002 7003 7004 7005; do mkdir -p ~/redis-lab/$p && redis-server --port $p --cluster-enabled yes --cluster-config-file ~/redis-lab/$p/nodes.conf --cluster-node-timeout 5000 --appendonly yes --dir ~/redis-lab/$p --daemonize yes --logfile ~/redis-lab/$p/redis.log; done
```

2. Crea il cluster:

```bash
redis-cli --cluster create 127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 --cluster-replicas 1 --cluster-yes
```

3. Verifica:

```bash
redis-cli -p 7000 CLUSTER INFO | grep -E 'cluster_state|cluster_slots_assigned'
```

```bash
redis-cli --cluster check 127.0.0.1:7000
```

4. Scrivi qualche chiave in modalità cluster (segue i redirect):

```bash
for i in $(seq 1 20); do redis-cli -c -p 7000 set k$i v$i >/dev/null; done; redis-cli --cluster info 127.0.0.1:7000
```

5. Aggiungi un nuovo master e ribilancia:

```bash
mkdir -p ~/redis-lab/7006 && redis-server --port 7006 --cluster-enabled yes --cluster-config-file ~/redis-lab/7006/nodes.conf --cluster-node-timeout 5000 --appendonly yes --dir ~/redis-lab/7006 --daemonize yes --logfile ~/redis-lab/7006/redis.log
```

```bash
redis-cli --cluster add-node 127.0.0.1:7006 127.0.0.1:7000
```

```bash
redis-cli --cluster rebalance 127.0.0.1:7000 --cluster-use-empty-masters
```

6. **Simula il guasto di un master** e osserva la promozione della replica:

```bash
redis-cli -p 7000 shutdown nosave 2>/dev/null; sleep 8; redis-cli -p 7001 CLUSTER NODES | grep -E 'master|slave'
```

**Verifica**: dopo il guasto, `cluster_state` torna `ok` perché una replica è
stata promossa (verifica che gli slot siano ancora tutti coperti):

```bash
redis-cli -p 7001 CLUSTER INFO | grep -E 'cluster_state|cluster_slots_assigned'
```

**Soluzione / spiegazione**: il cluster gestisce il failover internamente (niente
Sentinel). Resta disponibile finché ogni slot ha un master vivo; per questo in
produzione master e replica vanno su host/AZ diversi.

**Domande**
1. Perché `MSET k1 a k2 b` può fallire nel cluster, e come lo aggiusti?
2. Cosa succede se muore un master **e** la sua unica replica?

Cleanup:

```bash
for p in 7001 7002 7003 7004 7005 7006; do redis-cli -p $p shutdown nosave 2>/dev/null; done; rm -rf ~/redis-lab/700*
```

---

## Lab 6 — Monitoring, benchmark, tuning
**Obiettivo**: leggere le metriche chiave, fare un baseline di throughput,
osservare l'effetto di un comando lento e dell'eviction.

**Passi**

1. Avvia un'istanza con `maxmemory` basso e policy LRU per forzare l'eviction:

```bash
redis-server --port 7000 --dir ~/redis-lab --maxmemory 16mb --maxmemory-policy allkeys-lru --save '' --daemonize yes --logfile ~/redis-lab/7000.log
```

2. Baseline di throughput:

```bash
redis-benchmark -p 7000 -t set,get -n 100000 -q
```

3. Riempi oltre il limite e osserva le evizioni:

```bash
redis-benchmark -p 7000 -t set -n 200000 -r 1000000 -d 100 -q >/dev/null; redis-cli -p 7000 INFO stats | grep evicted_keys
```

4. Osserva un comando lento nello SLOWLOG:

```bash
redis-cli -p 7000 CONFIG SET slowlog-log-slower-than 1000
```

```bash
redis-cli -p 7000 eval 'local s=0 for i=1,5000000 do s=s+i end return s' 0 >/dev/null; redis-cli -p 7000 SLOWLOG GET 1
```

5. Diagnosi automatica (abilita prima il monitoraggio latenza, altrimenti
   `LATENCY DOCTOR` risponde che è disattivato):

```bash
redis-cli -p 7000 CONFIG SET latency-monitor-threshold 100
```

```bash
redis-cli -p 7000 LATENCY DOCTOR; redis-cli -p 7000 MEMORY DOCTOR
```

6. Metriche live:

```bash
redis-cli -p 7000 --stat
```

(Ctrl-C per uscire.)

**Verifica**: `evicted_keys` > 0 dopo aver superato `maxmemory`; lo script Lua
compare nello SLOWLOG; `--stat` mostra ops/sec e memoria in tempo reale.

**Tuning OS (solo RHEL, richiede sudo)** — applica e rimisura il baseline:

```bash
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled; echo 'vm.overcommit_memory=1' | sudo tee /etc/sysctl.d/90-redis.conf && sudo sysctl -p /etc/sysctl.d/90-redis.conf
```

**Domande**
1. Quale metrica ti dice che Redis è andato in **swap** (non solo frammentazione)?
2. Come calcoli l'hit ratio della cache da `INFO stats`?

Cleanup:

```bash
redis-cli -p 7000 shutdown nosave 2>/dev/null
```

---

## Lab 7 — Backup e restore (DR simulato)
**Obiettivo**: fare un backup consistente a caldo, distruggere i dati, e
ripristinarli.

**Passi**

1. Avvia, popola, fai il backup:

```bash
redis-server --port 7000 --dir ~/redis-lab --dbfilename lab7.rdb --save '' --appendonly no --daemonize yes --logfile ~/redis-lab/7000.log
```

```bash
for i in $(seq 1 1000); do redis-cli -p 7000 set item:$i "valore-$i" >/dev/null; done; redis-cli -p 7000 dbsize
```

```bash
PRE=$(redis-cli -p 7000 LASTSAVE); redis-cli -p 7000 BGSAVE; until [ "$(redis-cli -p 7000 LASTSAVE)" -gt "$PRE" ]; do sleep 1; done; cp ~/redis-lab/lab7.rdb ~/redis-lab/backup-lab7.rdb && echo "backup ok"
```

2. "Disastro": cancella tutto e ferma l'istanza:

```bash
redis-cli -p 7000 flushall && redis-cli -p 7000 shutdown nosave 2>/dev/null
```

3. **Restore**: rimetti il file di backup e riavvia:

```bash
cp ~/redis-lab/backup-lab7.rdb ~/redis-lab/lab7.rdb && redis-server --port 7000 --dir ~/redis-lab --dbfilename lab7.rdb --save '' --appendonly no --daemonize yes --logfile ~/redis-lab/7000.log
```

**Verifica**

```bash
redis-cli -p 7000 dbsize        # atteso: 1000
```

```bash
redis-cli -p 7000 get item:500  # atteso: valore-500
```

**Soluzione / spiegazione**: il backup è la copia dell'RDB ottenuto con un
`BGSAVE` completato (confrontando `LASTSAVE`). Il restore è copiare il file nella
`dir` a istanza ferma e riavviare. Con AOF attivo dovresti gestire il fatto che
Redis ricaricherebbe l'AOF invece dell'RDB (modulo 08).

**Domande**
1. Come automatizzeresti questo con rotazione/retention e auth?
2. Nel cluster, perché il backup va fatto per ogni master?

Cleanup:

```bash
redis-cli -p 7000 shutdown nosave 2>/dev/null; rm -f ~/redis-lab/lab7.rdb ~/redis-lab/backup-lab7.rdb
```

---

## Lab 8 — Troubleshooting: scenari guasti da risolvere
**Obiettivo**: ti vengono dati ambienti "rotti"; diagnostichi e correggi. Prova
prima da solo, poi confronta con la soluzione.

### Scenario A — "Le scritture danno errore MISCONF"

Riproduci. Nota: in Redis 7+ `dir` è un *protected config* e **non** è
modificabile a caldo con `CONFIG SET` (è una difesa contro manomissioni). Per
forzare un fallimento di BGSAVE in modo portabile facciamo in modo che il
`rename` finale dello snapshot fallisca, creando una *directory* con il nome del
file RDB (il rename di un file su una directory fallisce sempre):

```bash
redis-server --port 7000 --dir ~/redis-lab --dbfilename dump.rdb --stop-writes-on-bgsave-error yes --daemonize yes --logfile ~/redis-lab/8a.log; sleep 1; redis-cli -p 7000 set seed 1
```

```bash
mkdir ~/redis-lab/dump.rdb && redis-cli -p 7000 BGSAVE && sleep 2 && redis-cli -p 7000 set k v
```

L'ultimo `SET` deve restituire l'errore `MISCONF ... unable to persist to disk`.

Diagnosi attesa:

```bash
redis-cli -p 7000 INFO persistence | grep rdb_last_bgsave_status
```

```bash
grep -iE 'background sav|error moving|is a directory' ~/redis-lab/8a.log | tail -3
```

<details><summary>Soluzione A</summary>

`rdb_last_bgsave_status:err`: il log mostra `Error moving temp DB file ... Is a
directory`. Con `stop-writes-on-bgsave-error yes` un BGSAVE fallito **blocca le
scritture**. In produzione la causa reale è in genere **disco pieno** (`df -h`),
**permessi** sulla `dir` (l'utente `redis` non può scrivere) o la `dir` errata.
Fix: rimuovi l'ostacolo e verifica con un nuovo BGSAVE riuscito.

```bash
rmdir ~/redis-lab/dump.rdb && redis-cli -p 7000 BGSAVE && sleep 1 && redis-cli -p 7000 set k v
```

Dopo il fix `rdb_last_bgsave_status:ok` e il `SET` torna `OK`.
</details>

### Scenario B — "La replica non si aggiorna"

Riproduci (master con auth, replica senza `masterauth`):

```bash
redis-server --port 6379 --dir ~/redis-lab --requirepass MasterPass --daemonize yes --logfile ~/redis-lab/8b-m.log; redis-server --port 6380 --dir ~/redis-lab --dbfilename r.rdb --replicaof 127.0.0.1 6379 --daemonize yes --logfile ~/redis-lab/8b-r.log
```

Diagnosi:

```bash
redis-cli -p 6380 INFO replication | grep master_link_status
```

<details><summary>Soluzione B</summary>

`master_link_status:down` perché la replica non ha la password del master. Fix
(attendi che il link diventi `up`):

```bash
redis-cli -p 6380 CONFIG SET masterauth MasterPass; for i in $(seq 1 10); do st=$(redis-cli -p 6380 INFO replication | awk -F: '/master_link_status/{print $2}' | tr -d '\r'); [ "$st" = "up" ] && break; sleep 1; done; echo "master_link_status=$st"
```
</details>

### Scenario C — "Non riesco a connettermi da remoto"

Concettuale (single host): l'istanza ha `bind 127.0.0.1` e i client su altra
subnet falliscono.

<details><summary>Soluzione C</summary>

Verifica nell'ordine: `CONFIG GET bind` (aggiungi l'IP dell'interfaccia), `CONFIG
GET protected-mode` + auth, firewall (`firewall-cmd --list-all`, apri 6379 — e
16379 se cluster). Tre cause, un metodo: parti sempre da `redis-cli -h <ip>
ping` e isola lo strato che fallisce.
</details>

Cleanup:

```bash
for p in 7000 6379 6380; do redis-cli -p $p shutdown nosave 2>/dev/null; redis-cli -p $p -a MasterPass shutdown nosave 2>/dev/null; done; rm -rf ~/redis-lab/dump.rdb ~/redis-lab/r.rdb
```

---

## Capstone — Stack HA end-to-end
**Obiettivo**: integrare tutto. Costruisci un servizio Redis "production-like" e
documenta il runbook.

**Requisiti da soddisfare**

1. **Standalone con HA**: 1 master + 2 replica + 3 Sentinel (Lab 4).
2. **Sicurezza**: ACL con un utente applicativo limitato a `~app:*` e `default`
   senza permessi; password gestita via `REDISCLI_AUTH`.
3. **Persistenza**: AOF `everysec` + RDB; verifica `aof_last_write_status:ok`.
4. **Backup**: script con rotazione (modulo 08) schedulato, e un restore provato.
5. **Monitoring**: esegui `redis_exporter` contro il master e verifica
   `:9121/metrics`; elenca le 5 metriche che metteresti sotto alert.
6. **Drill di failover**: uccidi il master, dimostra che Sentinel promuove una
   replica e che il backup+restore funziona sul nuovo master.

**Deliverable**: un breve **runbook** (anche solo un file markdown) che, per
ciascun requisito, riporti i comandi usati, l'output di verifica, e la procedura
di recovery. È esattamente ciò che terresti nel repo del team.

**Criteri di "fatto bene"**
- `SENTINEL get-master-addr-by-name` cambia dopo il failover e il nuovo master
  accetta scritture.
- L'utente applicativo non può eseguire `FLUSHALL` né accedere a chiavi fuori
  `~app:*`.
- Un restore da backup ripopola correttamente `DBSIZE`.
- Sai elencare a memoria le metriche di allarme e cosa indicano.

---

### Hai finito il corso

Hai coperto installazione, configurazione, sicurezza, persistenza, replica/HA,
cluster, monitoring/tuning, backup/DR, upgrade e troubleshooting, con pratica su
ciascun tema. Per consolidare: rifai il **Capstone** trasformandolo in un Redis
**Cluster** a 6 nodi (Lab 5) invece che Sentinel, e confronta le due architetture
sul piano operativo.
