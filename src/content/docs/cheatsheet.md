---
title: "Cheatsheet comandi Redis"
description: "Riferimento rapido e ops-ready di tutti i principali comandi Redis: redis-cli, chiavi, tipi di dato (string, hash, list, set, sorted set, stream, bitmap, HLL, geo), TTL, pub/sub, transazioni, scripting, persistenza, replica, cluster, Sentinel, ACL, client, memoria e diagnostica."
---

Riferimento rapido **paste-ready**. Le voci tra `<...>` sono segnaposto. La
maggior parte dei comandi è valida da Redis 6.x; dove serve, è indicata la
versione minima. Per i dettagli operativi vedi i moduli del corso.

## redis-cli — connessione e flag utili

```bash
redis-cli                                  # localhost:6379
redis-cli -h <host> -p <port> -n <db>      # host/porta/numero DB (0-15, non in cluster)
redis-cli -u redis://user:pass@host:6379/0 # connessione via URI
redis-cli -a <password>                    # auth (meglio: export REDISCLI_AUTH=<password>)
redis-cli --tls --cacert ca.crt -p 6379    # connessione TLS
redis-cli -c -p 7000                        # modalità cluster (segue i redirect MOVED/ASK)
redis-cli -r 5 -i 1 <comando>              # ripeti 5 volte, 1s di intervallo
redis-cli --eval script.lua key1 , arg1     # esegue uno script Lua (la virgola separa KEYS/ARGV)
```

## Operazioni e diagnostica (one-liner ops-ready)

```bash
redis-cli PING                              # PONG se vivo
redis-cli --scan --pattern 'user:*'         # elenca chiavi senza bloccare (usa SCAN)
redis-cli --bigkeys                         # trova le chiavi più grandi per tipo
redis-cli --memkeys                         # trova le chiavi che occupano più memoria
redis-cli --hotkeys                         # chiavi più "calde" (richiede maxmemory-policy LFU)
redis-cli --latency                         # latenza live (ms)
redis-cli --latency-history -i 5            # latenza campionata ogni 5s
redis-cli --stat                            # statistiche live (ops/sec, memoria, client)
redis-cli --intrinsic-latency 5             # latenza intrinseca della macchina (5s)
redis-cli --rdb dump.rdb                     # scarica un dump RDB dal server
redis-cli MONITOR                            # stream live di TUTTI i comandi (solo debug!)
```

## Chiavi (generiche)

```bash
EXISTS <key> [<key> ...]                    # quante esistono
TYPE <key>                                  # tipo (string/list/set/zset/hash/stream)
DEL <key> ...                               # cancella (sincrono)
UNLINK <key> ...                            # cancella in background (non blocca)
RENAME <key> <newkey>                       # rinomina
RANDOMKEY                                   # una chiave a caso
KEYS <pattern>                              # ⚠️ O(N) BLOCCANTE — non usare in produzione
SCAN <cursor> MATCH <pat> COUNT <n>         # iterazione a cursore (preferito)
OBJECT ENCODING <key>                       # encoding interno (listpack/quicklist/...)
OBJECT IDLETIME <key>                       # secondi dall'ultimo accesso
OBJECT FREQ <key>                           # frequenza accessi (richiede LFU)
MEMORY USAGE <key>                          # byte stimati occupati dalla chiave
COPY <src> <dst> [REPLACE]                  # copia chiave (6.2+)
DUMP <key>  /  RESTORE <key> <ttl> <data>   # serializza / ripristina
```

## TTL e scadenze

```bash
EXPIRE <key> <sec> [NX|XX|GT|LT]            # scadenza relativa (opzioni 7.0+)
PEXPIRE <key> <ms>                          # scadenza in millisecondi
EXPIREAT <key> <unix-ts>                    # scadenza a timestamp assoluto
TTL <key>   /  PTTL <key>                   # secondi / ms rimanenti (-1 nessuna, -2 assente)
EXPIRETIME <key>                            # timestamp unix di scadenza (7.0+)
PERSIST <key>                               # rimuove la scadenza
```

## String

