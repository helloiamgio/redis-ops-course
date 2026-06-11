---
title: "Repository e deploy su Cloudflare Pages"
description: "Struttura del repository, sviluppo locale e pubblicazione del corso come sito Astro Starlight su Cloudflare Pages (Git integration e Wrangler CLI)."
---

Questo corso **è** un sito [Astro Starlight](https://starlight.astro.build/):
i contenuti vivono in `src/content/docs/` e si pubblicano come sito statico su
**Cloudflare Pages**. I diagrammi Mermaid sono renderizzati **lato client**
(integrazione `astro-mermaid`), quindi il build non richiede browser headless e
funziona ovunque, CF Pages incluso.

## Struttura del repository

```
redis-ops-course/
├── astro.config.mjs          # config Astro + Starlight; mermaid() PRIMA di starlight()
├── package.json              # dipendenze e script (dev/build/preview)
├── tsconfig.json
├── src/
│   ├── content.config.ts     # content collection "docs" (docsLoader + docsSchema)
│   └── content/docs/         # i moduli del corso (Markdown con frontmatter)
│       ├── index.md          # landing
│       ├── 01-architettura.md … 11-produzione-enterprise.md
│       └── deploy.md          # questa pagina
├── public/                   # asset statici (favicon, ecc.)
└── labs/scripts/             # script helper per i lab (cluster/sentinel up/down)
```

## Prerequisiti

- **Node.js 20 o 22 LTS** (vedi `.nvmrc`). Con nvm: `nvm use`.
- Account Cloudflare (piano Free sufficiente).
- Repository su GitHub o GitLab (consigliato per il deploy automatico).

## Sviluppo locale

```bash
npm install
```

```bash
npm run dev
```

Apri `http://localhost:4321`. Per verificare il sito statico prodotto:

```bash
npm run build && npm run preview
```

Il build genera la cartella **`dist/`** (l'output che Cloudflare Pages serve).

## Deploy A — Git integration (consigliato)

Pubblicazione automatica a ogni push.

1. Fai push del repository su GitHub/GitLab.
2. Cloudflare Dashboard → **Workers & Pages** → **Create** → **Pages** →
   **Connect to Git**, e seleziona il repository.
3. Imposta la build:
   - **Framework preset**: `Astro`
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Node version**: definisci la variabile d'ambiente `NODE_VERSION = 22`
     (oppure affidati a `.nvmrc`).
4. **Save and Deploy**. Al termine ottieni un URL `https://<progetto>.pages.dev`;
   ogni push su `main` ripubblica, ogni branch/PR genera una *preview*.

> Se imposti `site` in `astro.config.mjs` con l'URL definitivo, sitemap e link
> canonici saranno coerenti.

## Deploy B — Wrangler CLI (build locale)

Utile per pubblicare senza collegare Git.

```bash
npm install -D wrangler
```

```bash
npm run build && npx wrangler pages deploy dist --project-name=redis-ops-course
```

Il primo deploy crea il progetto Pages; i successivi lo aggiornano. Per un dominio
personalizzato: progetto Pages → **Custom domains** → aggiungi il dominio (con DNS
su Cloudflare la configurazione è automatica).

## Note su Mermaid

I blocchi ` ```mermaid ` nei file Markdown vengono trasformati in diagrammi
**nel browser** da `astro-mermaid`. Vincoli importanti della configurazione:

- `mermaid()` deve precedere `starlight()` nell'array `integrations` (così i
  blocchi non vengono trattati come semplice codice da Expressive Code).
- `autoTheme: true` allinea i diagrammi al tema chiaro/scuro di Starlight.

Gli stessi file, su GitHub e GitLab, mostrano i diagrammi Mermaid renderizzati
nativamente: il repository resta leggibile anche senza pubblicare il sito.

## Aggiornare i contenuti

Modifica o aggiungi file in `src/content/docs/` (con frontmatter `title`), poi
aggiorna la voce corrispondente nella `sidebar` di `astro.config.mjs`. Con la Git
integration, il push pubblica automaticamente.
