---
title: "Redis Operations — Corso completo"
description: "Corso operativo enterprise su Redis: installazione standalone e cluster, sicurezza, HA, persistenza, monitoring, casi d'uso e lab validati su RHEL e macOS."
---

Corso operativo su **Redis** con taglio **Operations / SRE / Platform Engineering**.
Niente sviluppo applicativo: l'obiettivo è installare, configurare, mettere in
sicurezza, scalare, monitorare e mantenere Redis in produzione, standalone e in
cluster, su **RHEL 9** e **macOS**.

Tutti i comandi sono pensati per essere incollati direttamente nel terminale.
Dove RHEL e macOS divergono, trovi entrambe le varianti.

---

## A chi è rivolto

Sysadmin, SRE, platform/infra engineer che gestiscono Redis come servizio di
piattaforma (cache, session store, rate limiting, code, lock distribuiti) e
devono garantirne disponibilità, performance e ripristino.

Prerequisiti: dimestichezza con la shell Unix, `systemd`, networking di base
(porte, firewall, TLS), concetti di processo/memoria. Non serve saper
programmare.

---

## Versioni di riferimento (giugno 2026)

| Componente | Versione | Note |
|---|---|---|
| Redis Open Source | **8.x** (stable 8.8, mantenute 8.6 / 8.4) | dal `redis.io` ufficiale |
| Valkey | 9.x | fork BSD del Linux Foundation |
| RHEL | 9.x (validato anche su Rocky/Alma 9) | AppStream fornisce Redis 6/7 |
| macOS | 14/15 (Apple Silicon e Intel) | via Homebrew |

> **Nota su licenza e fork.** Da Redis 7.4 il core è passato a RSALv2/SSPLv1
> (source-available, non più open source "puro"). Da Redis 8.0 è stato aggiunto
> anche **AGPLv3**. Nel frattempo il Linux Foundation ha forkato l'ultima
> versione BSD creando **Valkey**. Conseguenza operativa concreta: **RHEL/EL 10
> ha rimosso `redis` dai repository e fornisce `valkey`**; RHEL 9 ha ancora il
> modulo AppStream `redis` (versioni 6/7, più datate). Per le ultime versioni su
> RHEL usi il repo ufficiale `packages.redis.io` o i repo Remi. Tutto il corso
> vale praticamente identico per Valkey: i comandi `redis-*` hanno gli equivalenti
> `valkey-*` e la compatibilità di protocollo/comandi è 1:1 fino a Redis 7.2.

---

## Struttura del corso

| # | Modulo | Contenuto |
|---|---|---|
| 01 | [Architettura e fondamenti](01-architettura.md) | Modello in-memory, single-thread, memoria, persistenza, RESP |
| 02 | [Installazione standalone](02-installazione-standalone.md) | RHEL 9 (repo, AppStream, sorgente), macOS, layout, systemd |
| 03 | [Configurazione e sicurezza](03-configurazione-sicurezza.md) | `redis.conf`, `CONFIG`, ACL, TLS, hardening |
| 04 | [Persistenza](04-persistenza.md) | RDB, AOF, recovery, scelta della strategia |
| 05 | [Replica e Sentinel](05-replica-sentinel.md) | Replica async, HA con Sentinel, failover |
| 06 | [Redis Cluster](06-cluster.md) | Hash slot, sharding, creazione, reshard, scaling |
| 07 | [Monitoring e tuning](07-monitoring-tuning.md) | `INFO`, SLOWLOG, LATENCY, eviction, kernel, Prometheus |
| 08 | [Backup, upgrade, troubleshooting](08-backup-upgrade-troubleshooting.md) | Backup/restore, DR, upgrade rolling, playbook diagnostici |
| 09 | [Laboratori pratici](09-lab.md) | 8 lab + capstone, con soluzioni, eseguibili su RHEL/macOS |
| 10 | [Casi d'uso](10-casi-uso.md) | Cache, sessioni, rate limiting, lock, code/Stream, pub/sub |
| 11 | [Produzione enterprise e go-live](11-produzione-enterprise.md) | Sizing, topologie, sicurezza/governance, SLO, runbook, checklist |

I moduli 01–08, 10 e 11 sono teoria + comandi. Il **modulo 09** è il workbook
pratico: ogni lab richiama i concetti del modulo corrispondente. Tutti i comandi
e i flussi dei lab (standalone, persistenza, ACL/TLS, replica+Sentinel, cluster
con reshard e failover, monitoring, backup/restore, troubleshooting) sono stati
**eseguiti e validati** su Redis reale.

---

## Ambiente di laboratorio consigliato

Non servono più macchine. Quasi tutti i lab (replica, Sentinel, cluster) girano
su **una sola macchina** lanciando più istanze Redis su porte diverse, sia su
RHEL sia su macOS. Dove serve isolamento reale (es. test di rete o firewall),
puoi usare 3–6 VM o container, ma è opzionale.

Requisiti minimi: 2 vCPU, 4 GB RAM, 10 GB disco. Per il modulo cluster meglio
4 GB liberi.

Convenzioni usate nel corso:

- I blocchi `bash` sono comandi da terminale; il prompt non è incluso così puoi
  copiare l'intero blocco.
- `# RHEL` e `# macOS` marcano le varianti specifiche per piattaforma.
- I percorsi di default usati: dati `/var/lib/redis`, config `/etc/redis/`,
  log `/var/log/redis/` su RHEL; su macOS (Homebrew Apple Silicon)
  `/opt/homebrew/etc/redis.conf` e `/opt/homebrew/var/db/redis/`.
- I **diagrammi** sono in **Mermaid**: si renderizzano nativamente su GitHub e
  GitLab e, in Astro Starlight, con un plugin Mermaid (es. `rehype-mermaid` +
  Playwright, oppure `astro-mermaid`). In editor che non lo supportano vedrai il
  sorgente testuale del diagramma, comunque leggibile.

Buon lavoro.