```bash
SET <key> <val> [EX s|PX ms|EXAT ts] [NX|XX] [GET] [KEEPTTL]
GET <key>
MSET <k1> <v1> <k2> <v2>   /  MGET <k1> <k2>
SETEX <key> <sec> <val>  /  PSETEX <key> <ms> <val>
GETSET <key> <val>                          # (deprecato → SET ... GET)
GETDEL <key>                                # leggi e cancella (6.2+)
GETEX <key> EX <sec>                        # leggi e (ri)imposta TTL (6.2+)
APPEND <key> <val>   /  STRLEN <key>
INCR <key> / DECR <key> / INCRBY <key> <n> / INCRBYFLOAT <key> <f>
SETRANGE <key> <offset> <val>  /  GETRANGE <key> <start> <end>
```

## Hash

```bash
HSET <key> <field> <val> [<field> <val> ...]
HGET <key> <field>  /  HMGET <key> <f1> <f2>  /  HGETALL <key>
HDEL <key> <field> ...  /  HEXISTS <key> <field>
HINCRBY <key> <field> <n>  /  HINCRBYFLOAT <key> <field> <f>
HKEYS <key> / HVALS <key> / HLEN <key>
HRANDFIELD <key> [<count>] [WITHVALUES]     # 6.2+
HSCAN <key> <cursor> MATCH <pat> COUNT <n> [NOVALUES]
# Scadenza per singolo campo (7.4+):
HEXPIRE <key> <sec> FIELDS <n> <field> ...  /  HTTL <key> FIELDS <n> <field> ...
```

## List

```bash
LPUSH/RPUSH <key> <val> ...   /  LPOP/RPOP <key> [<count>]
LRANGE <key> <start> <stop>   /  LLEN <key>  /  LINDEX <key> <i>
LSET <key> <i> <val>  /  LINSERT <key> BEFORE|AFTER <pivot> <val>
LREM <key> <count> <val>  /  LTRIM <key> <start> <stop>
LMOVE <src> <dst> LEFT|RIGHT LEFT|RIGHT      # sposta atomico (6.2+)
LPOS <key> <val>                             # posizione di un elemento (6.0.6+)
LMPOP <numkeys> <k> ... LEFT|RIGHT [COUNT n] # pop multi-key (7.0+)
BLPOP/BRPOP <key> ... <timeout>              # pop bloccante (code)
BLMOVE <src> <dst> LEFT|RIGHT LEFT|RIGHT <timeout>
```

## Set

```bash
SADD <key> <m> ...   /  SREM <key> <m> ...
SMEMBERS <key>  /  SCARD <key>  /  SISMEMBER <key> <m>
SMISMEMBER <key> <m1> <m2>                   # 6.2+
SINTER/SUNION/SDIFF <k1> <k2> ...
SINTERCARD <numkeys> <k> ... [LIMIT n]       # 7.0+
SINTERSTORE/SUNIONSTORE/SDIFFSTORE <dst> <k> ...
SRANDMEMBER <key> [<count>]  /  SPOP <key> [<count>]
SSCAN <key> <cursor> MATCH <pat> COUNT <n>
```

## Sorted Set (ZSet)

```bash
ZADD <key> [NX|XX|GT|LT] [CH] <score> <m> [<score> <m> ...]
ZSCORE <key> <m>  /  ZMSCORE <key> <m1> <m2>  /  ZCARD <key>
ZINCRBY <key> <n> <m>
ZRANGE <key> <start> <stop> [REV] [WITHSCORES]            # forma unificata 6.2+
ZRANGE <key> <min> <max> BYSCORE [LIMIT off cnt]          # per punteggio
ZRANGE <key> <min> <max> BYLEX                            # lessicografico
ZRANK/ZREVRANK <key> <m> [WITHSCORE]
ZCOUNT <key> <min> <max>  /  ZREMRANGEBYRANK|BYSCORE|BYLEX
ZPOPMIN/ZPOPMAX <key> [<count>]  /  BZPOPMIN/BZPOPMAX <key> ... <timeout>
ZMPOP <numkeys> <k> ... MIN|MAX [COUNT n]                 # 7.0+
ZUNIONSTORE/ZINTERSTORE/ZDIFFSTORE <dst> <numkeys> <k> ...
ZSCAN <key> <cursor> MATCH <pat> COUNT <n>
```

## Bitmap / HyperLogLog / Geo

```bash
# Bitmap
SETBIT <key> <offset> <0|1>  /  GETBIT <key> <offset>
BITCOUNT <key> [start end [BYTE|BIT]]  /  BITPOS <key> <bit> [...]
BITOP AND|OR|XOR|NOT <dst> <k> ...  /  BITFIELD <key> ...
# HyperLogLog (conteggio unici approssimato)
PFADD <key> <el> ...  /  PFCOUNT <key> ...  /  PFMERGE <dst> <src> ...
# Geo
GEOADD <key> <lon> <lat> <member> ...
GEOSEARCH <key> FROMMEMBER <m>|FROMLONLAT <lon> <lat> BYRADIUS <r> m|km ASC
GEODIST <key> <m1> <m2> [m|km]  /  GEOPOS <key> <m>
```

