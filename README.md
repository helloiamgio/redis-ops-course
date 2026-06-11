# Redis Operations — Corso completo

Corso operativo **enterprise** su Redis per profili di piattaforma/infrastruttura:
installazione standalone e cluster, sicurezza, alta disponibilità, persistenza,
monitoring, casi d'uso e laboratori pratici. In italiano.

Il repository è anche un **sito di documentazione** [Astro Starlight](https://starlight.astro.build/)
pronto per il deploy su **Cloudflare Pages**.

## Contenuti

| # | Modulo | |
|---|--------|---|
| 01 | Architettura e fondamenti | `src/content/docs/01-architettura.md` |
| 02 | Installazione standalone | `…/02-installazione-standalone.md` |
| 03 | Configurazione e sicurezza | `…/03-configurazione-sicurezza.md` |
| 04 | Persistenza | `…/04-persistenza.md` |
| 05 | Replica e Sentinel | `…/05-replica-sentinel.md` |
| 06 | Redis Cluster | `…/06-cluster.md` |
| 07 | Monitoring e tuning | `…/07-monitoring-tuning.md` |
| 08 | Backup, upgrade, troubleshooting | `…/08-backup-upgrade-troubleshooting.md` |
| 09 | Laboratori pratici (8 lab + capstone) | `…/09-lab.md` |
| 10 | Casi d'uso | `…/10-casi-uso.md` |
| 11 | Produzione enterprise e go-live | `…/11-produzione-enterprise.md` |

Tutti i comandi e i flussi dei laboratori (standalone, persistenza, ACL/TLS,
replica + Sentinel con failover, cluster con reshard e node failure, monitoring,
backup/restore, troubleshooting e i casi d'uso) sono stati **eseguiti e validati**
su Redis reale. I 27 diagrammi sono in **Mermaid** (renderizzati nativamente da
GitHub/GitLab e, nel sito, da `astro-mermaid` lato client).

## Avvio rapido (sito)

```bash
nvm use            # Node 22 (vedi .nvmrc)
npm install
npm run dev        # http://localhost:4321
```

Build statico (output in `dist/`):

```bash
npm run build && npm run preview
```

## Deploy su Cloudflare Pages

Guida completa: [`src/content/docs/deploy.md`](src/content/docs/deploy.md).
In sintesi (Git integration): framework **Astro**, build command `npm run build`,
output directory `dist`, `NODE_VERSION=22`.

## Laboratori

Gli script helper per i lab più articolati sono in [`labs/scripts/`](labs/scripts/)
(avvio/teardown di un cluster a 6 nodi e di uno stack Sentinel in locale). Versioni
di riferimento: Redis 8.x (i lab sono compatibili e validati anche su 7.x).

## Licenza

Contenuti del corso rilasciati con licenza **CC BY-SA 4.0** (vedi [`LICENSE`](LICENSE)).
