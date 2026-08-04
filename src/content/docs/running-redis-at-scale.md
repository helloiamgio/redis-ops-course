---
title: "Percorso · Running Redis at Scale"
description: "Mappatura tra il syllabus ufficiale Redis University 'Running Redis at Scale' e i moduli di questo corso."
---

[Running Redis at Scale](https://redis.io/tutorials/operate/redis-at-scale/) è il
corso operativo ufficiale gratuito di Redis University. Questa pagina è
l'**indice di corrispondenza**: per ogni unità ufficiale trovi i moduli di questo
corso che coprono lo stesso terreno, più il link alla fonte originale.

:::note
I contenuti di questo sito sono scritti da zero, non sono una copia del corso
ufficiale. Segui i link per il materiale originale, i video e i quiz di Redis
University.
:::

---

## Percorso hands-on

Se vuoi **eseguire** invece che leggere, il percorso
[Scale](/scale/00-setup/) copre le stesse cinque unità in forma di laboratorio:
installazione, esercizi con output atteso, guasti da riprodurre e capstone
finale. Tutti i comandi sono stati validati su Redis reale.

| Unità | Laboratorio |
|---|---|
| Setup | [00 · Setup dell'ambiente](/scale/00-setup/) |
| 1 · Talking to Redis | [01 · Connessioni](/scale/01-connessioni/) |
| 2 · Persistence | [02 · Persistenza](/scale/02-persistenza/) |
| 3 · High Availability | [03 · Alta disponibilità](/scale/03-alta-disponibilita/) |
| 4 · Scalability | [04 · Scalabilità](/scale/04-scalabilita/) |
| 5 · Observability | [05 · Osservabilità](/scale/05-osservabilita/) |
| — | [06 · Capstone](/scale/06-capstone/) |

---

## Corrispondenza unità → moduli teorici

| Unità ufficiale | Argomenti | Moduli di questo corso |
|---|---|---|
| **1 · Talking to Redis** | gestione e tuning delle connessioni, protocollo, client | [13 · Connessioni e client tuning](/13-connessioni-client-tuning/) · [03 · Configurazione e sicurezza](/03-configurazione-sicurezza/) |
| **2 · Persistence and Durability** | RDB, AOF, trade-off durabilità/performance | [04 · Persistenza](/04-persistenza/) |
| **3 · High Availability** | replica, failover, Sentinel | [05 · Replica e Sentinel](/05-replica-sentinel/) |
| **4 · Scalability** | Redis Cluster, sharding, throughput e capacità | [06 · Redis Cluster](/06-cluster/) |
| **5 · Observability** | metriche, monitoring, diagnosi | [07 · Monitoring e tuning](/07-monitoring-tuning/) |

---

## Cosa aggiunge questo corso

Argomenti fuori dal perimetro del corso ufficiale, ma necessari in un contesto
enterprise on-prem:

| Tema | Modulo |
|---|---|
| Installazione e hardening su RHEL 8/9, ACL, TLS | [02](/02-installazione-standalone/) · [03](/03-configurazione-sicurezza/) |
| Backup, restore, upgrade, troubleshooting | [08](/08-backup-upgrade-troubleshooting/) |
| Laboratori eseguibili end-to-end | [09](/09-lab/) |
| Sizing, SLO, runbook, go-live | [11](/11-produzione-enterprise/) |
| Redis su Kubernetes e OpenShift (StatefulSet, operator, SCC) | [12](/12-kubernetes-openshift/) |
| Cheatsheet comandi ops-ready | [cheatsheet](/cheatsheet/) |

---

## Come usare i due materiali insieme

1. Segui l'unità ufficiale su redis.io per la teoria e i quiz.
2. Esegui i lab corrispondenti del [modulo 09](/09-lab/) — girano in locale con
   Docker Compose e riproducono failover, resharding e scenari di guasto.
3. Chiudi con il [modulo 11](/11-produzione-enterprise/) per portare il tutto in
   un contesto con change management, SLO e runbook.

:::tip[Certificazione]
La Redis Developer Certification è stata deprecata nel giugno 2024 e non ha
ancora una sostituta. Da Redis University ottieni certificati di completamento
superando esami e quiz con almeno l'80%.
:::

---

## Prerequisiti dei lab ufficiali

Il corso ufficiale presuppone `redis-server` e `redis-cli` nel `$PATH`, più
Docker e Docker Compose per gli esercizi. Se hai già seguito il
[modulo 02](/02-installazione-standalone/), sei a posto.

```bash
redis-server --version
redis-cli --version
docker compose version
```