## Streams

```bash
XADD <key> [MAXLEN ~ <n>] '*' <field> <val> ...   # '*' = id automatico
XLEN <key>  /  XRANGE <key> - +  /  XREVRANGE <key> + -
XREAD [COUNT n] [BLOCK ms] STREAMS <key> <id|$>
XDEL <key> <id> ...  /  XTRIM <key> MAXLEN ~ <n>
# Consumer group
XGROUP CREATE <key> <group> <id|$> [MKSTREAM]
XREADGROUP GROUP <group> <consumer> COUNT <n> STREAMS <key> '>'
XACK <key> <group> <id> ...
XPENDING <key> <group> [<start> <end> <count>]
XCLAIM <key> <group> <consumer> <min-idle-ms> <id> ...
XAUTOCLAIM <key> <group> <consumer> <min-idle-ms> <start>   # 6.2+
XINFO STREAM <key>  /  XINFO GROUPS <key>
```

## Pub/Sub

```bash
SUBSCRIBE <canale> ...   /  UNSUBSCRIBE [<canale>]
PSUBSCRIBE <pattern> ...  /  PUBLISH <canale> <msg>
PUBSUB CHANNELS [pattern]  /  PUBSUB NUMSUB <canale>
# Sharded Pub/Sub (consigliato in cluster, 7.0+)
SSUBSCRIBE <canale>  /  SPUBLISH <canale> <msg>
```

## Transazioni e scripting

```bash
MULTI ... <comandi> ... EXEC                 # esegue la coda atomicamente
DISCARD                                      # annulla la transazione
WATCH <key> ... / UNWATCH                    # optimistic lock (CAS)
EVAL "<script>" <numkeys> <key> ... <arg> ...    # Lua
EVALSHA <sha1> <numkeys> ...  /  SCRIPT LOAD "<script>"  /  SCRIPT FLUSH
FUNCTION LOAD "<code>"  /  FCALL <func> <numkeys> ...     # Functions (7.0+)
```

## Persistenza

```bash
SAVE                                         # snapshot sincrono (BLOCCA — solo emergenze)
BGSAVE                                       # snapshot in background (fork)
BGREWRITEAOF                                 # riscrive/compatta l'AOF
LASTSAVE                                     # timestamp dell'ultimo salvataggio RDB
CONFIG SET appendonly yes|no                 # abilita/disabilita AOF a caldo
CONFIG SET save "900 1 300 10"               # punti di salvataggio RDB
# Da shell:
redis-check-rdb dump.rdb   /  redis-check-aof --fix appendonlydir/<file>
```

## Replica

```bash
REPLICAOF <host> <port>                      # rendi questa istanza replica
REPLICAOF NO ONE                             # promuovi a master (stop replica)
WAIT <numreplicas> <timeout-ms>              # attendi ack da N replica
INFO replication                             # role, connected_slaves, master_link_status, offset
```

## Cluster

```bash
# Client
CLUSTER INFO        # cluster_state, slots_assigned, known_nodes
CLUSTER NODES       # elenco nodi (id, ip:port, flags, master/slave, slot)
CLUSTER SHARDS / CLUSTER SLOTS               # mappa slot→nodo
CLUSTER KEYSLOT <key>   /  CLUSTER MYID
CLUSTER COUNTKEYSINSLOT <slot>  /  CLUSTER GETKEYSINSLOT <slot> <n>
CLUSTER FAILOVER [FORCE|TAKEOVER]            # da eseguire su una replica
# Amministrazione (redis-cli --cluster)
redis-cli --cluster create <ip:port> ... --cluster-replicas 1
redis-cli --cluster check <ip:port>
redis-cli --cluster info <ip:port>
redis-cli --cluster add-node <new> <existing> [--cluster-slave]
redis-cli --cluster del-node <ip:port> <node-id>
redis-cli --cluster reshard <ip:port>
redis-cli --cluster rebalance <ip:port> [--cluster-use-empty-masters]
redis-cli --cluster fix <ip:port>
```

## Sentinel

