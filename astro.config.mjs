// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';

// https://astro.build/config
export default defineConfig({
  // Su Cloudflare Pages il sito è statico (SSG): nessun adapter necessario.
  // Imposta `site` con l'URL definitivo per sitemap/canonical (facoltativo).
  // site: 'https://redis-ops-course.pages.dev',
  integrations: [
    // ⚠️ astro-mermaid DEVE precedere starlight: intercetta i blocchi ```mermaid
    // e li renderizza lato client (nessun headless browser al build → ok su CF Pages).
    mermaid({
      theme: 'default',
      autoTheme: true, // segue il tema chiaro/scuro di Starlight
    }),
    starlight({
      title: 'Redis Operations',
      description:
        'Corso operativo enterprise su Redis: install, sicurezza, HA, cluster, monitoring e lab.',
      defaultLocale: 'it',
      locales: {
        root: { label: 'Italiano', lang: 'it' },
      },
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/helloiamgio/redis-ops-course',
        },
      ],
      sidebar: [
        { label: 'Introduzione', link: '/' },
        {
          label: 'Fondamenti',
          items: [
            { label: '01 · Architettura e fondamenti', link: '/01-architettura/' },
          ],
        },
        {
          label: 'Installazione e configurazione',
          items: [
            { label: '02 · Installazione standalone', link: '/02-installazione-standalone/' },
            { label: '03 · Configurazione e sicurezza', link: '/03-configurazione-sicurezza/' },
            { label: '04 · Persistenza', link: '/04-persistenza/' },
          ],
        },
        {
          label: 'Alta disponibilità e scaling',
          items: [
            { label: '05 · Replica e Sentinel', link: '/05-replica-sentinel/' },
            { label: '06 · Redis Cluster', link: '/06-cluster/' },
          ],
        },
        {
          label: 'Operatività',
          items: [
            { label: '07 · Monitoring e tuning', link: '/07-monitoring-tuning/' },
            { label: '08 · Backup, upgrade, troubleshooting', link: '/08-backup-upgrade-troubleshooting/' },
          ],
        },
        {
          label: 'Pratica',
          items: [
            { label: '09 · Laboratori pratici', link: '/09-lab/' },
            { label: '10 · Casi d\u2019uso', link: '/10-casi-uso/' },
          ],
        },
        {
          label: 'Enterprise',
          items: [
            { label: '11 · Produzione enterprise', link: '/11-produzione-enterprise/' },
          ],
        },
        { label: 'Repository e deploy', link: '/deploy/' },
      ],
    }),
  ],
});
