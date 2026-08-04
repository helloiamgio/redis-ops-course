---
title: "Scale · 00 · Setup dell'ambiente"
description: "Installazione di Redis su RHEL/Ubuntu, da sorgente e in container, verifica dei binari e preparazione delle tre topologie di laboratorio."
---

Percorso hands-on che copre lo stesso terreno operativo del syllabus
*Running Redis at Scale*: connessioni, persistenza, alta disponibilità,
scalabilità, osservabilità. Tutti gli esercizi sono stati **eseguiti e
validati** su Redis 7.0.15; dove il comportamento cambia tra versioni è
segnalato.

:::note[Come è fatto]
Ogni esercizio ha: **obiettivo** → **comandi** → **output atteso** →
**verifica**. Nessun esercizio richiede Docker: le topologie multi-nodo girano
con più `redis-server` su porte diverse dello stesso host.
:::

---

## 0.1 Installazione

### RHEL 8 / 9 (il caso della tua flotta)

```bash
dnf module list redis                 # stream disponibili in AppStream
dnf module enable redis:7 -y          # se lo stream 7 è presente
dnf install -y redis
redis-server --version
```

Se l'AppStream è fermo a una minor troppo vecchia, il repo ufficiale Redis:

```bash
dnf install -y https://packages.redis.io/redis-stack/redis-stack-server.rpm 2>/dev/null || true
# in alternativa (ambienti connessi):
curl -fsSL https://packages.redis.io/gpg > /tmp/redis.gpg
rpm --import /tmp/redis.gpg
cat > /etc/yum.repos.d/redis.repo <<'EOF'
[redis]
name=Redis
baseurl=https://packages.redis.io/rpm/rhel9
enabled=1
gpgcheck=1
EOF
dnf install -y redis
```

:::caution[Air-gapped]
In ambiente disconnesso mirrori l'RPM o compili da sorgente (§0.2). Verifica
sempre la versione: molte opzioni di questo corso (AOF multi-part, `CLIENT
NO-TOUCH`, `CLUSTER SHARDS`) hanno soglie di versione diverse.
:::

### Debian / Ubuntu

```bash
apt-get update && apt-get install -y redis-server redis-sentinel
redis-server --version && redis-cli --version
```

### Da sorgente (versione esatta, nessun repo)

```bash
dnf install -y gcc make jemalloc-devel openssl-devel systemd-devel   # RHEL
curl -fsSLO https://download.redis.io/redis-stable.tar.gz
tar xzf redis-stable.tar.gz && cd redis-stable
make BUILD_TLS=yes USE_SYSTEMD=yes -j"$(nproc)"
make install PREFIX=/usr/local
```

### Verifica dei binari

```bash
for b in redis-server redis-cli redis-sentinel redis-benchmark redis-check-aof redis-check-rdb; do
  printf "%-18s %s\n" "$b" "$(command -v $b || echo MANCANTE)"
done
```

Ti servono tutti e sei. `redis-check-aof` e `redis-check-rdb` sono spesso
symlink a `redis-server`: è normale.

---

## 0.2 Un'istanza pulita per i lab

Non usare il servizio di sistema per gli esercizi: lavora in una directory
dedicata, così puoi distruggere e ricreare senza toccare `/etc/redis`.

```bash
mkdir -p ~/redis-lab/single && cd ~/redis-lab/single
redis-server --port 6379 --dir ~/redis-lab/single \
  --daemonize yes --logfile r.log \
  --enable-debug-command yes \
  --unixsocket ~/redis-lab/single/redis.sock
redis-cli PING
```

:::caution[`enable-debug-command`]
Da Redis 7.0 il comando `DEBUG` è **disabilitato di default**. Senza
`--enable-debug-command yes` diversi esercizi di questo percorso rispondono:

```
ERR DEBUG command not allowed. If the enable-debug-command option is set to "local"...
```

Non abilitarlo mai in produzione: `DEBUG SEGFAULT` fa esattamente quello che
promette.
:::

Teardown, sempre disponibile:

```bash
redis-cli -p 6379 SHUTDOWN NOSAVE 2>/dev/null
rm -rf ~/redis-lab/single
```

---

## 0.3 Le tre topologie del percorso

| Topologia | Porte | Usata in |
|---|---|---|
| Singola istanza | 6379 | [01 Connessioni](/scale/01-connessioni/), [02 Persistenza](/scale/02-persistenza/), [05 Osservabilità](/scale/05-osservabilita/) |
| 1 master + 2 replica + 3 Sentinel | 6379–6381, 26379–26381 | [03 Alta disponibilità](/scale/03-alta-disponibilita/) |
| Cluster 3 master + 3 replica | 7000–7005 | [04 Scalabilità](/scale/04-scalabilita/) |

Gli script `sentinel-up.sh` / `cluster-up.sh` nel repository (`labs/scripts/`)
alzano le ultime due in un colpo solo. Nel percorso li costruiamo a mano la
prima volta: è il punto in cui si impara cosa fa ogni flag.

---

## 0.4 Baseline: misura prima di toccare

Registra questi valori a sistema sano. Ti serviranno come termine di paragone in
ogni esercizio successivo.

```bash
redis-cli --intrinsic-latency 5 | tail -1     # latenza dell'host, senza rete
redis-cli --latency | tail -1                 # RTT client→server
redis-benchmark -n 10000 -c 10 -t set,get -q  # throughput di riferimento
redis-cli INFO server | grep -E 'redis_version|os|arch_bits|process_id' | tr -d '\r'
```

Su un host di lab non caricato l'ordine di grandezza atteso è: latenza
intrinseca sotto il millisecondo, `--latency` avg ~0.1 ms in loopback,
throughput a cinque cifre per secondo.

---

## Checklist prima di procedere

- [ ] `redis-server --version` ≥ 7.0
- [ ] tutti e sei i binari presenti
- [ ] istanza di lab attiva su 6379 con `enable-debug-command`
- [ ] baseline di latenza e throughput registrata
- [ ] `ulimit -n` dell'utente ≥ 10240 (`ulimit -n`)

Prossimo passo: [01 · Connessioni](/scale/01-connessioni/).
