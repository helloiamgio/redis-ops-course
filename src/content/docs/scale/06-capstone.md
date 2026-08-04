---
title: "Scale · 06 · Capstone"
description: "Esercizio finale: progettare, costruire, rompere e documentare un deployment Redis completo."
---

Esercizio conclusivo senza comandi pronti: qui costruisci tu, con quello che hai
usato nelle cinque unità precedenti.

---

## Scenario

Ti viene chiesto di mettere in esercizio Redis come **cache di sessione** per un
applicativo con questi vincoli:

- 40 GB di dataset stimato a regime, chiavi con TTL di 30 minuti
- 12 istanze applicative, ciascuna con pool da 50 connessioni
- picco a 120.000 ops/s, letture 80% / scritture 20%
- RTO 60 secondi, RPO 5 minuti
- tre nodi fisici in due sale, storage locale NVMe
- finestra di patching mensile senza interruzione di servizio

---

## Consegna 1 — Progetto

Decidi e **motiva per iscritto**:

1. Standalone + Sentinel, oppure Cluster? Il discriminante è il dataset da
   40 GB, non le ops/s: quale limite tocchi per primo?
2. `maxmemory` per istanza e policy di eviction. Ricorda il margine per il fork.
3. Persistenza: RDB, AOF, entrambi, nessuna? Con RPO 5 minuti, cosa è
   effettivamente necessario?
4. Connessioni totali attese: verifica contro `maxclients` e contro
   `LimitNOFILE`. Quanto margine lasci?
5. Distribuzione dei nodi sulle due sale: dove finiscono i Sentinel (o le
   replica cluster) perché il quorum sopravviva alla perdita di una sala?

:::note[La domanda con la trappola]
Due sale e un quorum dispari non stanno insieme. Come lo risolvi, e cosa
accetti di perdere se cade la sala che ospita la maggioranza?
:::

---

## Consegna 2 — Build

Costruisci la topologia scelta in locale, con i comandi delle unità 03 o 04.
Requisiti:

- avvio scriptato e **idempotente** (rieseguirlo non deve rompere nulla)
- attese condizionate, mai `sleep` fissi
- verifica finale automatica che fallisca con exit code ≠ 0 se lo stato non è
  quello atteso

Traccia dello script di verifica:

```bash
#!/usr/bin/env bash
set -euo pipefail
fail() { echo "KO: $1" >&2; exit 1; }

[ "$(redis-cli -p 6379 PING)" = "PONG" ] || fail "master non risponde"
# ... aggiungi: ruoli, master_link_status, quorum, cluster_state,
#     rdb_last_bgsave_status, maxmemory impostato, rejected_connections = 0
echo "OK"
```

---

## Consegna 3 — Rompi

Esegui questi guasti e **cronometra il recupero**:

| Guasto | Come | Cosa misuri |
|---|---|---|
| Master ucciso | `kill -9` | tempo fino al nuovo master servente |
| Rete della replica | `CLIENT KILL TYPE replica` sul master | partial o full sync? |
| Disco pieno | riempi la dir di lavoro | cosa fa `BGSAVE`, cosa risponde il master |
| Saturazione connessioni | `maxclients` basso + client in loop | quale contatore lo rivela per primo |
| Comando lento | `DEBUG SLEEP` | lo slowlog lo cattura con la tua soglia? |

Per ognuno registra: **cosa hai visto per primo** (log, metrica o errore
applicativo), tempo di rilevamento, tempo di recupero.

:::caution[Il guasto che insegna di più]
Il disco pieno. Redis con `stop-writes-on-bgsave-error yes` (default) smette di
accettare scritture al primo `BGSAVE` fallito e risponde `MISCONF`. Molti lo
scoprono in produzione. Riprodurlo qui costa cinque minuti.
:::

---

## Consegna 4 — Documenta

Produci tre artefatti, quelli che servono davvero al passaggio in esercizio:

**a) Runbook di primo livello** — la catena diagnostica in otto passi
dell'[unità 05](/scale/05-osservabilita/#esercizio-57--la-catena-diagnostica-completa),
adattata alla tua topologia, con le soglie decise da te.

**b) Procedura di patching senza downtime** — sequenza esatta di comandi per
aggiornare tutti i nodi rispettando il vincolo di continuità. Punto chiave:
si patcha sempre prima la replica, si promuove in modo coordinato, si patcha
l'ex master.

**c) Tabella delle allerte** — metrica, soglia, severità, azione. Massimo dieci
righe: se ne servono di più, non hai deciso cosa conta.

---

## Autovalutazione

Il lavoro è completo quando sai rispondere senza consultare la
documentazione:

- [ ] Perché hai scelto quella topologia e a quale soglia cambieresti idea
- [ ] Quanta memoria hai lasciato al fork e perché quella cifra
- [ ] Quanti dati perdi nel caso peggiore, misurato non stimato
- [ ] Chi si accorge per primo di un failover: il monitoraggio o l'utente
- [ ] Cosa succede se cade la sala con la maggioranza del quorum
- [ ] Quale comando esegui per primo quando arriva la segnalazione

---

## Dove continuare

- [11 · Produzione enterprise](/11-produzione-enterprise/) — sizing, SLO,
  runbook, go-live
- [12 · Kubernetes e OpenShift](/12-kubernetes-openshift/) — la stessa
  topologia con operator e StatefulSet
- [13 · Connessioni e client tuning](/13-connessioni-client-tuning/) — il
  riferimento teorico dell'unità 01
