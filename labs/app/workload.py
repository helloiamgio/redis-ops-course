#!/usr/bin/env python3
"""
Generatore di carico applicativo realistico per i laboratori di tuning.

Ogni profilo riproduce un pattern che si incontra in produzione, incluse le
patologie. Non serve a "testare Redis": serve a darti qualcosa da misurare e da
correggere lato infrastruttura.

    pip install redis
    ./workload.py <profilo> [opzioni]

Profili:
  sessions      cache di sessione con TTL e distribuzione zipfiana (hit ratio)
  nopool        una connessione nuova per ogni comando (tempesta di connessioni)
  pool          stesso carico, connection pool riusato
  roundtrip     N comandi singoli vs pipeline, a parita' di lavoro
  bighash       hash che supera la soglia di encoding (esplosione di memoria)
  hotkey        chiave rovente: tutto il traffico su una sola chiave
  scanner       endpoint "dashboard" che usa KEYS (blocca l'istanza)
  blocking      consumer che occupano connessioni con comandi bloccanti
"""
import argparse
import random
import sys
import time

import redis

DEF_HOST = "127.0.0.1"
DEF_PORT = 6379


def conn(a, **kw):
    return redis.Redis(host=a.host, port=a.port, decode_responses=True, **kw)


def zipf(n, alpha=1.2):
    """Indice zipfiano in [0, n): poche chiavi calde, coda lunga."""
    while True:
        k = int(random.paretovariate(alpha - 1))
        if k < n:
            return k


# --------------------------------------------------------------------------
def p_sessions(a):
    """Cache di sessione: scritture con TTL, letture con distribuzione zipfiana."""
    r = conn(a)
    hits = misses = 0
    t0 = time.time()
    for i in range(a.ops):
        uid = zipf(a.keyspace)
        key = f"session:{uid}"
        if r.get(key) is None:
            misses += 1
            r.set(key, "x" * a.value_size, ex=a.ttl)
        else:
            hits += 1
    dt = time.time() - t0
    print(f"ops={a.ops} in {dt:.1f}s ({a.ops/dt:.0f}/s)")
    print(f"hit ratio applicativo: {hits/(hits+misses)*100:.1f}%")


def p_nopool(a):
    """Antipattern: una connessione TCP nuova a ogni comando."""
    t0 = time.time()
    for i in range(a.ops):
        r = redis.Redis(host=a.host, port=a.port)
        r.set(f"np:{i}", i)
        r.close()
    dt = time.time() - t0
    print(f"{a.ops} comandi senza pool in {dt:.2f}s ({a.ops/dt:.0f}/s)")


def p_pool(a):
    """Stesso carico, una sola connessione riusata."""
    r = conn(a)
    t0 = time.time()
    for i in range(a.ops):
        r.set(f"p:{i}", i)
    dt = time.time() - t0
    print(f"{a.ops} comandi con pool in {dt:.2f}s ({a.ops/dt:.0f}/s)")


def p_roundtrip(a):
    """Stesso lavoro, con e senza pipeline."""
    r = conn(a)
    t0 = time.time()
    for i in range(a.ops):
        r.set(f"rt:{i}", i)
    single = time.time() - t0

    t0 = time.time()
    pipe = r.pipeline(transaction=False)
    for i in range(a.ops):
        pipe.set(f"rtp:{i}", i)
        if i % 500 == 499:
            pipe.execute()
    pipe.execute()
    piped = time.time() - t0

    print(f"singoli : {single:.2f}s ({a.ops/single:.0f}/s)")
    print(f"pipeline: {piped:.2f}s ({a.ops/piped:.0f}/s)")
    print(f"speedup : {single/piped:.1f}x")


def p_bighash(a):
    """Un hash che cresce oltre la soglia di encoding."""
    r = conn(a)
    r.delete("bh")
    prev_enc = None
    for i in range(1, a.fields + 1):
        r.hset("bh", f"field:{i}", f"value:{i}")
        if i % a.step == 0 or i == a.fields:
            enc = r.object("encoding", "bh")
            mem = r.memory_usage("bh")
            flag = "  <-- CONVERSIONE" if enc != prev_enc and prev_enc else ""
            print(f"{i:6d} campi  {enc:10s}  {mem:9d} byte{flag}")
            prev_enc = enc


def p_hotkey(a):
    """Tutto il traffico su una sola chiave: hot key / hot slot."""
    r = conn(a)
    r.set("counter:global", 0)
    t0 = time.time()
    for _ in range(a.ops):
        r.incr("counter:global")
    dt = time.time() - t0
    print(f"{a.ops} INCR sulla stessa chiave in {dt:.2f}s ({a.ops/dt:.0f}/s)")


def p_scanner(a):
    """Endpoint 'dashboard' implementato con KEYS invece che con SCAN."""
    r = conn(a)
    t0 = time.time()
    keys = r.keys("session:*")
    dt = time.time() - t0
    print(f"KEYS  -> {len(keys)} chiavi in {dt*1000:.1f} ms (bloccante)")

    t0 = time.time()
    n = sum(1 for _ in r.scan_iter("session:*", count=1000))
    dt = time.time() - t0
    print(f"SCAN  -> {n} chiavi in {dt*1000:.1f} ms (non bloccante)")


def p_blocking(a):
    """Consumer bloccanti: ogni worker tiene una connessione occupata."""
    import threading

    def worker(i):
        r = conn(a)
        try:
            r.blpop("coda:inesistente", timeout=a.seconds)
        except Exception as e:
            print(f"worker {i}: {type(e).__name__}: {e}")

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(a.workers)]
    for t in ts:
        t.start()
    time.sleep(2)
    r = conn(a)
    info = r.info("clients")
    print(f"connected_clients={info['connected_clients']} "
          f"blocked_clients={info['blocked_clients']}")
    print(f"rejected_connections={r.info('stats')['rejected_connections']}")
    for t in ts:
        t.join()


PROFILES = {
    "sessions": p_sessions, "nopool": p_nopool, "pool": p_pool,
    "roundtrip": p_roundtrip, "bighash": p_bighash, "hotkey": p_hotkey,
    "scanner": p_scanner, "blocking": p_blocking,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profile", choices=sorted(PROFILES))
    ap.add_argument("--host", default=DEF_HOST)
    ap.add_argument("--port", type=int, default=DEF_PORT)
    ap.add_argument("--ops", type=int, default=5000)
    ap.add_argument("--keyspace", type=int, default=20000)
    ap.add_argument("--ttl", type=int, default=300)
    ap.add_argument("--value-size", type=int, default=200)
    ap.add_argument("--fields", type=int, default=700)
    ap.add_argument("--step", type=int, default=100)
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--seconds", type=int, default=5)
    a = ap.parse_args()
    try:
        PROFILES[a.profile](a)
    except redis.exceptions.RedisError as e:
        print(f"errore Redis: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
