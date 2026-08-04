---
title: "Scale · 02 · Persistenza e durabilità"
description: "Esercizi su RDB, AOF multi-part, fsync policy, rewrite, verifica dei file e restore reale."
---

Obiettivo dell'unità: scegliere consapevolmente il compromesso tra durabilità e
latenza, e saper ricostruire un'istanza da zero.

Prerequisito: istanza di lab su 6379.

---

## Esercizio 2.1 — RDB: snapshot su richiesta

```bash
redis-cli CONFIG SET save ""            # disattiva i trigger automatici
redis-cli MSET a 1 b 2 c 3
redis-cli BGSAVE
sleep 1
redis-cli INFO persistence | grep -E 'rdb_bgsave_in_progress|rdb_last_bgsave_status|rdb_changes_since_last_save|rdb_last_save_time'
redis-cli LASTSAVE
ls -l ~/redis-lab/single/dump.rdb
```

**Output atteso:**

```
rdb_changes_since_last_save:0
rdb_bgsave_in_progress:0
rdb_last_bgsave_status:ok
```

**Verifica:** `rdb_changes_since_last_save` torna a 0 solo a snapshot
completato. `LASTSAVE` restituisce un timestamp Unix: confrontarlo prima e dopo
è il modo affidabile per sapere se un `BGSAVE` è andato a buon fine in uno
script.

Riattiva i trigger e osserva la sintassi:

```bash
redis-cli CONFIG SET save "900 1 300 10 60 10000"
redis-cli CONFIG GET save
```

Significato: salva se almeno 1 chiave è cambiata in 900 s, **oppure** 10 in
300 s, **oppure** 10000 in 60 s.

:::caution[Il fork]
`BGSAVE` fa `fork()`: il picco di memoria può arrivare a 2× nel caso peggiore, e
`latest_fork_usec` è il tempo in cui l'istanza resta ferma. Su dataset grandi
con poca RAM libera è la causa numero uno di picchi di latenza.

```bash
redis-cli INFO stats | grep latest_fork_usec
```
:::

---

## Esercizio 2.2 — AOF attivato a caldo

**Obiettivo:** passare a AOF senza restart e capire il layout multi-part
(Redis 7+).

```bash
redis-cli CONFIG SET appendonly yes
sleep 1
redis-cli INFO persistence | grep -E 'aof_enabled|aof_rewrite_in_progress|aof_last_bgrewrite_status|aof_last_write_status'
ls -l ~/redis-lab/single/appendonlydir/
```

**Output misurato:**

```
aof_enabled:1
aof_last_bgrewrite_status:ok
aof_last_write_status:ok

appendonly.aof.1.base.rdb
appendonly.aof.1.incr.aof
appendonly.aof.manifest
```

**Verifica:** da Redis 7 l'AOF non è più un file unico ma una **directory** con
un base file (in formato RDB, se `aof-use-rdb-preamble yes`), uno o più file
incrementali e un manifest. Ogni script di backup scritto per Redis 6 che copia
`appendonly.aof` **fallisce silenziosamente** su Redis 7: è la trappola più
comune negli upgrade.

Rendi persistente la modifica (a caldo `CONFIG SET` non riscrive il file):

```bash
redis-cli CONFIG REWRITE      # solo se l'istanza è partita da un file di config
```

---

## Esercizio 2.3 — Le tre policy di fsync

```bash
redis-cli CONFIG GET appendfsync
for p in always everysec no; do
  redis-cli CONFIG SET appendfsync $p > /dev/null
  echo -n "$p: "; redis-benchmark -n 20000 -c 10 -t set -q | tail -1
done
redis-cli CONFIG SET appendfsync everysec
```

| Policy | Perdita massima | Costo |
|---|---|---|
| `always` | ~1 comando | throughput crolla, un `fsync` per scrittura |
| `everysec` | ~1 secondo | default, compromesso corretto nel 95% dei casi |
| `no` | a discrezione del kernel | massime prestazioni, nessuna garanzia |