```bash
redis-cli -p 26379 SENTINEL masters
redis-cli -p 26379 SENTINEL master <name>
redis-cli -p 26379 SENTINEL replicas <name>
redis-cli -p 26379 SENTINEL sentinels <name>
redis-cli -p 26379 SENTINEL get-master-addr-by-name <name>
redis-cli -p 26379 SENTINEL ckquorum <name>          # verifica il quorum
redis-cli -p 26379 SENTINEL failover <name>          # failover manuale
redis-cli -p 26379 SENTINEL reset <pattern>          # reset stato
```

## ACL e sicurezza

```bash
ACL WHOAMI                                   # utente corrente
ACL LIST / ACL USERS / ACL GETUSER <user>
ACL SETUSER <user> on >'<pass>' ~<key-pat> +@<cat> -@dangerous
ACL DELUSER <user>  /  ACL CAT  /  ACL GENPASS
ACL LOG [<count>]  /  ACL LOG RESET          # accessi negati
AUTH [<user>] <password>
CONFIG SET requirepass '<password>'          # password istanza (utente default)
```

## Client e connessione

```bash
HELLO [<protover>]                           # handshake / info protocollo (RESP2/3)
CLIENT ID / CLIENT INFO / CLIENT LIST
CLIENT SETNAME <nome> / CLIENT GETNAME
CLIENT KILL ID <id> | ADDR <ip:port>
CLIENT NO-EVICT on|off  /  CLIENT NO-TOUCH on|off
CLIENT PAUSE <ms> [WRITE|ALL]  /  CLIENT UNPAUSE
SELECT <db>  /  SWAPDB <i> <j>  /  ECHO <msg>
```

## Server, memoria e diagnostica

```bash
INFO [section]            # server|clients|memory|persistence|stats|replication|cpu|cluster|keyspace
DBSIZE                    # numero di chiavi nel DB corrente
CONFIG GET <param>  /  CONFIG SET <param> <val>  /  CONFIG REWRITE
CONFIG RESETSTAT          # azzera le statistiche
MEMORY USAGE <key>  /  MEMORY DOCTOR  /  MEMORY STATS  /  MEMORY PURGE
SLOWLOG GET [n]  /  SLOWLOG RESET  /  SLOWLOG LEN
LATENCY DOCTOR  /  LATENCY HISTORY <event>  /  LATENCY RESET
LATENCY LATEST  /  CONFIG SET latency-monitor-threshold <ms>
COMMAND COUNT  /  COMMAND DOCS <cmd>  /  COMMAND INFO <cmd>
TIME  /  LOLWUT                              # ora del server / easter egg di versione
DEBUG SLEEP <sec>  /  DEBUG OBJECT <key>     # solo debug
```

## Notifiche keyspace (eventi su chiavi)

```bash
CONFIG SET notify-keyspace-events KEA        # abilita tutti gli eventi
PSUBSCRIBE '__keyevent@0__:expired'          # ascolta le chiavi scadute sul DB 0
PSUBSCRIBE '__keyspace@0__:<key>'            # eventi su una chiave specifica
```

## Amministrazione e comandi "pericolosi"

```bash
FLUSHDB [ASYNC]                              # ⚠️ svuota il DB corrente
FLUSHALL [ASYNC]                             # ⚠️ svuota TUTTI i DB
SHUTDOWN [NOSAVE|SAVE]                        # arresta il server
RESET                                        # resetta lo stato della connessione
FAILOVER [TO <host> <port>] [ABORT]          # failover coordinato (6.2+)
```

> In produzione, rimuovi o limita i comandi pericolosi via ACL
> (`-@dangerous -flushall -flushdb -config -debug`) e riservali a un utente
> amministrativo (modulo 03).

## redis-benchmark (test di carico)

```bash
redis-benchmark -h <host> -p 6379 -t set,get -n 100000 -q
redis-benchmark -n 200000 -r 100000 -d 100 -P 16 -c 50    # pipeline 16, 50 client, valori 100B
redis-benchmark -t set -n 1000000 --threads 4             # multi-thread
```

---

Per il contesto e le motivazioni operative dietro a questi comandi, vedi i moduli
del corso: chiavi/tipi → [01](01-architettura.md), sicurezza/ACL →
[03](03-configurazione-sicurezza.md), persistenza → [04](04-persistenza.md),
replica/Sentinel → [05](05-replica-sentinel.md), cluster →
[06](06-cluster.md), diagnostica → [07](07-monitoring-tuning.md).
