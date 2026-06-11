---
title: "03 · Configurazione e sicurezza"
description: "redis.conf e CONFIG, autenticazione e ACL, TLS/mTLS e checklist di hardening a strati."
---

Obiettivo: conoscere i parametri di `redis.conf` che contano in produzione,
gestirli a caldo con `CONFIG`, e mettere in sicurezza l'istanza con ACL e TLS.

---

## 3.1 Come funziona la configurazione

Redis legge un file (`redis.conf`) all'avvio; molti parametri sono poi
modificabili a runtime senza riavvio con `CONFIG SET`.

```bash
redis-cli CONFIG GET maxmemory
```

```bash
redis-cli CONFIG SET maxmemory 256mb
```

`CONFIG SET` cambia il valore **in memoria** ma non riscrive il file: al riavvio
torna quello del `redis.conf`. Per persistere le modifiche fatte a caldo:

```bash
redis-cli CONFIG REWRITE
```

Per ispezionare tutta la config attiva:

```bash
redis-cli CONFIG GET '*' | paste - - | sort | head -n 40
```

> Pratica ops: tieni il `redis.conf` sotto **version control** (git) e tratta
> `CONFIG SET` come intervento d'emergenza da riportare poi nel file. Evita la
> deriva tra runtime e file.

---

## 3.2 Parametri di base che configuri sempre

Estratto commentato di un `redis.conf` di produzione standalone:

```ini
# --- Rete ---
bind 127.0.0.1 10.0.0.10        # interfacce su cui ascoltare (mai 0.0.0.0 in chiaro)
protected-mode yes              # rifiuta connessioni esterne senza auth/bind
port 6379
tcp-backlog 511
timeout 0                       # 0 = non chiudere connessioni idle
tcp-keepalive 300

# --- Generale ---
daemonize no                    # no se usi systemd con Type=notify
supervised systemd
pidfile /run/redis/redis.pid
loglevel notice
logfile /var/log/redis/redis.log
databases 16

# --- Memoria ---
maxmemory 2gb
maxmemory-policy noeviction     # vedi modulo 07 per la scelta
maxclients 10000

# --- Persistenza (dettaglio nel modulo 04) ---
dir /var/lib/redis
save 3600 1 300 100 60 10000
appendonly yes
```

Parametri da capire bene:

- **`bind`**: lista di IP locali su cui ascoltare. Lasciare l'ascolto su tutte le
  interfacce senza protezioni è la causa numero uno di Redis compromessi su
  Internet.
- **`protected-mode`**: se `yes` (default), Redis rifiuta connessioni da IP non
  locali quando non c'è né `bind` esplicito né password. È una rete di sicurezza,
  **non** un sostituto di autenticazione e firewall.
- **`maxclients`**: limite connessioni; ricorda che dipende anche dal limite di
  file descriptor del processo (`ulimit -n`, modulo 07).
- **`timeout` / `tcp-keepalive`**: gestione connessioni idle e rilevamento peer
  morti.

---

## 3.3 Autenticazione: da `requirepass` agli ACL

### Modo legacy: password unica

```bash
redis-cli CONFIG SET requirepass 'UnaPasswordLungaECasuale!'
```

```bash
redis-cli -a 'UnaPasswordLungaECasuale!' ping
```

`requirepass` dà a *tutti* i client gli stessi pieni poteri. In produzione moderna
si usano gli **ACL** (da Redis 6), che permettono utenti multipli con permessi
granulari.

### ACL (raccomandato)

Visualizza l'utente di default:

```bash
redis-cli ACL LIST
```

```bash
redis-cli ACL WHOAMI
```

Crea un utente applicativo che può solo leggere/scrivere chiavi con un certo
prefisso e usare solo alcuni comandi:

```bash
redis-cli ACL SETUSER app_cache on '>PasswordApp!' '~cache:*' '+@read' '+@write' '-@dangerous'
```

Lettura della spiegazione: `on` abilita l'utente, `>...` imposta la password,
`~cache:*` limita le chiavi accessibili al pattern, `+@read +@write` concede le
categorie di comandi di lettura/scrittura, `-@dangerous` toglie i comandi
pericolosi (`FLUSHALL`, `KEYS`, `CONFIG`, `SHUTDOWN`, ...).

Verifica e prova:

```bash
redis-cli ACL GETUSER app_cache
```

```bash
redis-cli -u 'redis://app_cache:PasswordApp!@127.0.0.1:6379' set cache:1 ok
```

Categorie utili: `+@read`, `+@write`, `+@admin`, `+@dangerous`, `+@keyspace`,
`+@connection`. Elenco:

```bash
redis-cli ACL CAT
```

Disabilita o riduci l'utente `default` (in produzione spesso lo si mette
`nopass off` oppure gli si toglie ogni permesso):

```bash
redis-cli ACL SETUSER default off
```

> Attenzione: se disabiliti `default` assicurati di avere un altro utente admin
> funzionante, altrimenti ti chiudi fuori.