**Verifica:** misura la differenza sul *tuo* storage. Su SSD locale il delta
`always` vs `everysec` è marcato; su NFS o storage di rete condiviso `always` è
di fatto inutilizzabile.

---

## Esercizio 2.4 — Rewrite e crescita dell'AOF

```bash
for i in $(seq 1 5000); do redis-cli SET k:$i $i > /dev/null; done
redis-cli INFO persistence | grep -E 'aof_base_size|aof_current_size|aof_pending_rewrite'
redis-cli BGREWRITEAOF
sleep 2
redis-cli INFO persistence | grep -E 'aof_last_bgrewrite_status|aof_rewrite_in_progress'
ls -l ~/redis-lab/single/appendonlydir/
```

**Verifica:** dopo il rewrite l'indice dei file nel manifest è incrementato
(`appendonly.aof.2.*`). Il rewrite automatico scatta su
`auto-aof-rewrite-percentage` (default 100) rispetto a
`auto-aof-rewrite-min-size` (default 64mb):

```bash
redis-cli CONFIG GET auto-aof-rewrite-percentage auto-aof-rewrite-min-size
```

---

## Esercizio 2.5 — Verificare l'integrità dei file

```bash
redis-check-rdb ~/redis-lab/single/dump.rdb
redis-check-aof ~/redis-lab/single/appendonlydir/appendonly.aof.manifest
```

**Output atteso:**

```
All AOF files and manifest are valid
```

**Verifica:** su Redis 7 `redis-check-aof` va puntato al **manifest**, non al
singolo `.aof`. In caso di file troncato (crash durante la scrittura):

```bash
redis-check-aof --fix ~/redis-lab/single/appendonlydir/appendonly.aof.manifest
```

`--fix` tronca l'AOF all'ultimo comando valido: perdi le scritture finali, ma
l'istanza riparte. Fai sempre una copia del file **prima** di usarlo.

---

## Esercizio 2.6 — Restore reale (il lab che conta)

**Obiettivo:** ricostruire un'istanza da un backup, senza scorciatoie.

```bash
# 1. stato noto
redis-cli DBSIZE
redis-cli BGSAVE && sleep 1
cp ~/redis-lab/single/dump.rdb /tmp/backup-$(date +%F).rdb

# 2. distruggi
redis-cli FLUSHALL
redis-cli DBSIZE          # 0

# 3. restore
redis-cli SHUTDOWN NOSAVE 2>/dev/null
rm -rf ~/redis-lab/single/appendonlydir
cp /tmp/backup-$(date +%F).rdb ~/redis-lab/single/dump.rdb
redis-server --port 6379 --dir ~/redis-lab/single --daemonize yes --logfile r.log
sleep 1
redis-cli DBSIZE          # il valore di partenza
```

:::caution[L'errore classico]
Se l'istanza ha `appendonly yes`, all'avvio Redis carica **l'AOF e ignora il
file RDB**. Restore da RDB su un'istanza AOF senza rimuovere `appendonlydir/`
= database vuoto e nessun messaggio d'errore. È lo scenario che manda a monte
i restore veri.
:::

Procedura corretta per un restore da RDB su istanza AOF:

```bash
# 1. avvia con appendonly no  2. carica l'RDB  3. CONFIG SET appendonly yes
#    (Redis rigenera l'AOF dal dataset in memoria)
```

---

## Domande di verifica

1. `rdb_last_bgsave_status:err`. Quali sono le due cause più probabili e come
   le distingui?
2. Perché con `appendonly yes` un restore da `dump.rdb` può risultare vuoto?
3. Il tuo script di backup copia `appendonly.aof`. Su Redis 7 cosa ottieni?
4. `latest_fork_usec` è 800000. Cosa significa per gli SLO di latenza?

Prossimo passo: [03 · Alta disponibilità](/scale/03-alta-disponibilita/).