### File ACL persistente

Per gestire molti utenti, esternalizza in un file:

```ini
# in redis.conf
aclfile /etc/redis/users.acl
```

```bash
redis-cli ACL SAVE      # scrive gli utenti correnti nell'aclfile
```

```bash
redis-cli ACL LOAD      # ricarica dall'aclfile
```

> `requirepass` e `aclfile` sono mutuamente esclusivi: scegli uno dei due
> approcci. Con `aclfile` la password di `default` si gestisce dentro il file.

### Comandi pericolosi

Storicamente si usava `rename-command` per nascondere/disabilitare comandi (es.
rinominare `FLUSHALL`). È **deprecato**: l'approccio corretto è togliere i comandi
via ACL (`-flushall`, `-config`, `-@dangerous`). Mantieni almeno un utente admin
che li conservi per la manutenzione.

---

## 3.4 TLS (cifratura in transito)

Da Redis 6 il TLS è nativo. Serve un Redis compilato con TLS (i pacchetti
ufficiali e AppStream recenti lo includono; da sorgente: `make BUILD_TLS=yes`).

### Generare certificati di test

Per laboratorio puoi generare una CA e un certificato server:

```bash
mkdir -p ~/redis-tls && cd ~/redis-tls
```

```bash
openssl genrsa -out ca.key 4096 && openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -subj "/CN=Redis-Lab-CA" -out ca.crt
```

```bash
openssl genrsa -out redis.key 2048 && openssl req -new -key redis.key -subj "/CN=redis-server" -out redis.csr && openssl x509 -req -in redis.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 365 -sha256 -out redis.crt
```

In produzione usa certificati emessi dalla CA aziendale, non self-signed.

### Configurare Redis per il TLS

```ini
# in redis.conf
port 0                    # disabilita la porta in chiaro (opzionale ma consigliato)
tls-port 6379
tls-cert-file /etc/redis/tls/redis.crt
tls-key-file  /etc/redis/tls/redis.key
tls-ca-cert-file /etc/redis/tls/ca.crt
tls-auth-clients yes      # richiede certificato client (mTLS); 'no' per solo server
```

### Connettersi in TLS

```bash
redis-cli --tls --cert ~/redis-tls/redis.crt --key ~/redis-tls/redis.key --cacert ~/redis-tls/ca.crt -p 6379 ping
```

Per replica e cluster in TLS servono anche `tls-replication yes` e
`tls-cluster yes`. Nota: il TLS aggiunge latenza/CPU; valuta l'impatto con
`redis-benchmark` (modulo 07).

---

## 3.5 Checklist di hardening

Da applicare prima di esporre Redis oltre `localhost`:

La sicurezza di Redis è a **strati**: ogni livello ferma un attacco diverso,
nessuno basta da solo.

```mermaid
flowchart TB
    NET["1. Rete: firewall + bind su IP interni (mai 0.0.0.0 esposto)"]
    PM["2. protected-mode yes"]
    AUTH["3. Autenticazione: ACL per ruolo, default disabilitato"]
    CMD["4. Comandi pericolosi rimossi via ACL (-@dangerous)"]
    TLS["5. TLS / mTLS sul traffico che esce dall'host"]
    OS["6. Utente di servizio non privilegiato + permessi file stretti"]
    NET --> PM --> AUTH --> CMD --> TLS --> OS --> SAFE["Istanza esponibile in rete interna"]
```


1. **Rete**: `bind` solo sulle interfacce necessarie; firewall (`firewalld`) che
   consente 6379 solo dalle subnet client; mai esposto su Internet.
2. **`protected-mode yes`** (lascialo attivo).
3. **Autenticazione**: ACL con utenti dedicati per ruolo; `default` disabilitato
   o senza permessi; password lunghe e casuali, gestite in un secret manager.
4. **Comandi pericolosi** rimossi via ACL agli utenti applicativi
   (`-@dangerous`, `-keys`, `-flushall`, `-config`, `-debug`).
5. **TLS** per il traffico che esce dall'host; mTLS dove richiesto.
6. **Utente di servizio non privilegiato** (`redis`), file con permessi stretti
   su chiavi private e aclfile (`chmod 600`).
7. **Limiti di sistema** allineati (`maxclients`, `ulimit -n`, vedi modulo 07).
8. **`maxmemory` + policy** impostati per evitare OOM (modulo 07).

Verifica rapida dello stato di sicurezza:

```bash
redis-cli CONFIG GET 'bind' && redis-cli CONFIG GET 'protected-mode' && redis-cli ACL WHOAMI && redis-cli ACL LIST
```

Esempio regola firewalld (consenti solo da una subnet):

```bash
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.0.0.0/24" port port="6379" protocol="tcp" accept' && sudo firewall-cmd --reload
```

---

### Prossimo passo

Modulo [04 — Persistenza](04-persistenza.md). Lab corrispondenti: **Lab 1 e Lab
3** nel modulo [09](09-lab.md).
